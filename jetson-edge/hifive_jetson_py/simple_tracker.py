from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from .models import BBox, YoloDetection


@dataclass
class TrackState:
    track_id: str
    bbox: BBox
    lane_no: int
    last_frame_num: int


class SimpleBBoxTracker:
    def __init__(self, iou_threshold: float = 0.30, max_age_frames: int = 10) -> None:
        self.iou_threshold = iou_threshold
        self.max_age_frames = max_age_frames
        self._seq = count(1)
        self._tracks: dict[str, TrackState] = {}

    def assign(
        self,
        camera_id: str,
        detections: list[YoloDetection],
        frame_num: int,
    ) -> list[YoloDetection]:
        self._drop_stale(frame_num)
        assigned: list[YoloDetection] = []
        used_tracks: set[str] = set()
        for detection in detections:
            track = self._best_track(detection, used_tracks)
            if track is None:
                track_id = f"{camera_id}-trk-{next(self._seq):06d}"
                track = TrackState(
                    track_id=track_id,
                    bbox=detection.bbox,
                    lane_no=detection.lane_no,
                    last_frame_num=frame_num,
                )
                self._tracks[track_id] = track
            else:
                track.bbox = detection.bbox
                track.lane_no = detection.lane_no
                track.last_frame_num = frame_num
            used_tracks.add(track.track_id)
            assigned.append(
                YoloDetection(
                    source_id=detection.source_id,
                    frame_num=detection.frame_num,
                    local_track_id=track.track_id,
                    bbox=detection.bbox,
                    confidence=detection.confidence,
                    timestamp_ns=detection.timestamp_ns,
                    lane_no=detection.lane_no,
                    global_lane_no=detection.global_lane_no,
                )
            )
        return assigned

    def _best_track(self, detection: YoloDetection, used_tracks: set[str]) -> TrackState | None:
        best: TrackState | None = None
        best_iou = 0.0
        for track in self._tracks.values():
            if track.track_id in used_tracks or track.lane_no != detection.lane_no:
                continue
            score = bbox_iou(track.bbox, detection.bbox)
            if score > best_iou:
                best = track
                best_iou = score
        if best is None or best_iou < self.iou_threshold:
            return None
        return best

    def _drop_stale(self, frame_num: int) -> None:
        stale = [
            track_id
            for track_id, track in self._tracks.items()
            if frame_num - track.last_frame_num > self.max_age_frames
        ]
        for track_id in stale:
            self._tracks.pop(track_id, None)


def bbox_iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a.x, a.y, a.x + a.w, a.y + a.h
    bx1, by1, bx2, by2 = b.x, b.y, b.x + b.w, b.y + b.h
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0
    union = a.w * a.h + b.w * b.h - intersection
    return intersection / max(1, union)
