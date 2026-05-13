from __future__ import annotations

from dataclasses import dataclass, field

from .config import RuntimeConfig
from .event_builder import PassageEventBuilder
from .geometry import lane_for_bbox, reject_small_plate
from .models import PlateDecision, PlateObservation
from .ocr_rules import OcrCandidateBuffer, valid_korean_plate


@dataclass
class PlateEventProcessor:
    config: RuntimeConfig
    builder: PassageEventBuilder
    candidate_buffer: OcrCandidateBuffer = field(default_factory=lambda: OcrCandidateBuffer(min_candidates=2))
    missing_ocr_observation_threshold: int = 8
    _emitted_tracks: set[str] = field(default_factory=set)
    _missing_ocr_counts: dict[str, int] = field(default_factory=dict)

    def handle_observation(self, observation: PlateObservation) -> bool:
        camera = self.config.camera_by_source_id(observation.source_id)
        if camera is None:
            print(f"drop observation from unknown source_id={observation.source_id}")
            return False

        lane = lane_for_bbox(camera, observation.bbox)
        reject_reason = reject_small_plate(
            observation.bbox,
            min_w=self.config.ocr.min_crop_width,
            min_h=self.config.ocr.min_crop_height,
        )
        if reject_reason:
            if observation.local_track_id in self._emitted_tracks:
                return False
            decision = PlateDecision("", 0.0, False, True, reject_reason, 0, 0.0)
            self.builder.build_and_submit(
                observation,
                lane_no=lane.lane_no,
                global_lane_no=lane.global_lane_no,
                decision=decision,
                forced_review_reason=reject_reason,
            )
            self._emitted_tracks.add(observation.local_track_id)
            return True

        if observation.plate_text:
            self._missing_ocr_counts.pop(observation.local_track_id, None)
            self.candidate_buffer.add(
                observation.local_track_id,
                observation.plate_text,
                observation.plate_confidence,
            )

        if observation.local_track_id in self._emitted_tracks:
            return False

        decision = self.candidate_buffer.decide(observation.local_track_id)
        if not observation.plate_text and decision.candidate_count == 0:
            count = self._missing_ocr_counts.get(observation.local_track_id, 0) + 1
            self._missing_ocr_counts[observation.local_track_id] = count
            if count < self.missing_ocr_observation_threshold:
                return False
            decision = PlateDecision("", 0.0, False, True, "missing_ocr_metadata", 0, 0.0)

        if decision.candidate_count < self.candidate_buffer.min_candidates and valid_korean_plate(observation.plate_text):
            return False

        self.builder.build_and_submit(
            observation,
            lane_no=lane.lane_no,
            global_lane_no=lane.global_lane_no,
            decision=decision,
        )
        self._emitted_tracks.add(observation.local_track_id)
        self.candidate_buffer.clear(observation.local_track_id)
        self._missing_ocr_counts.pop(observation.local_track_id, None)
        return True
