from __future__ import annotations

import argparse

from hifive_jetson_py.config import RuntimeConfig
from hifive_jetson_py.edge_service.runtime import EdgeServiceRuntime, EdgeServiceRuntimeOptions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HI-FIVE Jetson realtime YOLO/OCR edge runtime")
    parser.add_argument("--config", default="example_runtime_config.py")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--video", default="", help="Optional MP4 path for demo instead of configured camera source")
    parser.add_argument("--yolo-engine", default="", help="Override YOLO TensorRT engine path")
    parser.add_argument("--ocr-engine", default="", help="Override OCR TensorRT engine path")
    parser.add_argument("--host", default="", help="Override WebTransport ingress host")
    parser.add_argument("--port", type=int, default=0, help="Override WebTransport ingress port")
    parser.add_argument("--standby-host", default="", help="LTE/backup WebTransport ingress host")
    parser.add_argument("--standby-port", type=int, default=0, help="LTE/backup WebTransport ingress port")
    parser.add_argument("--failover-recheck-sec", type=float, default=0.5)
    parser.add_argument("--input-backend", choices=("deepstream", "gstreamer", "opencv"), default="deepstream")
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--display-scale", type=float, default=0.75)
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=0, help="0 means run until source ends")
    parser.add_argument("--height-threshold", type=int, default=20)
    parser.add_argument("--ocr-stable-sec", type=float, default=0.30)
    parser.add_argument("--track-memory-sec", type=float, default=1.0)
    parser.add_argument("--reid-sec", type=float, default=10.0)
    parser.add_argument("--queue-size", type=int, default=8)
    parser.add_argument("--transport-queue-size", type=int, default=128)
    parser.add_argument("--transport-timeout-sec", type=float, default=0.3)
    parser.add_argument("--retry-initial-sec", type=float, default=0.2)
    parser.add_argument("--retry-max-sec", type=float, default=2.0)
    parser.add_argument("--output-dir", default="/home/jetson/hifive/output/edge_service")
    parser.add_argument("--no-save-event-images", action="store_true")
    parser.add_argument("--status-interval-sec", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = RuntimeConfig.from_python_file(args.config)
    if args.check_config:
        print(f"device_id={config.device_id}")
        print(f"cameras={len(config.cameras)}")
        for camera in config.cameras:
            print(
                f"{camera.camera_id}: role={camera.camera_role} "
                f"source_id={camera.source_id} yolo_slots={len(camera.yolo_input_slots)}"
            )
        return

    runtime_options = EdgeServiceRuntimeOptions(
        config_path=args.config,
        camera_index=args.camera_index,
        video_override=args.video,
        host_override=args.host,
        port_override=args.port,
        standby_host_override=args.standby_host,
        standby_port_override=args.standby_port,
        failover_recheck_sec=args.failover_recheck_sec,
        input_backend=args.input_backend,
        display=args.display,
        display_scale=args.display_scale,
        start_sec=args.start_sec,
        frame_limit=args.limit,
        height_threshold=args.height_threshold,
        ocr_stable_sec=args.ocr_stable_sec,
        track_memory_sec=args.track_memory_sec,
        reid_sec=args.reid_sec,
        queue_size=args.queue_size,
        transport_queue_size=args.transport_queue_size,
        transport_timeout_sec=args.transport_timeout_sec,
        retry_initial_sec=args.retry_initial_sec,
        retry_max_sec=args.retry_max_sec,
        yolo_engine_override=args.yolo_engine,
        ocr_engine_override=args.ocr_engine,
        output_dir=args.output_dir,
        save_event_images=not args.no_save_event_images,
        status_interval_sec=args.status_interval_sec,
    )
    EdgeServiceRuntime(runtime_options).run()


if __name__ == "__main__":
    main()
