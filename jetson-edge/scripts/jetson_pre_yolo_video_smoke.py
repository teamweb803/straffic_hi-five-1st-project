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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MP4 to 960x960 pre-YOLO canvas smoke test")
    parser.add_argument("--video", default="/home/jetson/hifive/videos/IMG_4806.mp4")
    parser.add_argument("--config", default="/home/jetson/hifive/app/example_runtime_config.py")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--save-every", type=int, default=30)
    parser.add_argument("--output-dir", default="/home/jetson/hifive/logs/pre_yolo_smoke")
    return parser.parse_args()


def open_capture(video_arg: str):
    if video_arg.startswith(("file://", "rtsp://", "http://", "https://")):
        attempts = [
            ("gstreamer-uri", lambda: cv2.VideoCapture(video_arg, cv2.CAP_GSTREAMER)),
            ("default-uri", lambda: cv2.VideoCapture(video_arg)),
        ]
    else:
        path = Path(video_arg).expanduser()
        if not path.exists():
            raise RuntimeError(f"video file not found: {path}")
        resolved = path.resolve()
        file_uri = resolved.as_uri()
        gst_decodebin = (
            f"uridecodebin uri={file_uri} ! "
            "videoconvert ! video/x-raw,format=BGR ! appsink drop=1 sync=false"
        )
        attempts = [
            ("default-path", lambda: cv2.VideoCapture(str(resolved))),
            ("ffmpeg-path", lambda: cv2.VideoCapture(str(resolved), cv2.CAP_FFMPEG)),
            ("gstreamer-uri", lambda: cv2.VideoCapture(file_uri, cv2.CAP_GSTREAMER)),
            ("gstreamer-pipeline", lambda: cv2.VideoCapture(gst_decodebin, cv2.CAP_GSTREAMER)),
        ]

    errors: list[str] = []
    for name, factory in attempts:
        cap = factory()
        if not cap.isOpened():
            errors.append(f"{name}: open failed")
            cap.release()
            continue
        ok, first_frame = cap.read()
        if ok:
            return cap, name, first_frame
        errors.append(f"{name}: first read failed")
        cap.release()

    raise RuntimeError(f"cannot open video: {video_arg}; attempts={errors}")


def main() -> None:
    args = parse_args()
    config = RuntimeConfig.from_python_file(args.config)
    camera = config.cameras[args.camera_index]
    composer = TwoLaneYoloInputComposer(camera)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap, open_mode, pending_frame = open_capture(args.video)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        height, width = pending_frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"video={args.video}")
    print(f"open_mode={open_mode}")
    print(f"metadata width={width} height={height} fps={fps:.2f} frames={frame_count}")
    print(f"camera={camera.camera_id} role={camera.camera_role}")
    for slot in camera.yolo_input_slots:
        print(
            "slot "
            f"lane={slot.lane_no} source={slot.source_rect} canvas={slot.canvas_rect}"
        )

    if width != camera.frame_width or height != camera.frame_height:
        raise RuntimeError(
            f"video shape {width}x{height} does not match config "
            f"{camera.frame_width}x{camera.frame_height}"
        )

    compose_ms: list[float] = []
    read_frames = 0
    saved = 0
    total_start = time.perf_counter()
    while read_frames < args.limit:
        if pending_frame is not None:
            frame = pending_frame
            pending_frame = None
        else:
            ok, frame = cap.read()
            if not ok:
                break

        start = time.perf_counter()
        canvas = composer.compose(frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        compose_ms.append(elapsed_ms)

        if canvas.shape != (960, 960, 3):
            raise RuntimeError(f"bad canvas shape: {canvas.shape}")

        if args.save_every > 0 and read_frames % args.save_every == 0:
            out = output_dir / f"pre_yolo_{read_frames:06d}.jpg"
            cv2.imwrite(str(out), canvas)
            print(f"frame={read_frames} canvas={canvas.shape} compose_ms={elapsed_ms:.2f} saved={out}")
            saved += 1

        read_frames += 1

    cap.release()
    total_ms = (time.perf_counter() - total_start) * 1000.0
    avg_ms = sum(compose_ms) / len(compose_ms) if compose_ms else 0.0
    min_ms = min(compose_ms) if compose_ms else 0.0
    max_ms = max(compose_ms) if compose_ms else 0.0
    print(
        f"summary frames={read_frames} saved={saved} "
        f"compose_avg_ms={avg_ms:.2f} compose_min_ms={min_ms:.2f} "
        f"compose_max_ms={max_ms:.2f} total_ms={total_ms:.2f}"
    )


if __name__ == "__main__":
    main()
