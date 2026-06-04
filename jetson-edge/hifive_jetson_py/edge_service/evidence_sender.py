from __future__ import annotations

from dataclasses import dataclass

from hifive_jetson_py.transport import Sender

from .display import GREEN, draw_text
from .types import ReadyPlateEvent


EVIDENCE_EVENT_PREFIX = "evidence:"
EVENT_IMAGE_KIND = "event_image"
PLATE_CROP_KIND = "plate_crop"
EVENT_IMAGE_MAX_WIDTH = 640
EVENT_IMAGE_QUALITY = 70


@dataclass
class EvidenceFrameSender:
    sender: Sender
    jpeg_quality: int = 85

    def submit(self, ready: ReadyPlateEvent, event_id: str) -> None:
        task = ready.task
        if task.crop is not None:
            crop_image = self._jpeg(task.crop)
            if crop_image:
                self.sender.submit(
                    crop_image,
                    f"{EVIDENCE_EVENT_PREFIX}{PLATE_CROP_KIND}:{event_id}",
                )
        if task.canvas_snapshot is not None:
            event_image = self._event_image_jpeg(ready)
            if event_image:
                self.sender.submit(
                    event_image,
                    f"{EVIDENCE_EVENT_PREFIX}{EVENT_IMAGE_KIND}:{event_id}",
                )

    def _event_image_jpeg(self, ready: ReadyPlateEvent) -> bytes:
        import cv2

        task = ready.task
        annotated, offset_x, offset_y = self._lane_event_region(task.canvas_snapshot, task.yolo_bbox)
        box_x = task.yolo_bbox.x - offset_x
        box_y = task.yolo_bbox.y - offset_y
        cv2.rectangle(
            annotated,
            (box_x, box_y),
            (box_x + task.yolo_bbox.w, box_y + task.yolo_bbox.h),
            GREEN,
            2,
        )
        draw_text(
            annotated,
            f"#{task.display_id} {ready.text} h={task.yolo_bbox.h}px",
            (box_x, box_y + task.yolo_bbox.h + 18),
            0.55,
            GREEN,
            2,
        )
        return self._jpeg(self._resize_event_image(annotated), quality=EVENT_IMAGE_QUALITY)

    def _lane_event_region(self, canvas, bbox):  # type: ignore[no-untyped-def]
        height, width = canvas.shape[:2]
        lane_height = height // 2
        if lane_height <= 0:
            return canvas.copy(), 0, 0
        center_y = bbox.y + bbox.h // 2
        lane_y = 0 if center_y < lane_height else lane_height
        return canvas[lane_y : min(height, lane_y + lane_height), 0:width].copy(), 0, lane_y

    def _resize_event_image(self, image):  # type: ignore[no-untyped-def]
        import cv2

        height, width = image.shape[:2]
        if width <= EVENT_IMAGE_MAX_WIDTH:
            return image
        scale = EVENT_IMAGE_MAX_WIDTH / float(width)
        resized_height = max(1, int(round(height * scale)))
        return cv2.resize(image, (EVENT_IMAGE_MAX_WIDTH, resized_height), interpolation=cv2.INTER_AREA)

    def _jpeg(self, image, quality: int | None = None) -> bytes:  # type: ignore[no-untyped-def]
        import cv2

        target_quality = self.jpeg_quality if quality is None else quality
        target_quality = max(20, min(95, int(target_quality)))
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), target_quality])
        if not ok:
            return b""
        return encoded.tobytes()
