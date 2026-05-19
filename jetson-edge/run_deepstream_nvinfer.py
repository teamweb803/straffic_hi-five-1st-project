from __future__ import annotations

import argparse
import os
import queue
import threading
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse, unquote

from hifive_jetson_py.config import RuntimeConfig
from hifive_jetson_py.deepstream_nvinfer_pipeline import (
    DeepStreamNvinferOptions,
    build_deepstream_nvinfer_artifacts,
)
from hifive_jetson_py.deepstream_runtime import DeepStreamRuntime
from hifive_jetson_py.event_builder import PassageEventBuilder
from hifive_jetson_py.ocr_tensorrt import TensorRtOcrRunner
from hifive_jetson_py.protobuf_codec import PassageEventCodec
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.transport import build_sender
from hifive_jetson_py.edge_service.deepstream_yolo_adapter import DeepStreamYoloAdapter
from hifive_jetson_py.edge_service.display import GREEN, draw_text
from hifive_jetson_py.edge_service.evidence_sender import EvidenceFrameSender
from hifive_jetson_py.edge_service.event_dispatcher import EventDispatcher
from hifive_jetson_py.edge_service.ocr_worker import OcrWorker
from hifive_jetson_py.edge_service.plate_tracker import PlateBBoxTracker
from hifive_jetson_py.edge_service.preview_datagram import PreviewFrameSender
from hifive_jetson_py.edge_service.status_sender import EdgeStatusSender
from hifive_jetson_py.edge_service.types import OcrTask, ReadyPlateEvent, SharedState


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HI-FIVE DeepStream nvinfer YOLO + parallel OCR runtime")
    parser.add_argument("--config", default="example_runtime_config.py")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--source", default="", help="MP4 path, file:// URI, RTSP URI, or /dev/video*")
    parser.add_argument("--host", default="", help="Override WebTransport ingress host")
    parser.add_argument("--port", type=int, default=0, help="Override WebTransport ingress port")
    parser.add_argument("--standby-host", default="", help="LTE/backup WebTransport ingress host")
    parser.add_argument("--standby-port", type=int, default=0)
    parser.add_argument("--failover-recheck-sec", type=float, default=0.5)
    parser.add_argument("--transport-timeout-sec", type=float, default=0.3)
    parser.add_argument("--retry-initial-sec", type=float, default=0.2)
    parser.add_argument("--retry-max-sec", type=float, default=2.0)
    parser.add_argument("--yolo-engine", default="")
    parser.add_argument("--ocr-engine", default="")
    parser.add_argument(
        "--parser-lib",
        default="/home/jetson/hifive/deepstream_plugins/libnvdsinfer_custom_hifive.so",
        help="Custom DeepStream parser .so used by nvinfer YOLO",
    )
    parser.add_argument("--yolo-parser-lib", default="")
    parser.add_argument("--ocr-parser-lib", default="", help="Deprecated: OCR runs in the Python TensorRT worker")
    parser.add_argument("--yolo-parser-func", default="NvDsInferParseCustomYoloPlate")
    parser.add_argument("--ocr-parser-func", default="", help="Deprecated: OCR runs in the Python TensorRT worker")
    parser.add_argument("--tracker-lib", default="", help="Deprecated: tracking runs in PlateBBoxTracker")
    parser.add_argument("--tracker-config", default="", help="Deprecated: tracking runs in PlateBBoxTracker")
    parser.add_argument("--output-dir", default="/home/jetson/hifive/output/deepstream")
    parser.add_argument("--height-threshold", type=int, default=20)
    parser.add_argument("--ocr-stable-sec", type=float, default=0.30)
    parser.add_argument("--track-memory-sec", type=float, default=1.0)
    parser.add_argument("--reid-sec", type=float, default=10.0)
    parser.add_argument("--queue-size", type=int, default=8)
    parser.add_argument("--transport-queue-size", type=int, default=128)
    parser.add_argument("--status-interval-sec", type=float, default=1.0)
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--display-scale", type=float, default=0.75, help="Deprecated: DeepStream display uses native sink")
    parser.add_argument("--display-sink", choices=("egl", "drm", "3d"), default="egl")
    parser.add_argument("--srt-host", default="", help="Enable H264/SRT output to this Ingress host")
    parser.add_argument("--srt-port", type=int, default=0)
    parser.add_argument("--srt-bitrate-kbps", type=int, default=2500)
    parser.add_argument("--srt-latency-ms", type=int, default=120)
    parser.add_argument("--srt-iframe-interval", type=int, default=15)
    parser.add_argument("--srt-fps", type=int, default=30)
    parser.add_argument("--srt-width", type=int, default=720)
    parser.add_argument("--srt-height", type=int, default=720)
    parser.add_argument("--srt-encoder", choices=("x264", "openh264"), default="x264")
    parser.add_argument("--preview-datagram-fps", type=float, default=0.0)
    parser.add_argument("--preview-jpeg-quality", type=int, default=45)
    parser.add_argument("--evidence-upload", action="store_true")
    parser.add_argument("--evidence-jpeg-quality", type=int, default=85)
    parser.add_argument("--repeat", action="store_true", help="Repeat finite video source until stopped")
    parser.add_argument("--repeat-delay-sec", type=float, default=0.2)
    parser.add_argument("--no-save-event-images", action="store_true")
    parser.add_argument("--print-pipeline", action="store_true")
    parser.add_argument("--dry-run-build", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = RuntimeConfig.from_python_file(args.config)
    if not config.cameras:
        raise RuntimeError("at least one camera is required")
    camera = config.cameras[args.camera_index]

    transport = config.transport
    if args.host:
        transport = replace(transport, ingress_host=args.host)
    if args.port > 0:
        transport = replace(transport, ingress_port=args.port)
    if args.standby_host:
        transport = replace(transport, failover_enabled=True, standby_ingress_host=args.standby_host)
    if args.standby_port > 0:
        transport = replace(transport, standby_ingress_port=args.standby_port)
    if args.failover_recheck_sec > 0:
        transport = replace(transport, failover_recheck_sec=args.failover_recheck_sec)
    if args.transport_timeout_sec > 0:
        transport = replace(transport, timeout_sec=args.transport_timeout_sec)
    if args.retry_initial_sec > 0:
        transport = replace(transport, retry_initial_sec=args.retry_initial_sec)
    if args.retry_max_sec > 0:
        transport = replace(transport, retry_max_sec=args.retry_max_sec)
    config = replace(config, transport=transport)
    if args.yolo_engine:
        config = replace(config, yolo=replace(config.yolo, engine_path=args.yolo_engine))
    if args.ocr_engine:
        config = replace(config, ocr=replace(config.ocr, engine_path=args.ocr_engine))

    _require_file(config.ocr.engine_path, "OCR engine")
    _require_file(config.ocr.vocab_path, "OCR vocab")
    artifacts = build_deepstream_nvinfer_artifacts(
        config,
        camera,
        DeepStreamNvinferOptions(
            output_dir=Path(args.output_dir),
            source_override=args.source,
            yolo_parser_library_path=args.yolo_parser_lib or args.parser_lib,
            yolo_parser_function=args.yolo_parser_func,
            display=args.display,
            display_sink=args.display_sink,
            srt_host=args.srt_host,
            srt_port=args.srt_port,
            srt_bitrate_kbps=args.srt_bitrate_kbps,
            srt_latency_ms=args.srt_latency_ms,
            srt_iframe_interval=args.srt_iframe_interval,
            srt_fps=args.srt_fps,
            srt_width=args.srt_width,
            srt_height=args.srt_height,
            srt_encoder=args.srt_encoder,
        ),
    )
    config = replace(config, pipeline_text=artifacts.pipeline_text, probe_element_name="post_yolo_probe")
    os.environ.setdefault("HIFIVE_OCR_VOCAB", config.ocr.vocab_path)
    if args.print_pipeline:
        print(config.pipeline_text)
    print(f"deepstream_yolo_config={artifacts.yolo_config_path}")
    print(f"ocr_worker_engine={config.ocr.engine_path}")
    if args.dry_run_build:
        return

    codec = PassageEventCodec(schema_version=config.schema_version)
    spool = FileSpool(config.spool_dir)
    sender = build_sender(config.transport, spool)
    builder = PassageEventBuilder(config=config, codec=codec, sender=sender)
    stop_event = threading.Event()
    shared = SharedState(lock=threading.Lock(), stop_event=stop_event)
    started_at_ms = int(time.time() * 1000)
    last_frame_at = time.perf_counter()

    if args.status_interval_sec > 0:
        EdgeStatusSender(
            config=config,
            camera=camera,
            sender=sender,
            shared=shared,
            spool=spool,
            output_dir=Path(args.output_dir),
            interval_sec=args.status_interval_sec,
            source_mode="video" if args.source else "camera",
            source_value=args.source or camera.source_uri,
            started_at_ms=started_at_ms,
        ).start()

    source_fps = _source_fps(args.source or camera.source_uri)
    tracker = PlateBBoxTracker(
        fps=source_fps,
        memory_sec=args.track_memory_sec,
        reid_sec=args.reid_sec,
    )
    ocr_queue: queue.Queue[OcrTask] = queue.Queue(maxsize=args.queue_size)
    event_queue: queue.Queue[ReadyPlateEvent] = queue.Queue()
    OcrWorker(
        ocr_runner=TensorRtOcrRunner(config.ocr.engine_path, config.ocr.vocab_path),
        tracker=tracker,
        input_queue=ocr_queue,
        event_queue=event_queue,
        shared=shared,
        stable_sec=args.ocr_stable_sec,
        min_confidence=config.ocr.confidence_threshold,
    ).start()
    adapter = DeepStreamYoloAdapter(
        camera=camera,
        tracker=tracker,
        ocr_queue=ocr_queue,
        shared=shared,
        height_threshold=args.height_threshold,
    )
    dispatcher = EventDispatcher(
        config=config,
        builder=builder,
        shared=shared,
        queue_size=args.transport_queue_size,
        evidence_sender=EvidenceFrameSender(sender, args.evidence_jpeg_quality) if args.evidence_upload else None,
    )
    preview_sender = None
    if args.preview_datagram_fps > 0:
        preview_sender = PreviewFrameSender(
            sender=sender,
            device_id=config.device_id,
            camera_id=camera.camera_id,
            fps=args.preview_datagram_fps,
            jpeg_quality=args.preview_jpeg_quality,
        )
    output_dir = Path(args.output_dir)
    if not args.no_save_event_images:
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"deepstream_nvinfer=started camera={camera.camera_id} source_fps={source_fps:.3f}")
    print(f"yolo_engine={config.yolo.engine_path}")
    print(f"ocr_engine={config.ocr.engine_path}")
    print(f"transport={config.transport.kind} host={config.transport.ingress_host} port={config.transport.ingress_port}")
    print(f"srt_output={'enabled' if args.srt_host and args.srt_port > 0 else 'disabled'} host={args.srt_host} port={args.srt_port} fps={args.srt_fps} size={args.srt_width}x{args.srt_height} encoder={args.srt_encoder}")
    print(f"edge_status_interval_sec={args.status_interval_sec}")
    print(f"repeat_video={args.repeat}")
    print(f"evidence_upload={args.evidence_upload}")

    def on_frame(frame_num: int) -> None:
        nonlocal last_frame_at
        now = time.perf_counter()
        dt = max(1e-6, now - last_frame_at)
        last_frame_at = now
        with shared.lock:
            instant_fps = 1.0 / dt
            shared.latest_fps = instant_fps if shared.latest_fps <= 0 else shared.latest_fps * 0.85 + instant_fps * 0.15
            shared.processed_frames = max(shared.processed_frames + 1, frame_num + 1)

    runtime_error = False

    def on_error(detail: str) -> None:
        nonlocal runtime_error
        runtime_error = True
        with shared.lock:
            shared.last_error = detail

    def on_yolo_frame(canvas_bgr, frame_num: int, timestamp_ns: int, detections):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        tracks = adapter.process_yolo_frame(canvas_bgr, frame_num, timestamp_ns, detections)
        with shared.lock:
            shared.latest_yolo_ms = (time.perf_counter() - start) * 1000.0
        if preview_sender is not None:
            preview_sender.maybe_send(
                canvas_bgr,
                list(tracker.tracks.values()),
                shared,
                args.height_threshold,
                frame_num,
            )
        _drain_events(
            event_queue=event_queue,
            dispatcher=dispatcher,
            output_dir=output_dir,
            save_images=not args.no_save_event_images,
        )
        return tracks

    try:
        cycle = 0
        while not stop_event.is_set():
            runtime_error = False
            last_frame_at = time.perf_counter()
            if cycle > 0:
                tracker.reset()
                with shared.lock:
                    shared.latest_yolo_ms = 0.0
                    shared.latest_ocr_ms = 0.0
                    shared.yolo_detections = 0
            DeepStreamRuntime(
                config=config,
                on_yolo_frame=on_yolo_frame,
                on_frame=on_frame,
                on_error=on_error,
                shared=shared,
                height_threshold=args.height_threshold,
                always_extract_frame=args.preview_datagram_fps > 0,
            ).run()
            for _ in range(20):
                _drain_events(
                    event_queue=event_queue,
                    dispatcher=dispatcher,
                    output_dir=output_dir,
                    save_images=not args.no_save_event_images,
                )
                if getattr(ocr_queue, "unfinished_tasks", 0) == 0 and event_queue.empty():
                    break
                time.sleep(0.05)
            if runtime_error or not args.repeat or not args.source:
                break
            cycle += 1
            if args.repeat_delay_sec > 0:
                time.sleep(args.repeat_delay_sec)
            print(f"deepstream_nvinfer=repeat cycle={cycle} source={args.source}")
    finally:
        for _ in range(20):
            _drain_events(
                event_queue=event_queue,
                dispatcher=dispatcher,
                output_dir=output_dir,
                save_images=not args.no_save_event_images,
            )
            if getattr(ocr_queue, "unfinished_tasks", 0) == 0 and event_queue.empty():
                break
            time.sleep(0.05)
        stop_event.set()
        _drain_events(
            event_queue=event_queue,
            dispatcher=dispatcher,
            output_dir=output_dir,
            save_images=not args.no_save_event_images,
        )
        dispatcher.drain()


