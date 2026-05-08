from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from queue import Empty, Full
from typing import Any, Protocol

from .config import CameraConfig
from .lane_yolo_input import TwoLaneYoloInputComposer
from .models import BBox, PlateObservation, YoloDetection, YoloInputDetection
from .shared_crop_ipc import SharedPlateCropTask, SharedPlateCropWriter, open_shared_plate_crop
from .simple_tracker import SimpleBBoxTracker


class YoloRunner(Protocol):
    def infer(self, yolo_input_bgr: Any) -> list[YoloInputDetection | BBox]:
        ...


class OcrRunner(Protocol):
    def predict_crop(self, crop_bgr: Any):
        ...


@dataclass
class YoloLoop:
    camera: CameraConfig
    yolo_runner: YoloRunner
    ocr_queue: Any
    crop_writer: SharedPlateCropWriter = field(default_factory=SharedPlateCropWriter)
    tracker: SimpleBBoxTracker = field(default_factory=SimpleBBoxTracker)

    def __post_init__(self) -> None:
        self.composer = TwoLaneYoloInputComposer(self.camera)

    def process_frame(self, frame_bgr: Any, frame_num: int, timestamp_ns: int) -> int:
        yolo_input = self.composer.compose(frame_bgr)
        yolo_results = self._normalize_yolo_results(self.yolo_runner.infer(yolo_input))
        detections: list[YoloDetection] = []
        for yolo_result in yolo_results:
            restored = self.composer.restore_bbox(yolo_result.bbox)
            if restored is None:
                continue
            original_bbox, lane_no, global_lane_no = restored
            detections.append(
                YoloDetection(
                    source_id=self.camera.source_id,
                    frame_num=frame_num,
                    local_track_id="",
                    bbox=original_bbox,
                    confidence=yolo_result.confidence,
                    timestamp_ns=timestamp_ns,
                    lane_no=lane_no,
                    global_lane_no=global_lane_no,
                )
            )

        pushed = 0
        for detection in self.tracker.assign(self.camera.camera_id, detections, frame_num):
            task = self.crop_writer.write_from_frame(frame_bgr, detection)
            if task is None:
                continue
            try:
                self.ocr_queue.put_nowait(task)
            except Full:
                self.crop_writer.discard(task)
                continue
            pushed += 1
        return pushed

    def _normalize_yolo_results(self, results: list[YoloInputDetection | BBox]) -> list[YoloInputDetection]:
        normalized: list[YoloInputDetection] = []
        for result in results:
            if isinstance(result, BBox):
                normalized.append(YoloInputDetection(bbox=result, confidence=1.0))
            else:
                normalized.append(result)
        return normalized


@dataclass
class OcrLoop:
    ocr_runner: OcrRunner
    on_observation: Callable[[PlateObservation], None]
    input_queue: Any
    timeout_sec: float = 0.1

    def run_forever(self) -> None:
        while True:
            self.process_once()

    def process_once(self) -> bool:
        try:
            task: SharedPlateCropTask = self.input_queue.get(timeout=self.timeout_sec)
        except Empty:
            return False
        with open_shared_plate_crop(task, unlink=True) as crop_bgr:
            result = self.ocr_runner.predict_crop(crop_bgr)
        observation = PlateObservation(
            source_id=task.source_id,
            frame_num=task.frame_num,
            local_track_id=task.local_track_id,
            bbox=task.bbox,
            vehicle_confidence=task.vehicle_confidence,
            plate_text=str(result.text),
            plate_confidence=float(result.confidence),
            timestamp_ns=task.timestamp_ns,
        )
        self.on_observation(observation)
        return True
