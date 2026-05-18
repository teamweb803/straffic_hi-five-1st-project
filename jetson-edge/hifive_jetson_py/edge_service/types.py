from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from hifive_jetson_py.models import BBox
from hifive_jetson_py.shared_crop_ipc import SharedPlateCropTask


@dataclass(frozen=True)
class DetectionSnapshot:
    frame_num: int
    original_bbox: BBox
    yolo_bbox: BBox
    confidence: float
    timestamp_ns: int
    lane_no: int
    global_lane_no: int


@dataclass
class PlateTrack:
    track_id: str
    display_id: int
    bbox: BBox
    yolo_bbox: BBox
    lane_no: int
    global_lane_no: int
    confidence: float
    first_seen_frame: int
    last_seen_frame: int
    last_seen_monotonic: float
    visible: bool = True
    event_sent: bool = False
    pending_ocr: bool = False
    live_text: str = ""
    live_confidence: float = 0.0
    live_valid: bool = False
    stable_text: str = ""
    stable_confidence: float = 0.0
    candidate_text: str = ""
    candidate_started_at: float = 0.0


@dataclass(frozen=True)
class OcrTask:
    track_id: str
    display_id: int
    source_id: int
    frame_num: int
    bbox: BBox
    yolo_bbox: BBox
    lane_no: int
    global_lane_no: int
    confidence: float
    timestamp_ns: int
    crop: Any | None
    readable: bool
    canvas_snapshot: Any | None = None
    shared_crop: SharedPlateCropTask | None = None


@dataclass(frozen=True)
class ReadyPlateEvent:
    task: OcrTask
    text: str
    confidence: float


@dataclass
class SharedState:
    lock: threading.Lock
    stop_event: threading.Event
    latest_yolo_ms: float = 0.0
    latest_ocr_ms: float = 0.0
    latest_fps: float = 0.0
    processed_frames: int = 0
    processed_ocr_tasks: int = 0
    yolo_detections: int = 0
    sent_events: int = 0
    dropped_ocr_tasks: int = 0
    status_send_ok: int = 0
    status_send_fail: int = 0
    last_status_send_ms: int = 0
    last_error: str = ""
