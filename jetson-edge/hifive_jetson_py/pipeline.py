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
    _emitted_tracks: set[str] = field(default_factory=set)

    def handle_observation(self, observation: PlateObservation) -> None:
        camera = self.config.camera_by_source_id(observation.source_id)
        if camera is None:
            print(f"drop observation from unknown source_id={observation.source_id}")
            return

        lane = lane_for_bbox(camera, observation.bbox)
        reject_reason = reject_small_plate(
            observation.bbox,
            min_w=self.config.ocr.min_crop_width,
            min_h=self.config.ocr.min_crop_height,
        )
        if reject_reason:
            if observation.local_track_id in self._emitted_tracks:
                return
            decision = PlateDecision("", 0.0, False, True, reject_reason, 0, 0.0)
            self.builder.build_and_submit(
                observation,
                lane_no=lane.lane_no,
                global_lane_no=lane.global_lane_no,
                decision=decision,
                forced_review_reason=reject_reason,
            )
            self._emitted_tracks.add(observation.local_track_id)
            return

        if observation.plate_text:
            self.candidate_buffer.add(
                observation.local_track_id,
                observation.plate_text,
                observation.plate_confidence,
            )

        if observation.local_track_id in self._emitted_tracks:
            return

        decision = self.candidate_buffer.decide(observation.local_track_id)
        if not observation.plate_text and decision.candidate_count == 0:
            decision = PlateDecision("", 0.0, False, True, "missing_ocr_metadata", 0, 0.0)

        if decision.candidate_count < self.candidate_buffer.min_candidates and valid_korean_plate(observation.plate_text):
            return

        self.builder.build_and_submit(
            observation,
            lane_no=lane.lane_no,
            global_lane_no=lane.global_lane_no,
            decision=decision,
        )
        self._emitted_tracks.add(observation.local_track_id)
        self.candidate_buffer.clear(observation.local_track_id)
