from __future__ import annotations

from dataclasses import dataclass

from .config import CameraConfig, YoloInputSlot
from .models import BBox


@dataclass
class TwoLaneYoloInputComposer:
    camera: CameraConfig
    canvas_width: int = 960
    canvas_height: int = 960

    def compose(self, frame_bgr):
        import cv2
        import numpy as np

        frame = np.asarray(frame_bgr)
        if frame.ndim != 3:
            raise ValueError("frame must be HxWxC")
        canvas = np.zeros((self.canvas_height, self.canvas_width, frame.shape[2]), dtype=frame.dtype)
        for slot in self.camera.yolo_input_slots:
            source = self._crop(frame, slot.source_rect)
            if source.size == 0:
                continue
            if source.shape[1] != slot.canvas_rect.w or source.shape[0] != slot.canvas_rect.h:
                source = cv2.resize(
                    source,
                    (slot.canvas_rect.w, slot.canvas_rect.h),
                    interpolation=cv2.INTER_LINEAR,
                )
            x1 = slot.canvas_rect.x
            y1 = slot.canvas_rect.y
            x2 = x1 + slot.canvas_rect.w
            y2 = y1 + slot.canvas_rect.h
            canvas[y1:y2, x1:x2] = source
        return canvas

    def restore_bbox(self, yolo_bbox: BBox) -> tuple[BBox, int, int] | None:
        slot = self.slot_for_bbox(yolo_bbox)
        if slot is None:
            return None
        restored = self._restore_from_slot(yolo_bbox, slot)
        return restored, slot.lane_no, slot.global_lane_no

    def slot_for_bbox(self, yolo_bbox: BBox) -> YoloInputSlot | None:
        cx, cy = yolo_bbox.center()
        for slot in self.camera.yolo_input_slots:
            rect = slot.canvas_rect
            if rect.x <= cx < rect.x + rect.w and rect.y <= cy < rect.y + rect.h:
                return slot
        return None

    def _restore_from_slot(self, yolo_bbox: BBox, slot: YoloInputSlot) -> BBox:
        source = slot.source_rect
        canvas = slot.canvas_rect
        scale_x = source.w / canvas.w
        scale_y = source.h / canvas.h
        x = source.x + int(round((yolo_bbox.x - canvas.x) * scale_x))
        y = source.y + int(round((yolo_bbox.y - canvas.y) * scale_y))
        w = int(round(yolo_bbox.w * scale_x))
        h = int(round(yolo_bbox.h * scale_y))
        return BBox(x=x, y=y, w=w, h=h, coord="original_frame")

    def _crop(self, frame, rect: BBox):
        h, w = frame.shape[:2]
        clipped = rect.clipped(w, h)
        return frame[clipped.y : clipped.y + clipped.h, clipped.x : clipped.x + clipped.w]
