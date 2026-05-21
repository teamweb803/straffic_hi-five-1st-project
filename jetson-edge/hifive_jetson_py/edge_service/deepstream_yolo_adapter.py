from __future__ import annotations

from dataclasses import dataclass, field
import queue

from hifive_jetson_py.config import CameraConfig
from hifive_jetson_py.lane_yolo_input import TwoLaneYoloInputComposer
from hifive_jetson_py.models import YoloDetection, YoloInputDetection
from hifive_jetson_py.shared_crop_ipc import SharedPlateCropWriter

from .ocr_worker import put_latest_ocr_task
from .plate_tracker import PlateBBoxTracker
from .types import DetectionSnapshot, OcrTask, PlateTrack, SharedState


@dataclass
class DeepStreamYoloAdapter:
    camera: CameraConfig
    tracker: PlateBBoxTracker
    ocr_queue: queue.Queue[OcrTask]
    shared: SharedState
    height_threshold: int
    crop_writer: SharedPlateCropWriter = field(default_factory=SharedPlateCropWriter)

    def __post_init__(self) -> None:
        self.composer = TwoLaneYoloInputComposer(self.camera)

    def process_yolo_frame(
        self,
        canvas_bgr,
        frame_num: int,
        timestamp_ns: int,
        detections: list[YoloInputDetection],
    ) -> list[PlateTrack]:
        snapshots = self._snapshots_from_detections(detections, frame_num, timestamp_ns)
        assigned_tracks = self.tracker.update(snapshots, frame_num)
        if not snapshots:
            return assigned_tracks

        if canvas_bgr is None:
            with self.shared.lock:
                self.shared.dropped_ocr_tasks += len(snapshots)
                self.shared.last_error = "DeepStream frame surface unavailable for OCR crop"
            return assigned_tracks

        for track, snapshot in zip(assigned_tracks, snapshots):
            if snapshot.yolo_bbox.h < self.height_threshold:
                self._clear_unreadable_track(track)
                continue

            shared_crop = self.crop_writer.write_from_frame(
                canvas_bgr,
                YoloDetection(
                    source_id=self.camera.source_id,
                    frame_num=frame_num,
                    local_track_id=track.track_id,
                    bbox=snapshot.yolo_bbox,
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
                canvas_snapshot=canvas_bgr.copy(),
                shared_crop=shared_crop,
            )
            put_latest_ocr_task(self.ocr_queue, self.shared, track.track_id, self.tracker, task)

        with self.shared.lock:
            self.shared.yolo_detections += len(snapshots)
        return assigned_tracks

    def _snapshots_from_detections(
        self,
        detections: list[YoloInputDetection],
        frame_num: int,
        timestamp_ns: int,
    ) -> list[DetectionSnapshot]:
        snapshots: list[DetectionSnapshot] = []
        for detection in detections:
            restored = self.composer.restore_bbox(detection.bbox)
            if restored is None:
                continue
            original_bbox, lane_no, global_lane_no = restored
            snapshots.append(
                DetectionSnapshot(
                    frame_num=frame_num,
                    original_bbox=original_bbox,
                    yolo_bbox=detection.bbox,
                    confidence=detection.confidence,
                    timestamp_ns=timestamp_ns,
                    lane_no=lane_no,
                    global_lane_no=global_lane_no,
                )
            )
        return snapshots

    def _clear_unreadable_track(self, track: PlateTrack) -> None:
        with self.shared.lock:
            track.pending_ocr = False
            track.live_text = ""
            track.live_confidence = 0.0
            track.live_valid = False
            track.candidate_text = ""
            track.candidate_started_at = 0.0
            track.candidate_confidence = 0.0
            track.candidate_task = None
