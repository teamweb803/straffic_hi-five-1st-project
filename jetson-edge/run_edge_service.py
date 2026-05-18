from __future__ import annotations

import argparse

from hifive_jetson_py.edge_service.runtime import EdgeServiceRuntimeOptions
from hifive_jetson_py.edge_service.server import EdgeServiceManager, build_edge_service_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HI-FIVE Jetson always-on edge service")
    parser.add_argument("--config", default="example_runtime_config.py")
    parser.add_argument("--control-host", default="0.0.0.0")
    parser.add_argument("--control-port", type=int, default=8010)
    parser.add_argument("--ingress-host", default="")
    parser.add_argument("--ingress-port", type=int, default=0)
    parser.add_argument("--standby-host", default="")
    parser.add_argument("--standby-port", type=int, default=0)
    parser.add_argument("--failover-recheck-sec", type=float, default=0.5)
    parser.add_argument(
        "--runtime-runner",
        choices=("deepstream-nvinfer", "python-runtime"),
        default="deepstream-nvinfer",
    )
    parser.add_argument("--input-backend", choices=("deepstream", "gstreamer", "opencv"), default="deepstream")
    parser.add_argument("--yolo-engine", default="")
    parser.add_argument("--ocr-engine", default="")
    parser.add_argument("--display-scale", type=float, default=0.75)
    parser.add_argument("--display-sink", choices=("egl", "drm", "3d"), default="egl")
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
    parser.add_argument("--preview-datagram-fps", type=float, default=0.0)
    parser.add_argument("--preview-jpeg-quality", type=int, default=45)
    parser.add_argument("--srt-host", default="")
    parser.add_argument("--srt-port", type=int, default=0)
    parser.add_argument("--srt-bitrate-kbps", type=int, default=2500)
    parser.add_argument("--srt-latency-ms", type=int, default=120)
    parser.add_argument("--srt-iframe-interval", type=int, default=15)
    parser.add_argument("--srt-fps", type=int, default=30)
    parser.add_argument("--srt-width", type=int, default=720)
    parser.add_argument("--srt-height", type=int, default=720)
    parser.add_argument("--evidence-upload", action="store_true")
    parser.add_argument("--evidence-jpeg-quality", type=int, default=85)
    parser.add_argument("--parser-lib", default="/home/jetson/hifive/deepstream_plugins/libnvdsinfer_custom_hifive.so")
    parser.add_argument("--yolo-parser-lib", default="")
    parser.add_argument("--ocr-parser-lib", default="")
    parser.add_argument("--yolo-parser-func", default="NvDsInferParseCustomYoloPlate")
    parser.add_argument("--ocr-parser-func", default="NvDsInferParseCustomCrnnPlate")
    parser.add_argument("--tracker-lib", default="/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so")
    parser.add_argument(
        "--tracker-config",
        default="/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    options = EdgeServiceRuntimeOptions(
        config_path=args.config,
        host_override=args.ingress_host,
        port_override=args.ingress_port,
        standby_host_override=args.standby_host,
        standby_port_override=args.standby_port,
        failover_recheck_sec=args.failover_recheck_sec,
        runtime_runner=args.runtime_runner,
        input_backend=args.input_backend,
        display=False,
        display_scale=args.display_scale,
        display_sink=args.display_sink,
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
        preview_datagram_fps=args.preview_datagram_fps,
        preview_jpeg_quality=args.preview_jpeg_quality,
        srt_host=args.srt_host,
        srt_port=args.srt_port,
        srt_bitrate_kbps=args.srt_bitrate_kbps,
        srt_latency_ms=args.srt_latency_ms,
        srt_iframe_interval=args.srt_iframe_interval,
        srt_fps=args.srt_fps,
        srt_width=args.srt_width,
        srt_height=args.srt_height,
        evidence_upload=args.evidence_upload,
        evidence_jpeg_quality=args.evidence_jpeg_quality,
        parser_lib=args.parser_lib,
        yolo_parser_lib=args.yolo_parser_lib,
        ocr_parser_lib=args.ocr_parser_lib,
        yolo_parser_func=args.yolo_parser_func,
        ocr_parser_func=args.ocr_parser_func,
        tracker_lib=args.tracker_lib,
        tracker_config=args.tracker_config,
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
