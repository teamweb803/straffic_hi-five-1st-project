from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2


def _add_import_roots() -> None:
    root = Path(__file__).resolve().parent
    candidates = (root, root / "jetson_python_runtime_py")
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))


_add_import_roots()

from hifive_jetson_py.config import RuntimeConfig  # noqa: E402
from hifive_jetson_py.lane_yolo_input import TwoLaneYoloInputComposer  # noqa: E402
from hifive_jetson_py.yolo_tensorrt import TensorRtYoloRunner  # noqa: E402
from jetson_pre_yolo_video_smoke import open_capture  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MP4 to TensorRT YOLO smoke test")
    parser.add_argument("--video", default="/home/jetson/hifive/videos/IMG_4806.mp4")
    parser.add_argument("--config", default="/home/jetson/hifive/app/example_runtime_config.py")
    parser.add_argument("--engine", default="")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--save-every", type=int, default=30)
    parser.add_argument("--output-dir", default="/home/jetson/hifive/logs/yolo_engine_smoke")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = RuntimeConfig.from_python_file(args.config)
    camera = config.cameras[args.camera_index]
    composer = TwoLaneYoloInputComposer(camera)
    engine_path = args.engine or config.yolo.engine_path
    yolo = TensorRtYoloRunner(
        engine_path=engine_path,
        confidence_threshold=config.yolo.confidence_threshold,
        input_width=config.yolo.input_width,
        input_height=config.yolo.input_height,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap, open_mode, pending_frame = open_capture(args.video)
    print(f"video={args.video}")
    print(f"open_mode={open_mode}")
    print(f"engine={engine_path}")
    print(f"camera={camera.camera_id} role={camera.camera_role}")

    read_frames = 0
    total_detections = 0
    infer_ms_values: list[float] = []
    while read_frames < args.limit:
        if pending_frame is not None:
            frame = pending_frame
            pending_frame = None
        else:
            ok, frame = cap.read()
            if not ok:
                break

        canvas = composer.compose(frame)
        start = time.perf_counter()
        detections = yolo.infer(canvas)
        infer_ms = (time.perf_counter() - start) * 1000.0
        infer_ms_values.append(infer_ms)
        total_detections += len(detections)

        if read_frames % args.save_every == 0:
            annotated = canvas.copy()
            for detection in detections:
                b = detection.bbox
                cv2.rectangle(annotated, (b.x, b.y), (b.x + b.w, b.y + b.h), (0, 255, 0), 2)
                cv2.putText(
                    annotated,
                    f"{detection.confidence:.2f}",
                    (b.x, max(20, b.y - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
            out = output_dir / f"yolo_{read_frames:06d}.jpg"
            cv2.imwrite(str(out), annotated)
            print(
                f"frame={read_frames} detections={len(detections)} "
                f"infer_ms={infer_ms:.2f} saved={out}"
            )

        read_frames += 1

    cap.release()
    avg_ms = sum(infer_ms_values) / len(infer_ms_values) if infer_ms_values else 0.0
    min_ms = min(infer_ms_values) if infer_ms_values else 0.0
    max_ms = max(infer_ms_values) if infer_ms_values else 0.0
    print(
        f"summary frames={read_frames} detections={total_detections} "
        f"infer_avg_ms={avg_ms:.2f} infer_min_ms={min_ms:.2f} infer_max_ms={max_ms:.2f}"
    )


if __name__ == "__main__":
    main()
