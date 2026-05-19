from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

from hifive_jetson_py.transport import Sender

from .display import draw_runtime_overlay
from .types import PlateTrack, SharedState


@dataclass
class PreviewFrameSender:
    sender: Sender
    device_id: str
    camera_id: str
    fps: float = 1.0
    jpeg_quality: int = 45
    max_payload_bytes: int = 56_000

    def __post_init__(self) -> None:
        self._interval = 1.0 / max(0.1, self.fps)
        self._last_sent_at = 0.0
        self._queue: queue.Queue[tuple[bytes, str]] = queue.Queue(maxsize=1)
        self._thread = threading.Thread(target=self._run_forever, name="hifive-preview-datagram", daemon=True)
        self._thread.start()

    def maybe_send(
        self,
        canvas_bgr: Any | None,
        tracks: list[PlateTrack],
        shared: SharedState,
        height_threshold: int,
        frame_num: int,
    ) -> None:
        if canvas_bgr is None:
            return
        now = time.monotonic()
        if now - self._last_sent_at < self._interval:
            return
        self._last_sent_at = now

        encoded = self._encode_preview(canvas_bgr, tracks, shared, height_threshold, frame_num)
        if encoded is None:
            return
        event_id = f"preview-frame-{int(time.time() * 1000)}-{self.device_id}-{self.camera_id}"
        self._replace_latest((encoded, event_id))

    def _encode_preview(
        self,
        canvas_bgr: Any,
        tracks: list[PlateTrack],
        shared: SharedState,
        height_threshold: int,
        frame_num: int,
    ) -> bytes | None:
        import cv2

        preview = canvas_bgr.copy()
        draw_runtime_overlay(preview, tracks, shared, height_threshold, frame_num)
        quality = max(20, min(95, int(self.jpeg_quality)))
        while quality >= 20:
            ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            if ok:
                body = encoded.tobytes()
                if len(body) <= self.max_payload_bytes:
                    return body
            quality -= 5
        return None

    def _replace_latest(self, item: tuple[bytes, str]) -> None:
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            pass

    def _run_forever(self) -> None:
        while True:
            payload, event_id = self._queue.get()
            try:
                self.sender.submit_latest(payload, event_id)
            finally:
                self._queue.task_done()
