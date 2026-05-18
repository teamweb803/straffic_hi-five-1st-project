from __future__ import annotations

import time

from hifive_jetson_py.models import BBox

from .types import DetectionSnapshot, PlateTrack


LANE_BAND_HEIGHT = 480
YOLO_CANVAS_WIDTH = 960


class PlateBBoxTracker:
    def __init__(self, fps: float, memory_sec: float, reid_sec: float) -> None:
        self.memory_frames = max(1, int(round(memory_sec * fps)))
        self.reid_frames = max(self.memory_frames, int(round(reid_sec * fps)))
        self.tracks: dict[str, PlateTrack] = {}
        self.ocr_memory: dict[str, tuple[int, int]] = {}
        self._next_id = 1
        self._next_display_id = 1

    def reset(self) -> None:
        self.tracks.clear()
        self.ocr_memory.clear()
        self._next_id = 1
        self._next_display_id = 1

    def update(self, detections: list[DetectionSnapshot], frame_num: int) -> list[PlateTrack]:
        for track in self.tracks.values():
            track.visible = False

        assigned: list[PlateTrack] = []
        used_track_ids: set[str] = set()
        now = time.monotonic()
        for detection in detections:
            track = self._match(detection, frame_num, used_track_ids)
            if track is None:
                track = self._create_track(detection, frame_num, now)
            else:
                track.bbox = detection.original_bbox
                track.yolo_bbox = detection.yolo_bbox
                track.lane_no = detection.lane_no
                track.global_lane_no = detection.global_lane_no
                track.confidence = detection.confidence
                track.last_seen_frame = frame_num
                track.last_seen_monotonic = now
                track.visible = True
            used_track_ids.add(track.track_id)
            assigned.append(track)

        self._drop_expired(frame_num)
        self._drop_ocr_memory(frame_num)
        return assigned

    def remember_ocr(self, display_id: int, text: str, frame_num: int) -> None:
        if display_id > 0 and text:
            self.ocr_memory[text] = (display_id, frame_num)

    def ensure_display_id(self, track: PlateTrack) -> int:
        if track.display_id <= 0:
            track.display_id = self._next_display_id
            self._next_display_id += 1
        return track.display_id

    def restore_display_id_by_ocr(self, track: PlateTrack, text: str, frame_num: int) -> bool:
        if not text:
            return False
        remembered = self.ocr_memory.get(text)
        if remembered is None:
            return False
        display_id, last_frame = remembered
        if frame_num - last_frame <= self.reid_frames:
            track.display_id = display_id
            return True
        return False

    def _create_track(self, detection: DetectionSnapshot, frame_num: int, now: float) -> PlateTrack:
        track_id = f"trk-{self._next_id:06d}"
        track = PlateTrack(
            track_id=track_id,
            display_id=0,
            bbox=detection.original_bbox,
            yolo_bbox=detection.yolo_bbox,
            lane_no=detection.lane_no,
            global_lane_no=detection.global_lane_no,
            confidence=detection.confidence,
            first_seen_frame=frame_num,
            last_seen_frame=frame_num,
            last_seen_monotonic=now,
        )
        self.tracks[track_id] = track
        self._next_id += 1
        return track

    def _match(
        self,
        detection: DetectionSnapshot,
        frame_num: int,
        used_track_ids: set[str],
    ) -> PlateTrack | None:
        best_track: PlateTrack | None = None
        best_score = -1.0
        for track in self.tracks.values():
            if track.track_id in used_track_ids:
                continue
            age = frame_num - track.last_seen_frame
            if age > self.memory_frames:
                continue
            score = track_match_score(track, detection, age, self.memory_frames)
            if score > best_score:
                best_score = score
                best_track = track
        if best_track is None or best_score < 0.0:
            return None
        return best_track

    def _drop_expired(self, frame_num: int) -> None:
        stale = [
            track_id
            for track_id, track in self.tracks.items()
            if frame_num - track.last_seen_frame > self.reid_frames
        ]
        for track_id in stale:
            self.tracks.pop(track_id, None)

    def _drop_ocr_memory(self, frame_num: int) -> None:
        stale = [
            text
            for text, (_, last_frame) in self.ocr_memory.items()
            if frame_num - last_frame > self.reid_frames
        ]
        for text in stale:
            self.ocr_memory.pop(text, None)


def track_match_score(track: PlateTrack, detection: DetectionSnapshot, age_frames: int, memory_frames: int) -> float:
    yolo_score = plate_match_score(track.yolo_bbox, detection.yolo_bbox, age_frames, memory_frames)
    original_score = plate_match_score(track.bbox, detection.original_bbox, age_frames, memory_frames)
    score = max(yolo_score, original_score + 0.15)
    if track.stable_text:
        score = max(score, lane_wrap_match_score(track.yolo_bbox, detection.yolo_bbox, age_frames, memory_frames))
        score += 0.25
    return score


def lane_wrap_match_score(previous: BBox, current: BBox, age_frames: int, memory_frames: int) -> float:
    wrap_memory_frames = max(3, min(memory_frames, memory_frames // 2))
    if age_frames > wrap_memory_frames:
        return -1.0

    px, py = previous.center()
    cx, cy = current.center()
    previous_lane_band = int(py // LANE_BAND_HEIGHT)
    current_lane_band = int(cy // LANE_BAND_HEIGHT)
    if previous_lane_band != 0 or current_lane_band != 1:
        return -1.0

    edge_zone = YOLO_CANVAS_WIDTH * 0.35
    previous_right = px >= YOLO_CANVAS_WIDTH - edge_zone
    current_left = cx <= edge_zone
    if not (previous_right and current_left):
        return -1.0

    size_ref = max(12.0, float(max(previous.w, previous.h, current.w, current.h)))
    size_ratio = min(previous.h, current.h) / max(1.0, max(previous.h, current.h))
    normalized_y_dist = abs((py % LANE_BAND_HEIGHT) - (cy % LANE_BAND_HEIGHT))
    y_gate = max(180.0, size_ref * 7.0)
    if size_ratio < 0.25 or normalized_y_dist > y_gate:
        return -1.0
    return 1.1 + size_ratio - normalized_y_dist / max(1.0, y_gate)


def plate_match_score(previous: BBox, current: BBox, age_frames: int, memory_frames: int) -> float:
    iou = bbox_iou(previous, current)
    px, py = previous.center()
    cx, cy = current.center()
    center_dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
    size_ref = max(12.0, float(max(previous.w, previous.h, current.w, current.h)))
    size_ratio = min(previous.h, current.h) / max(1.0, max(previous.h, current.h))
    if iou >= 0.05:
        return iou + size_ratio
    gate = max(80.0, size_ref * 8.0) if age_frames <= memory_frames else max(50.0, size_ref * 4.0)
    if center_dist <= gate and size_ratio >= 0.35:
        return 0.5 + size_ratio - center_dist / max(1.0, gate)
    return -1.0


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
