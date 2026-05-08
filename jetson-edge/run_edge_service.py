from __future__ import annotations

import argparse

from hifive_jetson_py.edge_service.runtime import EdgeServiceRuntimeOptions
from hifive_jetson_py.edge_service.server import EdgeServiceManager, build_edge_service_app


DEFAULT_YOLO_ENGINE = "/home/jetson/hifive/models/yolo11s_fp16.engine"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HI-FIVE Jetson always-on edge service")
    parser.add_argument("--config", default="example_runtime_config.py")
    parser.add_argument("--control-host", default="0.0.0.0")
    parser.add_argument("--control-port", type=int, default=8010)
    parser.add_argument("--ingress-host", default="")
    parser.add_argument("--ingress-port", type=int, default=0)
    parser.add_argument("--yolo-engine", default=DEFAULT_YOLO_ENGINE)
    parser.add_argument("--ocr-engine", default="")
    parser.add_argument("--display-scale", type=float, default=0.75)
    parser.add_argument("--height-threshold", type=int, default=20)
    parser.add_argument("--ocr-stable-sec", type=float, default=0.30)
    parser.add_argument("--track-memory-sec", type=float, default=1.0)
    parser.add_argument("--reid-sec", type=float, default=10.0)
    parser.add_argument("--queue-size", type=int, default=8)
    parser.add_argument("--transport-queue-size", type=int, default=128)
    parser.add_argument("--transport-timeout-sec", type=float, default=1.0)
    parser.add_argument("--retry-initial-sec", type=float, default=0.2)
    parser.add_argument("--retry-max-sec", type=float, default=2.0)
    parser.add_argument("--output-dir", default="/home/jetson/hifive/output/edge_service")
    parser.add_argument("--no-save-event-images", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    options = EdgeServiceRuntimeOptions(
        config_path=args.config,
        host_override=args.ingress_host,
        port_override=args.ingress_port,
        display=False,
        display_scale=args.display_scale,
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
    )
    manager = EdgeServiceManager(options)

    import uvicorn

    print(f"edge_service_control=http://{args.control_host}:{args.control_port}")
    uvicorn.run(
        build_edge_service_app(manager),
        host=args.control_host,
        port=args.control_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
