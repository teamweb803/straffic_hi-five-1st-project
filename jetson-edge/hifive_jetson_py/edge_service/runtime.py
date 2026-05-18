from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from hifive_jetson_py.config import RuntimeConfig
from hifive_jetson_py.event_builder import PassageEventBuilder
from hifive_jetson_py.ocr_tensorrt import TensorRtOcrRunner
from hifive_jetson_py.protobuf_codec import PassageEventCodec
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.transport import build_sender
from hifive_jetson_py.yolo_tensorrt import TensorRtYoloRunner

from .display import GREEN, draw_runtime_overlay, draw_text, show_frame
from .event_dispatcher import EventDispatcher
from .ocr_worker import OcrWorker
from .plate_tracker import PlateBBoxTracker
from .status_sender import EdgeStatusSender
from .types import OcrTask, ReadyPlateEvent, SharedState
from .video_source import FrameSource
from .yolo_worker import YoloWorker


@dataclass(frozen=True)
class EdgeServiceRuntimeOptions:
    config_path: str
    camera_index: int = 0
    video_override: str = ""
    host_override: str = ""
    port_override: int = 0
    standby_host_override: str = ""
    standby_port_override: int = 0
    failover_recheck_sec: float = 0.5
    runtime_runner: str = "deepstream-nvinfer"
    input_backend: str = "deepstream"
    display: bool = False
    display_scale: float = 0.75
    display_sink: str = "egl"
    start_sec: float = 0.0
    frame_limit: int = 0
    height_threshold: int = 20
    ocr_stable_sec: float = 0.30
    track_memory_sec: float = 1.0
    reid_sec: float = 10.0
    queue_size: int = 8
    transport_queue_size: int = 128
    transport_timeout_sec: float = 0.3
    retry_initial_sec: float = 0.2
    retry_max_sec: float = 2.0
    yolo_engine_override: str = ""
    ocr_engine_override: str = ""
    output_dir: str = "/home/jetson/hifive/output/edge_service"
    save_event_images: bool = True
    status_interval_sec: float = 1.0
    preview_datagram_fps: float = 0.0
    preview_jpeg_quality: int = 45
    srt_host: str = ""
    srt_port: int = 0
    srt_bitrate_kbps: int = 2500
    srt_latency_ms: int = 120
    srt_iframe_interval: int = 30
    evidence_upload: bool = False
    evidence_jpeg_quality: int = 85
    parser_lib: str = "/home/jetson/hifive/deepstream_plugins/libnvdsinfer_custom_hifive.so"
    yolo_parser_lib: str = ""
    ocr_parser_lib: str = ""
    yolo_parser_func: str = "NvDsInferParseCustomYoloPlate"
    ocr_parser_func: str = "NvDsInferParseCustomCrnnPlate"
    tracker_lib: str = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
    tracker_config: str = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"
    external_stop_event: threading.Event | None = None


