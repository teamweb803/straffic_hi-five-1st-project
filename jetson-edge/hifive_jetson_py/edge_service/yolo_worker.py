from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field

from hifive_jetson_py.config import CameraConfig
from hifive_jetson_py.lane_yolo_input import TwoLaneYoloInputComposer
from hifive_jetson_py.models import BBox, YoloDetection, YoloInputDetection
from hifive_jetson_py.shared_crop_ipc import SharedPlateCropWriter

from .ocr_worker import put_latest_ocr_task
from .plate_tracker import PlateBBoxTracker
from .types import DetectionSnapshot, OcrTask, PlateTrack, SharedState


@dataclass
class YoloFrameResult:
    canvas: object
    tracks: list[PlateTrack]
    yolo_ms: float
    detection_count: int


@dataclass
class YoloWorker:
    camera: CameraConfig
    yolo_runner: object
    tracker: PlateBBoxTracker
    ocr_queue: queue.Queue[OcrTask]
    shared: SharedState
    height_threshold: int
    crop_writer: SharedPlateCropWriter = field(default_factory=SharedPlateCropWriter)

    def __post_init__(self) -> None:
        self.composer = TwoLaneYoloInputComposer(self.camera)

    def process_frame(self, frame_bgr, frame_num: int, timestamp_ns: int) -> YoloFrameResult:
        canvas = self.composer.compose(frame_bgr)
        start = time.perf_counter()
        yolo_results = self._normalize_results(self.yolo_runner.infer(canvas))
        yolo_ms = (time.perf_counter() - start) * 1000.0

        snapshots: list[DetectionSnapshot] = []
        for yolo_result in yolo_results:
            restored = self.composer.restore_bbox(yolo_result.bbox)
            if restored is None:
                continue
            original_bbox, lane_no, global_lane_no = restored
            snapshots.append(
                DetectionSnapshot(
                    frame_num=frame_num,
                    original_bbox=original_bbox,
                    yolo_bbox=yolo_result.bbox,
                    confidence=yolo_result.confidence,
                    timestamp_ns=timestamp_ns,
                    lane_no=lane_no,
                    global_lane_no=global_lane_no,
                )
            )

        assigned_tracks = self.tracker.update(snapshots, frame_num)
        for track, snapshot in zip(assigned_tracks, snapshots):
            if snapshot.yolo_bbox.h < self.height_threshold:
                self._clear_unreadable_track(track)
                continue
            shared_crop = self.crop_writer.write_from_frame(
                frame_bgr,
                YoloDetection(
                    source_id=self.camera.source_id,
                    frame_num=frame_num,
                    local_track_id=track.track_id,
                    bbox=snapshot.original_bbox,
                    confidence=snapshot.confidence,
                    timestamp_ns=timestamp_ns,
                    lane_no=snapshot.lane_no,
                    global_lane_no=snapshot.global_lane_no,
                ),
            )
            if shared_crop is None:
                continue
            task = OcrTask(
                track_id=track.track_id,
                display_id=track.display_id,
                source_id=self.camera.source_id,
                frame_num=frame_num,
                bbox=snapshot.original_bbox,
                yolo_bbox=snapshot.yolo_bbox,
                lane_no=snapshot.lane_no,
                global_lane_no=snapshot.global_lane_no,
                confidence=snapshot.confidence,
                timestamp_ns=timestamp_ns,
                crop=None,
                readable=snapshot.yolo_bbox.h >= self.height_threshold,
                canvas_snapshot=canvas.copy(),
                shared_crop=shared_crop,
            )
            put_latest_ocr_task(self.ocr_queue, self.shared, track.track_id, self.tracker, task)

        with self.shared.lock:
            self.shared.latest_yolo_ms = yolo_ms
            self.shared.yolo_detections += len(snapshots)
        return YoloFrameResult(canvas=canvas, tracks=assigned_tracks, yolo_ms=yolo_ms, detection_count=len(snapshots))

    def _clear_unreadable_track(self, track: PlateTrack) -> None:
        with self.shared.lock:
            track.pending_ocr = False
            track.live_text = ""
            track.live_confidence = 0.0
            track.live_valid = False
            track.candidate_text = ""
            track.candidate_started_at = 0.0

    def _normalize_results(self, results) -> list[YoloInputDetection]:
        normalized: list[YoloInputDetection] = []
        for result in results:
            if isinstance(result, BBox):
                normalized.append(YoloInputDetection(bbox=result, confidence=1.0))
            else:
                normalized.append(result)
        return normalized
