from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
import time

from .config import RuntimeConfig
from .models import BBox, PlateDecision, PlateObservation
from .protobuf_codec import PassageEventCodec
from .transport import Sender


_SEQ = count(1)


@dataclass
class PassageEventBuilder:
    config: RuntimeConfig
    codec: PassageEventCodec
    sender: Sender

    def build_and_submit(
        self,
        observation: PlateObservation,
        lane_no: int,
        global_lane_no: int,
        decision: PlateDecision,
        forced_review_reason: str | None = None,
    ) -> dict:
        camera = self.config.camera_by_source_id(observation.source_id)
        if camera is None:
            raise RuntimeError(f"unknown source_id={observation.source_id}")

        review_reason = forced_review_reason or decision.review_reason
        needs_review = bool(forced_review_reason or decision.needs_review)
        event_id = self._event_id(camera.camera_id, observation.local_track_id)
        event = {
            "event_id": event_id,
            "device_id": self.config.device_id,
            "camera_id": camera.camera_id,
            "camera_group_id": camera.camera_group_id,
            "camera_role": camera.camera_role,
            "lane_no": lane_no,
            "global_lane_no": global_lane_no,
            "local_track_id": observation.local_track_id,
            "vehicle_pass_id": "",
            "timestamp": self._timestamp(observation.timestamp_ns),
            "direction": camera.direction,
            "vehicle_confidence": observation.vehicle_confidence,
            "plate": {
                "text": decision.text,
                "confidence": decision.confidence,
                "candidate_count": decision.candidate_count,
                "agreement_ratio": decision.agreement_ratio,
            },
            "plate_bbox": observation.bbox.to_dict(),
            "needs_review": needs_review,
            "review_reason": review_reason or "",
            "payload_format": "protobuf",
            "schema_version": self.config.schema_version,
        }
        payload = self.codec.encode(event)
        self.sender.submit(payload, event_id)
        return event

    def _event_id(self, camera_id: str, local_track_id: str) -> str:
        seq = next(_SEQ)
        return f"{self.config.device_id}-{camera_id}-{int(time.time_ns())}-{local_track_id}-{seq:06d}"

    def _timestamp(self, timestamp_ns: int) -> str:
        if timestamp_ns <= 0:
            return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, timezone.utc).isoformat(timespec="milliseconds")
