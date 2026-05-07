from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
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
from hifive_jetson_py.models import YoloDetection  # noqa: E402
from hifive_jetson_py.ocr_tensorrt import TensorRtOcrRunner  # noqa: E402
from hifive_jetson_py.protobuf_codec import PassageEventCodec  # noqa: E402
from hifive_jetson_py.simple_tracker import SimpleBBoxTracker  # noqa: E402
from hifive_jetson_py.spool import FileSpool  # noqa: E402
from hifive_jetson_py.webtransport_transport import WebTransportIngressSender  # noqa: E402
from hifive_jetson_py.yolo_tensorrt import TensorRtYoloRunner  # noqa: E402
from jetson_pre_yolo_video_smoke import open_capture  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MP4 -> YOLO -> OCR -> WebTransport ingress smoke test")
    parser.add_argument("--video", default="/home/jetson/hifive/videos/IMG_4806.mp4")
    parser.add_argument("--config", default="/home/jetson/hifive/app/example_runtime_config.py")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--path", default="/hifive/edge")
    parser.add_argument("--server-name", default="")
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0, help="0 means run until the video ends")
    parser.add_argument("--max-events", type=int, default=0, help="0 means no event cap")
    parser.add_argument("--emit-min-seen-frames", type=int, default=3)
    parser.add_argument("--emit-after-stable-frames", type=int, default=8)
    parser.add_argument("--emit-after-missing-frames", type=int, default=30)
    parser.add_argument("--min-plate-width", type=int, default=0)
    parser.add_argument("--min-plate-height", type=int, default=0)
    parser.add_argument("--min-ocr-confidence", type=float, default=0.70)
    parser.add_argument("--send-invalid", action="store_true")
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--display-scale", type=float, default=0.75)
    parser.add_argument("--display-delay-ms", type=int, default=1)
    parser.add_argument("--save-yolo-every", type=int, default=0)
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    parser.add_argument("--spool-dir", default="/home/jetson/hifive/spool/video_yolo_ocr_smoke")
    parser.add_argument("--output-dir", default="/home/jetson/hifive/logs/video_yolo_ocr_smoke")
    return parser.parse_args()


@dataclass
class TrackBest:
    track_id: str
    lane_no: int
    global_lane_no: int
    best_bbox: object
    best_yolo_bbox: object
    best_crop: object
    best_frame: object
    best_canvas: object
    best_confidence: float
    best_quality: float
    best_frame_num: int
    best_updated_frame: int
    last_seen_frame: int
    seen_count: int = 1
    emitted: bool = False


def build_event(config: RuntimeConfig, camera, frame_num: int, detection, plate_text: str, plate_conf: float) -> tuple[str, dict]:
    event_id = f"video-smoke-{time.time_ns()}-{frame_num:06d}-{detection.bbox.x}-{detection.bbox.y}"
    event = {
        "event_id": event_id,
        "device_id": config.device_id,
        "camera_id": camera.camera_id,
        "camera_group_id": camera.camera_group_id,
        "camera_role": camera.camera_role,
        "lane_no": detection.lane_no,
        "global_lane_no": detection.global_lane_no,
        "local_track_id": detection.local_track_id,
        "vehicle_pass_id": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000+00:00", time.gmtime()),
        "direction": camera.direction,
        "vehicle_confidence": detection.confidence,
        "plate": {
            "text": plate_text,
            "confidence": plate_conf,
            "candidate_count": 1 if plate_text else 0,
            "agreement_ratio": 1.0 if plate_text else 0.0,
        },
        "plate_bbox": detection.bbox.to_dict(),
        "needs_review": not bool(plate_text),
        "review_reason": "" if plate_text else "empty_ocr_result",
        "payload_format": "protobuf",
        "schema_version": config.schema_version,
    }
    return event_id, event


def crop_bbox(frame, bbox):
    clipped = bbox.clipped(frame.shape[1], frame.shape[0])
    if clipped.w <= 0 or clipped.h <= 0:
        return None
    return frame[clipped.y : clipped.y + clipped.h, clipped.x : clipped.x + clipped.w].copy()


def should_keep_ocr_result(decoded, min_confidence: float, send_invalid: bool) -> bool:
    if not decoded.text and not send_invalid:
        return False
    if decoded.confidence < min_confidence:
        return False
    if not send_invalid and not decoded.valid_pattern:
        return False
    return True


def detection_quality(bbox, confidence: float) -> float:
    return float(bbox.w * bbox.h) * float(confidence)


