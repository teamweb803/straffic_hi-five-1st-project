from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    w: int
    h: int
    unit: str = "pixel"
    coord: str = "original_frame"

    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    def clipped(self, frame_w: int, frame_h: int) -> "BBox":
        x1 = max(0, min(frame_w, self.x))
        y1 = max(0, min(frame_h, self.y))
        x2 = max(0, min(frame_w, self.x + self.w))
        y2 = max(0, min(frame_h, self.y + self.h))
        return BBox(x=x1, y=y1, w=max(0, x2 - x1), h=max(0, y2 - y1), unit=self.unit, coord=self.coord)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlateObservation:
    source_id: int
    frame_num: int
    local_track_id: str
    bbox: BBox
    vehicle_confidence: float
    plate_text: str
    plate_confidence: float
    timestamp_ns: int


@dataclass(frozen=True)
class YoloDetection:
    source_id: int
    frame_num: int
    local_track_id: str
    bbox: BBox
    confidence: float
    timestamp_ns: int
    lane_no: int = 0
    global_lane_no: int = 0


@dataclass(frozen=True)
class YoloInputDetection:
    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class OcrCandidate:
    text: str
    confidence: float
    valid_pattern: bool
    review_reason: str | None = None


@dataclass(frozen=True)
class PlateDecision:
    text: str
    confidence: float
    valid_pattern: bool
    needs_review: bool
    review_reason: str
    candidate_count: int
    agreement_ratio: float
    raw_candidates: list[dict[str, Any]] = field(default_factory=list)