def _drain_events(
    *,
    event_queue: queue.Queue[ReadyPlateEvent],
    dispatcher: EventDispatcher,
    output_dir: Path,
    save_images: bool,
) -> None:
    while True:
        try:
            ready = event_queue.get_nowait()
        except queue.Empty:
            return
        dispatcher.submit(ready)
        if save_images:
            _save_event_images(output_dir, ready)
        print(
            f"event track=#{ready.task.display_id} lane={ready.task.lane_no} "
            f"plate={ready.text} conf={ready.confidence:.4f} frame={ready.task.frame_num}"
        )


def _save_event_images(output_dir: Path, ready: ReadyPlateEvent) -> None:
    import cv2

    task = ready.task
    if task.canvas_snapshot is None or task.crop is None:
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


def _source_fps(source: str) -> float:
    if not source or source.startswith("/dev/video"):
        return 30.0
    source_path = source
    if source.startswith("file://"):
        source_path = unquote(urlparse(source).path)
    if "://" in source_path:
        return 30.0
    try:
        import cv2

        cap = cv2.VideoCapture(source_path)
        try:
            fps = float(cap.get(5) or 0.0)
        finally:
            cap.release()
        if fps > 0:
            return fps
    except Exception:
        pass
    return 30.0


def _require_file(path: str, label: str) -> None:
    if not path:
        raise RuntimeError(f"{label} path is required")
    if not Path(path).exists():
        raise RuntimeError(f"{label} not found: {path}")


if __name__ == "__main__":
    main()
