from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from hifive_jetson_py.config import RuntimeConfig
from hifive_jetson_py.event_builder import PassageEventBuilder
from hifive_jetson_py.models import PlateDecision, PlateObservation

from .types import ReadyPlateEvent, SharedState


@dataclass
class EventDispatcher:
    config: RuntimeConfig
    builder: PassageEventBuilder
    shared: SharedState
    queue_size: int = 128

    def __post_init__(self) -> None:
        self._queue: queue.Queue[ReadyPlateEvent] = queue.Queue(maxsize=self.queue_size)
        self._thread = threading.Thread(target=self._run_forever, name="hifive-transport-worker", daemon=True)
        self._thread.start()

    def submit(self, ready: ReadyPlateEvent) -> None:
        try:
            self._queue.put_nowait(ready)
        except queue.Full:
            print(
                f"transport queue full; event not queued "
                f"track=#{ready.task.display_id} plate={ready.text} frame={ready.task.frame_num}"
            )

    def drain(self) -> None:
        self._queue.join()

    def _run_forever(self) -> None:
        while not self.shared.stop_event.is_set() or not self._queue.empty():
            try:
                ready = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            self._submit_now(ready)
            self._queue.task_done()

    def _submit_now(self, ready: ReadyPlateEvent) -> None:
        task = ready.task
        observation = PlateObservation(
            source_id=task.source_id,
            frame_num=task.frame_num,
            local_track_id=f"#{task.display_id}",
            bbox=task.bbox,
            vehicle_confidence=task.confidence,
            plate_text=ready.text,
            plate_confidence=ready.confidence,
            timestamp_ns=task.timestamp_ns,
        )
        decision = PlateDecision(
            text=ready.text,
            confidence=ready.confidence,
            valid_pattern=True,
            needs_review=False,
            review_reason="",
            candidate_count=1,
            agreement_ratio=1.0,
        )
        self.builder.build_and_submit(
            observation=observation,
            lane_no=task.lane_no,
            global_lane_no=task.global_lane_no,
            decision=decision,
        )
        with self.shared.lock:
            self.shared.sent_events += 1
