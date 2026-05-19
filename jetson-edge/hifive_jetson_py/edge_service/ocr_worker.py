from __future__ import annotations

import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace

from hifive_jetson_py.shared_crop_ipc import discard_shared_plate_crop, open_shared_plate_crop

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
        with self._task_crop(task) as crop_bgr:
            decoded = self.ocr_runner.predict_crop(crop_bgr)
            ocr_ms = (time.perf_counter() - start) * 1000.0
            now = time.monotonic()
            ready = self._process_decoded(task, decoded, ocr_ms, now, crop_bgr)
        if ready is not None:
            self.event_queue.put(ready)

    def _process_decoded(self, task: OcrTask, decoded, ocr_ms: float, now: float, crop_bgr) -> ReadyPlateEvent | None:
        with self.shared.lock:
            self.shared.latest_ocr_ms = ocr_ms
            self.shared.processed_ocr_tasks += 1
            track = self.tracker.tracks.get(task.track_id)
            if track is None:
                return None

            track.pending_ocr = False
            if track.stable_text:
                return None
            track.live_confidence = float(decoded.confidence)
            track.live_valid = bool(decoded.valid_pattern)

            if not task.readable:
                track.candidate_text = ""
                track.candidate_started_at = 0.0
                return None

            if not self._can_emit(decoded):
                return None

            if decoded.text != track.candidate_text:
                track.candidate_text = str(decoded.text)
                track.candidate_started_at = now
                track.live_text = ""
                return None

            if now - track.candidate_started_at < self.stable_sec:
                return None

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
                return None

            track.event_sent = True
            return ReadyPlateEvent(
                task=replace(task, display_id=track.display_id, crop=crop_bgr.copy(), shared_crop=None),
                text=track.stable_text,
                confidence=track.stable_confidence,
            )

    @contextmanager
    def _task_crop(self, task: OcrTask):
        if task.shared_crop is not None:
            with open_shared_plate_crop(task.shared_crop, unlink=True) as crop_bgr:
                yield crop_bgr
            return
        if task.crop is None:
            raise RuntimeError("OCR task has no crop data")
        yield task.crop

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
) -> bool:
    with shared.lock:
        track = tracker.tracks.get(track_id)
        if track is None or track.pending_ocr:
            if task.shared_crop is not None:
                discard_shared_plate_crop(task.shared_crop)
            shared.dropped_ocr_tasks += 1
            return False
        track.pending_ocr = True
    try:
        input_queue.put_nowait(task)
    except queue.Full:
        with shared.lock:
            track = tracker.tracks.get(track_id)
            if track is not None:
                track.pending_ocr = False
            shared.dropped_ocr_tasks += 1
        if task.shared_crop is not None:
            discard_shared_plate_crop(task.shared_crop)
        return False
    return True
