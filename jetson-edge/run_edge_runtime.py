from __future__ import annotations

import argparse

from hifive_jetson_py.config import RuntimeConfig
from hifive_jetson_py.event_builder import PassageEventBuilder
from hifive_jetson_py.jetson_parallel_runtime import JetsonParallelRuntime
from hifive_jetson_py.pipeline import PlateEventProcessor
from hifive_jetson_py.protobuf_codec import PassageEventCodec
from hifive_jetson_py.ocr_tensorrt import TensorRtOcrRunner
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.transport import build_sender
from hifive_jetson_py.yolo_tensorrt import TensorRtYoloRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HI-FIVE Jetson Python parallel YOLO/OCR runtime")
    parser.add_argument("--config", default="example_runtime_config.py")
    parser.add_argument("--check-config", action="store_true")
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

    codec = PassageEventCodec(schema_version=config.schema_version)
    spool = FileSpool(config.spool_dir)
    sender = build_sender(config.transport, spool)
    builder = PassageEventBuilder(config=config, codec=codec, sender=sender)
    processor = PlateEventProcessor(config=config, builder=builder)
    runtime = JetsonParallelRuntime(
        config=config,
        yolo_runner_factory=lambda camera: TensorRtYoloRunner(
            engine_path=config.yolo.engine_path,
            confidence_threshold=config.yolo.confidence_threshold,
            input_width=config.yolo.input_width,
            input_height=config.yolo.input_height,
        ),
        ocr_runner=TensorRtOcrRunner(
            engine_path=config.ocr.engine_path,
            vocab_path=config.ocr.vocab_path,
        ),
        on_observation=processor.handle_observation,
    )
    runtime.run()


if __name__ == "__main__":
    main()
