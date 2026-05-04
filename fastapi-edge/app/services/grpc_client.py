"""Spring Boot 백엔드로 통과 이벤트를 전송하는 gRPC 클라이언트.

설계 포인트
----------
1. 비동기 큐 기반 스트리밍
   - YOLO 콜백이 큐에 PassageEventRequest 를 push 만 하고 즉시 반환.
   - 백그라운드 worker 가 StreamPassageEvents 양방향 스트림으로 송신.
   - 네트워크 끊김/백엔드 다운 시에도 엣지 처리량이 영향받지 않는다.

2. 재연결 + 지수 백오프
   - 채널이 끊기면 backoff 로 재연결, 큐에 쌓인 이벤트는 보존.

3. 멱등성
   - event_id(UUID) 를 키로 백엔드가 중복을 걸러낸다.

4. 검수 분기
   - plate_confidence < threshold 인 케이스는 단건 RPC(SendPassageEvent)
     로 분리 전송하여 PENDING_REVIEW 상태로 적재되도록 한다.

NOTE
----
- 본 파일은 `tolling_pb2`, `tolling_pb2_grpc` (proto 컴파일 결과물) 을
  import 한다. 컴파일 방법은 scripts/generate_proto.sh 참고.
- 컴파일 전에는 import 오류가 나므로, 모듈 임포트는 lazy 로 처리.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from app.core.config import Settings
from app.models.schemas import GpsTelemetry, VehicleTypeEnum, YoloDetection
from app.services.crossing import CrossingDecision

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Lazy proto import
# ------------------------------------------------------------------ #
def _load_proto_modules():
    """generate_proto.sh 실행 후 생성되는 모듈을 lazy import."""
    from app.grpc_generated import tolling_pb2, tolling_pb2_grpc  # noqa: WPS433
    return tolling_pb2, tolling_pb2_grpc


# ------------------------------------------------------------------ #
# 매핑 테이블
# ------------------------------------------------------------------ #
_VEHICLE_TYPE_MAP = {
    VehicleTypeEnum.UNKNOWN: 0,
    VehicleTypeEnum.PASSENGER: 1,
    VehicleTypeEnum.VAN: 2,
    VehicleTypeEnum.TRUCK: 3,
    VehicleTypeEnum.BUS: 4,
    VehicleTypeEnum.SPECIAL: 5,
    VehicleTypeEnum.MOTORCYCLE: 6,
}

_DIRECTION_MAP = {"unknown": 0, "entry": 1, "exit": 2}


def _to_pb_timestamp(dt: datetime) -> Timestamp:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = Timestamp()
    ts.FromDatetime(dt.astimezone(timezone.utc))
    return ts


# ------------------------------------------------------------------ #
# 클라이언트
# ------------------------------------------------------------------ #
class TollingGrpcClient:
    """비동기 gRPC 클라이언트 + 송신 큐 워커."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=settings.send_queue_max_size)
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub = None
        self._pb2 = None
        self._pb2_grpc = None
        self._stream_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    # -------------------------------------------------------------- #
    # 라이프사이클
    # -------------------------------------------------------------- #
    async def start(self) -> None:
        self._pb2, self._pb2_grpc = _load_proto_modules()
        await self._connect()
        self._stream_task = asyncio.create_task(self._stream_worker(), name="grpc-stream-worker")
        logger.info("TollingGrpcClient started → %s", self._settings.grpc_target)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._stream_task:
            await asyncio.sleep(0)
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._channel:
            await self._channel.close()
        logger.info("TollingGrpcClient stopped")

    async def _connect(self) -> None:
        if self._settings.grpc_use_tls:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(self._settings.grpc_target, credentials)
        else:
            self._channel = grpc.aio.insecure_channel(self._settings.grpc_target)
        self._stub = self._pb2_grpc.TollingEventServiceStub(self._channel)

    # -------------------------------------------------------------- #
    # 외부에서 호출하는 enqueue API
    # -------------------------------------------------------------- #
    async def enqueue_event(
        self,
        det: YoloDetection,
        decision: CrossingDecision,
        gps: Optional[GpsTelemetry],
    ) -> None:
        if not decision.crossed:
            return  # 통과 안 한 트랙은 송신 대상이 아님

        request = self._build_request(det, decision, gps)

        # 저신뢰도는 단건 RPC 로 빠르게 검수 큐에 적재
        if det.plate_confidence < self._settings.low_ocr_confidence_threshold:
            asyncio.create_task(self._send_unary(request), name="grpc-unary-low-conf")
            return

        try:
            self._queue.put_nowait(request)
        except asyncio.QueueFull:
            logger.error(
                "Send queue full (%d). Dropping event_id=%s",
                self._settings.send_queue_max_size,
                request.event_id,
            )

    # -------------------------------------------------------------- #
    # 빌더
    # -------------------------------------------------------------- #
    def _build_request(
        self,
        det: YoloDetection,
        decision: CrossingDecision,
        gps: Optional[GpsTelemetry],
    ):
        pb2 = self._pb2
        req = pb2.PassageEventRequest()
        req.event_id = str(uuid.uuid4())
        req.edge_node_id = self._settings.edge_node_id
        req.lane_id = det.lane_id
        req.plate = det.plate_text or ""
        req.plate_confidence = float(det.plate_confidence)
        req.vehicle_type = _VEHICLE_TYPE_MAP.get(det.vehicle_type, 0)
        req.direction = _DIRECTION_MAP.get(decision.direction, 0)
        req.captured_at.CopyFrom(_to_pb_timestamp(det.captured_at))

        if gps is not None:
            req.gps.latitude = gps.latitude
            req.gps.longitude = gps.longitude
            req.gps.speed_kmh = gps.speed_kmh
            req.gps.heading = gps.heading
            req.gps.captured_at.CopyFrom(_to_pb_timestamp(gps.captured_at))

        # ROI 썸네일은 선택. base64 → bytes 변환은 호출부 책임.
        # (여기서는 간단히 비워둠. YOLO 담당이 raw bytes 로 넘기도록 확장 가능.)

        track = req.track
        track.track_id = det.track_id
        track.frame_index = det.frame_index
        track.bbox_x = det.bbox.x
        track.bbox_y = det.bbox.y
        track.bbox_w = det.bbox.w
        track.bbox_h = det.bbox.h
        track.crossing_ratio = decision.crossing_ratio
        return req

    # -------------------------------------------------------------- #
    # 단건 RPC (저신뢰도 / 보정 재전송)
    # -------------------------------------------------------------- #
    async def _send_unary(self, request) -> None:
        backoff = self._settings.grpc_initial_backoff_sec
        for attempt in range(1, self._settings.grpc_max_retries + 1):
            try:
                resp = await self._stub.SendPassageEvent(
                    request,
                    timeout=self._settings.grpc_request_timeout_sec,
                )
                logger.info(
                    "[unary] event_id=%s status=%s message=%s",
                    request.event_id, resp.status, resp.message,
                )
                return
            except grpc.aio.AioRpcError as exc:
                logger.warning(
                    "[unary] attempt=%d failed: %s (%s)",
                    attempt, exc.code(), exc.details(),
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._settings.grpc_max_backoff_sec)
        logger.error("[unary] giving up event_id=%s", request.event_id)

    # -------------------------------------------------------------- #
    # 스트리밍 워커 (정상 트래픽)
    # -------------------------------------------------------------- #
    async def _stream_worker(self) -> None:
        backoff = self._settings.grpc_initial_backoff_sec
        while not self._stop_event.is_set():
            try:
                await self._stream_loop()
                backoff = self._settings.grpc_initial_backoff_sec  # 정상 종료 시 리셋
            except grpc.aio.AioRpcError as exc:
                logger.warning(
                    "Stream broken: %s (%s). reconnect in %.1fs",
                    exc.code(), exc.details(), backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._settings.grpc_max_backoff_sec)
                await self._reconnect()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Stream worker unexpected error")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._settings.grpc_max_backoff_sec)

    async def _stream_loop(self) -> None:
        async def request_iter():
            while not self._stop_event.is_set():
                req = await self._queue.get()
                yield req

        # 양방향 스트리밍. 백엔드 응답은 로깅만.
        call = self._stub.StreamPassageEvents(request_iter())
        async for response in call:
            logger.debug(
                "[stream] ack event_id=%s status=%s",
                response.event_id, response.status,
            )

    async def _reconnect(self) -> None:
        if self._channel:
            await self._channel.close()
        await self._connect()
