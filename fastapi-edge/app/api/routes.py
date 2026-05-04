"""FastAPI 라우터.

Endpoints
---------
- POST /v1/yolo/detections : YOLO 모듈로부터 검출 배치를 수신
- POST /v1/gps/track       : 트랙 단위 GPS 푸시
- POST /v1/gps/lane        : 차로 단위 GPS 푸시
- GET  /healthz            : 헬스체크
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.models.schemas import GpsTelemetry, YoloBatch
from app.services.crossing import CrossingLineDetector
from app.services.grpc_client import TollingGrpcClient
from app.services.gps_service import GpsCache
from app.services.spring_client import SpringRestClient

logger = logging.getLogger(__name__)
router = APIRouter()


# 상태(서비스) 의존성 주입 helper
def get_detector(req: Request) -> CrossingLineDetector:
    return req.app.state.detector


def get_grpc_client(req: Request) -> TollingGrpcClient:
    return req.app.state.grpc_client


def get_gps_cache(req: Request) -> GpsCache:
    return req.app.state.gps_cache


def get_spring_client(req: Request) -> SpringRestClient:
    return req.app.state.spring_client


# ------------------------------------------------------------------ #
# YOLO 검출 수신
# ------------------------------------------------------------------ #
@router.post("/v1/yolo/detections", status_code=status.HTTP_202_ACCEPTED)
async def receive_detections(
    batch: YoloBatch,
    detector: CrossingLineDetector = Depends(get_detector),
    grpc_client: TollingGrpcClient = Depends(get_grpc_client),
    gps_cache: GpsCache = Depends(get_gps_cache),
):
    crossed_count = 0
    for det in batch.detections:
        # GPS 결합: 검출에 포함된 telemetry 우선, 없으면 캐시 fallback
        gps = det.gps or gps_cache.latest_for(det.track_id, det.lane_id)

        decision = detector.evaluate(det)
        if decision.crossed:
            crossed_count += 1
            await grpc_client.enqueue_event(det, decision, gps)
    return {"received": len(batch.detections), "crossed": crossed_count}


# ------------------------------------------------------------------ #
# GPS 푸시
# ------------------------------------------------------------------ #
@router.post("/v1/gps/track/{track_id}")
async def push_gps_for_track(
    track_id: int,
    telemetry: GpsTelemetry,
    gps_cache: GpsCache = Depends(get_gps_cache),
    spring_client: SpringRestClient = Depends(get_spring_client),
):
    if track_id < 0:
        raise HTTPException(status_code=400, detail="invalid track_id")
    gps_cache.upsert_for_track(track_id, telemetry)
    await spring_client.send_gps_telemetry(telemetry, track_id=track_id)
    return {"ok": True}


@router.post("/v1/gps/lane/{lane_id}")
async def push_gps_for_lane(
    lane_id: str,
    telemetry: GpsTelemetry,
    gps_cache: GpsCache = Depends(get_gps_cache),
    spring_client: SpringRestClient = Depends(get_spring_client),
):
    gps_cache.upsert_for_lane(lane_id, telemetry)
    await spring_client.send_gps_telemetry(telemetry, lane_id=lane_id)
    return {"ok": True}


# ------------------------------------------------------------------ #
# 헬스체크
# ------------------------------------------------------------------ #
@router.get("/healthz")
async def healthz():
    return {"status": "ok"}
