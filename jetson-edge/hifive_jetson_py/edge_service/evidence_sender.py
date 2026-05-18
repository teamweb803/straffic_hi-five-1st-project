from __future__ import annotations

from dataclasses import dataclass

from hifive_jetson_py.transport import Sender

from .display import GREEN, draw_text
from .types import ReadyPlateEvent


EVIDENCE_EVENT_PREFIX = "evidence:"
EVENT_IMAGE_KIND = "event_image"
PLATE_CROP_KIND = "plate_crop"


@dataclass
class EvidenceFrameSender:
    sender: Sender
    jpeg_quality: int = 85

    def submit(self, ready: ReadyPlateEvent, event_id: str) -> None:
        task = ready.task
        if task.canvas_snapshot is not None:
            event_image = self._event_image_jpeg(ready)
            if event_image:
                self.sender.submit(
                    event_image,
                    f"{EVIDENCE_EVENT_PREFIX}{EVENT_IMAGE_KIND}:{event_id}",
                )
        if task.crop is not None:
            crop_image = self._jpeg(task.crop)
            if crop_image:
                self.sender.submit(
                    crop_image,
                    f"{EVIDENCE_EVENT_PREFIX}{PLATE_CROP_KIND}:{event_id}",
                )

    def _event_image_jpeg(self, ready: ReadyPlateEvent) -> bytes:
        import cv2

        task = ready.task
        annotated = task.canvas_snapshot.copy()
        cv2.rectangle(
            annotated,
            (task.yolo_bbox.x, task.yolo_bbox.y),
            (task.yolo_bbox.x + task.yolo_bbox.w, task.yolo_bbox.y + task.yolo_bbox.h),
            GREEN,
            2,
        )
        draw_text(
            annotated,
            f"#{task.display_id} {ready.text} h={task.yolo_bbox.h}px",
            (task.yolo_bbox.x, task.yolo_bbox.y + task.yolo_bbox.h + 18),
            0.55,
            GREEN,
            2,
        )
        return self._jpeg(annotated)

    def _jpeg(self, image) -> bytes:  # type: ignore[no-untyped-def]
        import cv2

        quality = max(20, min(95, int(self.jpeg_quality)))
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return b""
        return encoded.tobytes()