class EdgeServiceRuntime:
    def __init__(self, options: EdgeServiceRuntimeOptions) -> None:
        self.options = options

    def run(self) -> None:
        config = self._load_config()
        if not config.cameras:
            raise RuntimeError("at least one camera is required")
        camera = config.cameras[self.options.camera_index]

        codec = PassageEventCodec(schema_version=config.schema_version)
        spool = FileSpool(config.spool_dir)
        sender = build_sender(config.transport, spool)
        builder = PassageEventBuilder(config=config, codec=codec, sender=sender)

        yolo_runner = TensorRtYoloRunner(
            engine_path=config.yolo.engine_path,
            confidence_threshold=config.yolo.confidence_threshold,
            input_width=config.yolo.input_width,
            input_height=config.yolo.input_height,
        )
        ocr_runner = TensorRtOcrRunner(
            engine_path=config.ocr.engine_path,
            vocab_path=config.ocr.vocab_path,
        )

        source = FrameSource(
            camera=camera,
            source_override=self.options.video_override,
            start_sec=self.options.start_sec,
            input_backend=self.options.input_backend,
        )
        cap, open_mode = source.open()
        source_fps = cap.get(5) or 30.0
        tracker = PlateBBoxTracker(
            fps=source_fps,
            memory_sec=self.options.track_memory_sec,
            reid_sec=self.options.reid_sec,
        )
        stop_event = self.options.external_stop_event or threading.Event()
        shared = SharedState(lock=threading.Lock(), stop_event=stop_event)
        source_mode = "video" if self.options.video_override else "camera"
        source_value = self.options.video_override or camera.source_uri or camera.source_pipeline or str(self.options.camera_index)
        started_at_ms = int(time.time() * 1000)
        output_dir = Path(self.options.output_dir)
        if self.options.status_interval_sec > 0:
            EdgeStatusSender(
                config=config,
                camera=camera,
                sender=sender,
                shared=shared,
                spool=spool,
                output_dir=output_dir,
                interval_sec=self.options.status_interval_sec,
                source_mode=source_mode,
                source_value=source_value,
                started_at_ms=started_at_ms,
            ).start()
        ocr_queue: queue.Queue[OcrTask] = queue.Queue(maxsize=self.options.queue_size)
        event_queue: queue.Queue[ReadyPlateEvent] = queue.Queue()
        OcrWorker(
            ocr_runner=ocr_runner,
            tracker=tracker,
            input_queue=ocr_queue,
            event_queue=event_queue,
            shared=shared,
            stable_sec=self.options.ocr_stable_sec,
            min_confidence=config.ocr.confidence_threshold,
        ).start()

        yolo_worker = YoloWorker(
            camera=camera,
            yolo_runner=yolo_runner,
            tracker=tracker,
            ocr_queue=ocr_queue,
            shared=shared,
            height_threshold=self.options.height_threshold,
        )
        dispatcher = EventDispatcher(
            config=config,
            builder=builder,
            shared=shared,
            queue_size=self.options.transport_queue_size,
        )
        if self.options.save_event_images:
            output_dir.mkdir(parents=True, exist_ok=True)

        print(f"edge_service=started mode={open_mode} camera={camera.camera_id}")
        print(f"yolo_engine={config.yolo.engine_path}")
        print(f"ocr_engine={config.ocr.engine_path}")
        print(f"transport={config.transport.kind} host={config.transport.ingress_host} port={config.transport.ingress_port}")
        print(f"edge_status_interval_sec={self.options.status_interval_sec}")

        frame_num = int(cap.get(1) or 0)
        processed = 0
        last_loop_at = time.perf_counter()
        try:
            while not shared.stop_event.is_set() and (self.options.frame_limit <= 0 or processed < self.options.frame_limit):
                ok, frame = cap.read()
                if not ok:
                    break

                now = time.perf_counter()
                dt = max(1e-6, now - last_loop_at)
                last_loop_at = now
                with shared.lock:
                    instant_fps = 1.0 / dt
                    shared.latest_fps = instant_fps if shared.latest_fps <= 0 else shared.latest_fps * 0.85 + instant_fps * 0.15

                result = yolo_worker.process_frame(frame, frame_num=frame_num, timestamp_ns=time.time_ns())
                with shared.lock:
                    shared.processed_frames = processed + 1
                self._drain_events(event_queue, dispatcher, output_dir)

                if self.options.display:
                    draw_runtime_overlay(
                        result.canvas,
                        list(tracker.tracks.values()),
                        shared,
                        self.options.height_threshold,
                        frame_num,
                    )
                    if not show_frame("HI-FIVE Edge Service", result.canvas, self.options.display_scale):
                        break

                frame_num += 1
                processed += 1
        finally:
            shared.stop_event.set()
            cap.release()
            if self.options.display:
                import cv2

                cv2.destroyAllWindows()

        print(
            f"edge_service=stopped processed_frames={processed} "
            f"events={shared.sent_events} spool_count={spool.count()} detections={shared.yolo_detections}"
        )

    def _load_config(self) -> RuntimeConfig:
        config = RuntimeConfig.from_python_file(self.options.config_path)
        transport = config.transport
        if self.options.host_override:
            transport = replace(transport, ingress_host=self.options.host_override)
        if self.options.port_override > 0:
            transport = replace(transport, ingress_port=self.options.port_override)
        if self.options.standby_host_override:
            transport = replace(
                transport,
                failover_enabled=True,
                standby_ingress_host=self.options.standby_host_override,
            )
        if self.options.standby_port_override > 0:
            transport = replace(transport, standby_ingress_port=self.options.standby_port_override)
        if self.options.failover_recheck_sec > 0:
            transport = replace(transport, failover_recheck_sec=self.options.failover_recheck_sec)
        if self.options.transport_timeout_sec > 0:
            transport = replace(transport, timeout_sec=self.options.transport_timeout_sec)
        if self.options.retry_initial_sec > 0:
            transport = replace(transport, retry_initial_sec=self.options.retry_initial_sec)
        if self.options.retry_max_sec > 0:
            transport = replace(transport, retry_max_sec=self.options.retry_max_sec)
        if transport is not config.transport:
            config = replace(config, transport=transport)
        if self.options.yolo_engine_override:
            config = replace(config, yolo=replace(config.yolo, engine_path=self.options.yolo_engine_override))
        if self.options.ocr_engine_override:
            config = replace(config, ocr=replace(config.ocr, engine_path=self.options.ocr_engine_override))
        return config

    def _drain_events(
        self,
        event_queue: queue.Queue[ReadyPlateEvent],
        dispatcher: EventDispatcher,
        output_dir: Path,
    ) -> None:
        while True:
            try:
                ready = event_queue.get_nowait()
            except queue.Empty:
                return
            dispatcher.submit(ready)
            if self.options.save_event_images:
                self._save_event_images(output_dir, ready)
            print(
                f"event track=#{ready.task.display_id} lane={ready.task.lane_no} "
                f"plate={ready.text} conf={ready.confidence:.4f} frame={ready.task.frame_num}"
            )

    def _save_event_images(self, output_dir: Path, ready: ReadyPlateEvent) -> None:
        import cv2

        task = ready.task
        if task.canvas_snapshot is None:
            return
        annotated = task.canvas_snapshot.copy()
        cv2.rectangle(
            annotated,
            (task.yolo_bbox.x, task.yolo_bbox.y),
            (task.yolo_bbox.x + task.yolo_bbox.w, task.yolo_bbox.y + task.yolo_bbox.h),
            GREEN,
            2,
        )
        draw_text(
            annotated,
            f"#{task.display_id} {ready.text} h={task.yolo_bbox.h}px",
            (task.yolo_bbox.x, task.yolo_bbox.y + task.yolo_bbox.h + 18),
            0.55,
            GREEN,
            2,
        )
        cv2.imwrite(str(output_dir / f"event_canvas_{task.display_id:03d}_f{task.frame_num:06d}.png"), annotated)
        cv2.imwrite(str(output_dir / f"event_crop_{task.display_id:03d}_f{task.frame_num:06d}.png"), task.crop)
