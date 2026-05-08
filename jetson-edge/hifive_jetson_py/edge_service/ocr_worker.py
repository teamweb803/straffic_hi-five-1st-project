from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, replace

from .plate_tracker import PlateBBoxTracker
from .types import OcrTask, ReadyPlateEvent, SharedState


@dataclass
class OcrWorker:
    ocr_runner: object
    tracker: PlateBBoxTracker
    input_queue: queue.Queue[OcrTask]
    event_queue: queue.Queue[ReadyPlateEvent]
    shared: SharedState
    stable_sec: float
    min_confidence: float
    allow_invalid: bool = False

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run_forever, name="hifive-ocr-worker", daemon=True)
        thread.start()
        return thread

    def run_forever(self) -> None:
        while not self.shared.stop_event.is_set():
            try:
                task = self.input_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            self.process_task(task)
            self.input_queue.task_done()

    def process_task(self, task: OcrTask) -> None:
        start = time.perf_counter()
        decoded = self.ocr_runner.predict_crop(task.crop)
        ocr_ms = (time.perf_counter() - start) * 1000.0
        now = time.monotonic()

        with self.shared.lock:
            self.shared.latest_ocr_ms = ocr_ms
            self.shared.processed_ocr_tasks += 1
            track = self.tracker.tracks.get(task.track_id)
            if track is None:
                return

            track.pending_ocr = False
            if track.stable_text:
                return
            track.live_confidence = float(decoded.confidence)
            track.live_valid = bool(decoded.valid_pattern)

            if not task.readable:
                track.candidate_text = ""
                track.candidate_started_at = 0.0
                return

            if not self._can_emit(decoded):
                return

            if decoded.text != track.candidate_text:
                track.candidate_text = str(decoded.text)
                track.candidate_started_at = now
                track.live_text = ""
                return

            if now - track.candidate_started_at < self.stable_sec:
                return

            track.stable_text = str(decoded.text)
            track.live_text = track.stable_text
            track.stable_confidence = float(decoded.confidence)
            restored = self.tracker.restore_display_id_by_ocr(track, track.stable_text, task.frame_num)
            if not restored:
                self.tracker.ensure_display_id(track)
            self.tracker.remember_ocr(track.display_id, track.stable_text, task.frame_num)
            if restored:
                track.event_sent = True
            if track.event_sent:
                return

            track.event_sent = True
            self.event_queue.put(
                ReadyPlateEvent(
                    task=replace(task, display_id=track.display_id),
                    text=track.stable_text,
                    confidence=track.stable_confidence,
                )
            )

    def _can_emit(self, decoded) -> bool:
        if not decoded.text:
            return False
        if float(decoded.confidence) < self.min_confidence:
            return False
        if not self.allow_invalid and not bool(decoded.valid_pattern):
            return False
        return True


def put_latest_ocr_task(
    input_queue: queue.Queue[OcrTask],
    shared: SharedState,
    track_id: str,
    tracker: PlateBBoxTracker,
    task: OcrTask,
) -> None:
    with shared.lock:
        track = tracker.tracks.get(track_id)
        if track is None or track.pending_ocr:
            return
        track.pending_ocr = True
    try:
        input_queue.put_nowait(task)
    except queue.Full:
        with shared.lock:
            track = tracker.tracks.get(track_id)
            if track is not None:
                track.pending_ocr = False