def draw_detection(frame, bbox, label: str, color=(0, 255, 0)):
    cv2.rectangle(frame, (bbox.x, bbox.y), (bbox.x + bbox.w, bbox.y + bbox.h), color, 2)
    cv2.putText(
        frame,
        label,
        (bbox.x, max(20, bbox.y - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )


def save_debug_triplet(
    output_dir: Path,
    prefix: str,
    index: int,
    frame_num: int,
    canvas,
    yolo_bbox,
    frame,
    bbox,
    crop,
    label: str,
) -> tuple[Path, Path, Path]:
    yolo_path = output_dir / f"{prefix}_yolo_canvas_{index:03d}_f{frame_num:06d}.png"
    original_path = output_dir / f"{prefix}_original_bbox_{index:03d}_f{frame_num:06d}.png"
    crop_path = output_dir / f"{prefix}_crop_{index:03d}_f{frame_num:06d}.png"

    canvas_annotated = canvas.copy()
    draw_detection(canvas_annotated, yolo_bbox, label)
    original_annotated = frame.copy()
    draw_detection(original_annotated, bbox, label)

    cv2.imwrite(str(yolo_path), canvas_annotated)
    cv2.imwrite(str(original_path), original_annotated)
    cv2.imwrite(str(crop_path), crop)
    return yolo_path, original_path, crop_path


def maybe_show(window_name: str, frame, scale: float, delay_ms: int) -> bool:
    if scale != 1.0:
        frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imshow(window_name, frame)
    key = cv2.waitKey(max(1, delay_ms)) & 0xFF
    return key not in (ord("q"), 27)


def seek_video(cap, pending_frame, start_frame: int, start_sec: float):
    if start_frame <= 0 and start_sec <= 0:
        return 0, pending_frame

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    target_frame = start_frame
    if target_frame <= 0 and fps > 0:
        target_frame = int(round(start_sec * fps))
    if target_frame <= 0:
        return 0, pending_frame

    if cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame):
        return target_frame, None

    skipped = 0
    pending_frame = None
    while skipped < target_frame:
        ok, _ = cap.read()
        if not ok:
            break
        skipped += 1
    return skipped, pending_frame


def main() -> None:
    args = parse_args()
    config = RuntimeConfig.from_python_file(args.config)
    camera = config.cameras[args.camera_index]
    composer = TwoLaneYoloInputComposer(camera)
    tracker = SimpleBBoxTracker()
    yolo = TensorRtYoloRunner(
        engine_path=config.yolo.engine_path,
        confidence_threshold=config.yolo.confidence_threshold,
        input_width=config.yolo.input_width,
        input_height=config.yolo.input_height,
    )
    ocr = TensorRtOcrRunner(engine_path=config.ocr.engine_path, vocab_path=config.ocr.vocab_path)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    spool = FileSpool(args.spool_dir)
    sender = WebTransportIngressSender(
        host=args.host,
        port=args.port,
        path=args.path,
        server_name=args.server_name or args.host,
        verify_tls=False,
        timeout_sec=args.timeout_sec,
        spool=spool,
        retry_enabled=False,
    )
    codec = PassageEventCodec(schema_version=config.schema_version)

    cap, open_mode, pending_frame = open_capture(args.video)
    print(f"video={args.video}")
    print(f"open_mode={open_mode}")
    print(f"camera={camera.camera_id} role={camera.camera_role}")
    print(f"yolo_engine={config.yolo.engine_path}")
    print(f"ocr_engine={config.ocr.engine_path}")
    frames, pending_frame = seek_video(cap, pending_frame, args.start_frame, args.start_sec)
    if frames > 0:
        print(f"start_frame={frames}")

    processed_frames = 0
    events = 0
    total_detections = 0
    ocr_attempts = 0
    skipped_small = 0
    skipped_ocr = 0
    track_states: dict[str, TrackBest] = {}
    yolo_ms_values: list[float] = []
    ocr_ms_values: list[float] = []
    send_ms_values: list[float] = []

    min_plate_width = args.min_plate_width or config.ocr.min_crop_width
    min_plate_height = args.min_plate_height or config.ocr.min_crop_height

    while (args.limit <= 0 or processed_frames < args.limit) and (args.max_events <= 0 or events < args.max_events):
        if pending_frame is not None:
            frame = pending_frame
            pending_frame = None
        else:
            ok, frame = cap.read()
            if not ok:
                break

        canvas = composer.compose(frame)
        yolo_start = time.perf_counter()
        yolo_results = yolo.infer(canvas)
        yolo_ms = (time.perf_counter() - yolo_start) * 1000.0
        yolo_ms_values.append(yolo_ms)

        raw_detections: list[YoloDetection] = []
        yolo_bbox_by_raw_key = {}
        for yolo_result in yolo_results:
            restored = composer.restore_bbox(yolo_result.bbox)
            if restored is None:
                continue
            bbox, lane_no, global_lane_no = restored
            raw_detection = YoloDetection(
                source_id=camera.source_id,
                frame_num=frames,
                local_track_id="",
                bbox=bbox,
                confidence=yolo_result.confidence,
                timestamp_ns=time.time_ns(),
                lane_no=lane_no,
                global_lane_no=global_lane_no,
            )
            raw_detections.append(raw_detection)
            yolo_bbox_by_raw_key[(bbox.x, bbox.y, bbox.w, bbox.h, lane_no)] = yolo_result.bbox

        detections = tracker.assign(camera.camera_id, raw_detections, frames)
        display_frame = frame.copy()
        for detection in detections:
            total_detections += 1
            draw_detection(
                display_frame,
                detection.bbox,
                f"{detection.local_track_id} {detection.confidence:.2f}",
            )

            key = (
                detection.bbox.x,
                detection.bbox.y,
                detection.bbox.w,
                detection.bbox.h,
                detection.lane_no,
            )
            yolo_bbox = yolo_bbox_by_raw_key.get(key)
            if yolo_bbox is None:
                yolo_bbox = detection.bbox

            if detection.bbox.w < min_plate_width or detection.bbox.h < min_plate_height:
                skipped_small += 1
                continue

            crop = crop_bbox(frame, detection.bbox)
            if crop is None:
                continue

            quality = detection_quality(detection.bbox, detection.confidence)
            state = track_states.get(detection.local_track_id)
            if state is None:
                track_states[detection.local_track_id] = TrackBest(
                    track_id=detection.local_track_id,
                    lane_no=detection.lane_no,
                    global_lane_no=detection.global_lane_no,
                    best_bbox=detection.bbox,
                    best_yolo_bbox=yolo_bbox,
                    best_crop=crop,
                    best_frame=frame.copy(),
                    best_canvas=canvas.copy(),
                    best_confidence=detection.confidence,
                    best_quality=quality,
                    best_frame_num=frames,
                    best_updated_frame=frames,
                    last_seen_frame=frames,
                )
                continue

            state.last_seen_frame = frames
            state.seen_count += 1
            if quality > state.best_quality:
                state.lane_no = detection.lane_no
                state.global_lane_no = detection.global_lane_no
                state.best_bbox = detection.bbox
                state.best_yolo_bbox = yolo_bbox
                state.best_crop = crop
                state.best_frame = frame.copy()
                state.best_canvas = canvas.copy()
                state.best_confidence = detection.confidence
                state.best_quality = quality
                state.best_frame_num = frames
                state.best_updated_frame = frames

        emit_track_ids = []
        for track_id, state in track_states.items():
            if state.emitted:
                continue
            missing_ready = frames - state.last_seen_frame >= args.emit_after_missing_frames
            stable_ready = (
                state.seen_count >= args.emit_min_seen_frames
                and frames - state.best_updated_frame >= args.emit_after_stable_frames
            )
            if missing_ready or stable_ready:
                emit_track_ids.append(track_id)

        for track_id in emit_track_ids:
            state = track_states[track_id]
            ocr_start = time.perf_counter()
            decoded = ocr.predict_crop(state.best_crop)
            ocr_ms = (time.perf_counter() - ocr_start) * 1000.0
            ocr_ms_values.append(ocr_ms)
            ocr_attempts += 1

            if not should_keep_ocr_result(decoded, args.min_ocr_confidence, args.send_invalid):
                skipped_ocr += 1
                state.emitted = True
                continue

            best_detection = YoloDetection(
                source_id=camera.source_id,
                frame_num=state.best_frame_num,
                local_track_id=state.track_id,
                bbox=state.best_bbox,
                confidence=state.best_confidence,
                timestamp_ns=time.time_ns(),
                lane_no=state.lane_no,
                global_lane_no=state.global_lane_no,
            )
            event_id, event = build_event(
                config,
                camera,
                state.best_frame_num,
                best_detection,
                decoded.text,
                decoded.confidence,
            )
            payload = codec.encode(event)
            send_start = time.perf_counter()
            accepted = sender.submit(payload, event_id)
            send_ms = (time.perf_counter() - send_start) * 1000.0
            send_ms_values.append(send_ms)

            event_index = events + 1
            yolo_path, original_path, crop_path = save_debug_triplet(
                output_dir,
                "event",
                event_index,
                state.best_frame_num,
                state.best_canvas,
                state.best_yolo_bbox,
                state.best_frame,
                state.best_bbox,
                state.best_crop,
                f"{state.track_id} {decoded.text or 'EMPTY'} {state.best_confidence:.2f}",
            )
            print(
                f"event={event_index} frame={state.best_frame_num} lane={state.lane_no} "
                f"track={state.track_id} seen={state.seen_count} "
                f"bbox=({state.best_bbox.x},{state.best_bbox.y},{state.best_bbox.w},{state.best_bbox.h}) "
                f"yolo_conf={state.best_confidence:.4f} plate={decoded.text} "
                f"ocr_conf={decoded.confidence:.4f} valid={decoded.valid_pattern} "
                f"yolo_ms={yolo_ms:.2f} ocr_ms={ocr_ms:.2f} send_ms={send_ms:.2f} "
                f"accepted={accepted} yolo={yolo_path} original={original_path} crop={crop_path}"
            )
            events += 1
            state.emitted = True
            if args.max_events > 0 and events >= args.max_events:
                break

        if args.save_yolo_every > 0 and processed_frames % args.save_yolo_every == 0:
            cv2.imwrite(str(output_dir / f"live_yolo_f{frames:06d}.png"), display_frame)

        if args.display:
            if not maybe_show("HI-FIVE YOLO tracking", display_frame, args.display_scale, args.display_delay_ms):
                break

        frames += 1
        processed_frames += 1

    for track_id, state in list(track_states.items()):
        if state.emitted:
            continue
        if args.max_events > 0 and events >= args.max_events:
            break
        ocr_start = time.perf_counter()
        decoded = ocr.predict_crop(state.best_crop)
        ocr_ms = (time.perf_counter() - ocr_start) * 1000.0
        ocr_ms_values.append(ocr_ms)
        ocr_attempts += 1
        if not should_keep_ocr_result(decoded, args.min_ocr_confidence, args.send_invalid):
            skipped_ocr += 1
            state.emitted = True
            continue
        best_detection = YoloDetection(
            source_id=camera.source_id,
            frame_num=state.best_frame_num,
            local_track_id=state.track_id,
            bbox=state.best_bbox,
            confidence=state.best_confidence,
            timestamp_ns=time.time_ns(),
            lane_no=state.lane_no,
            global_lane_no=state.global_lane_no,
        )
        event_id, event = build_event(config, camera, state.best_frame_num, best_detection, decoded.text, decoded.confidence)
        payload = codec.encode(event)
        send_start = time.perf_counter()
        accepted = sender.submit(payload, event_id)
        send_ms = (time.perf_counter() - send_start) * 1000.0
        send_ms_values.append(send_ms)
        event_index = events + 1
        yolo_path, original_path, crop_path = save_debug_triplet(
            output_dir,
            "event",
            event_index,
            state.best_frame_num,
            state.best_canvas,
            state.best_yolo_bbox,
            state.best_frame,
            state.best_bbox,
            state.best_crop,
            f"{state.track_id} {decoded.text or 'EMPTY'} {state.best_confidence:.2f}",
        )
        print(
            f"event={event_index} frame={state.best_frame_num} lane={state.lane_no} "
            f"track={state.track_id} seen={state.seen_count} "
            f"bbox=({state.best_bbox.x},{state.best_bbox.y},{state.best_bbox.w},{state.best_bbox.h}) "
            f"yolo_conf={state.best_confidence:.4f} plate={decoded.text} "
            f"ocr_conf={decoded.confidence:.4f} valid={decoded.valid_pattern} "
            f"ocr_ms={ocr_ms:.2f} send_ms={send_ms:.2f} "
            f"accepted={accepted} yolo={yolo_path} original={original_path} crop={crop_path}"
        )
        events += 1
        state.emitted = True

    cap.release()
    if args.display:
        cv2.destroyAllWindows()
    yolo_avg = sum(yolo_ms_values) / len(yolo_ms_values) if yolo_ms_values else 0.0
    ocr_avg = sum(ocr_ms_values) / len(ocr_ms_values) if ocr_ms_values else 0.0
    send_avg = sum(send_ms_values) / len(send_ms_values) if send_ms_values else 0.0
    print(
        f"summary start_frame={frames - processed_frames} processed_frames={processed_frames} "
        f"last_frame={frames} events={events} spool_count={spool.count()} "
        f"yolo_detections={total_detections} ocr_attempts={ocr_attempts} "
        f"skipped_small={skipped_small} skipped_ocr={skipped_ocr} "
        f"yolo_avg_ms={yolo_avg:.2f} ocr_avg_ms={ocr_avg:.2f} send_avg_ms={send_avg:.2f}"
    )


if __name__ == "__main__":
    main()
