"""YOLO/OCR 모듈로부터 수신하는 데이터의 Pydantic 스키마.

YOLO 담당이 FastAPI 로 POST /v1/yolo/detections 호출 시 사용한다.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class VehicleTypeEnum(str, Enum):
    UNKNOWN = "unknown"
    PASSENGER = "passenger"
    VAN = "van"
    TRUCK = "truck"
    BUS = "bus"
    SPECIAL = "special"
    MOTORCYCLE = "motorcycle"


class BoundingBox(BaseModel):
    """이미지 내 차량 bbox (픽셀 기준)."""
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0


class GpsTelemetry(BaseModel):
    gps_device_id: str | None = None
    plate_number: str | None = None
    edge_node_id: str | None = None
    lane_id: str | None = None
    track_id: int | None = None
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: float = 0.0
    altitude_m: float | None = None
    accuracy_m: float | None = None
    provider: str | None = None
    captured_at: datetime


class YoloDetection(BaseModel):
    """YOLO 한 프레임 1개 트랙의 검출 결과."""
    track_id: int = Field(..., ge=0)
    lane_id: str
    frame_index: int = Field(..., ge=0)
    captured_at: datetime
    bbox: BoundingBox
    vehicle_type: VehicleTypeEnum = VehicleTypeEnum.UNKNOWN
    vehicle_type_confidence: float = Field(0.0, ge=0.0, le=1.0)

    # OCR 결과 (번호판 ROI 처리 후)
    plate_text: Optional[str] = None
    plate_confidence: float = Field(0.0, ge=0.0, le=1.0)
    plate_roi_jpeg_b64: Optional[str] = Field(
        default=None,
        description="검수용 base64 인코딩 JPEG. None 이면 첨부 안 함.",
    )

    gps: Optional[GpsTelemetry] = None

    @field_validator("plate_text")
    @classmethod
    def strip_plate(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v


class YoloBatch(BaseModel):
    """한 번의 추론 사이클에서 검출된 트랙 묶음."""
    edge_node_id: Optional[str] = None
    detections: list[YoloDetection]
