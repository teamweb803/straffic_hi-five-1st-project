from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class IngressStats:
    started_at_ns: int = 0
    received_events: int = 0
    acked_events: int = 0
    retry_events: int = 0
    rejected_events: int = 0
    malformed_frames: int = 0
    last_event_id: str = ""
    last_error: str = ""
    last_payload_bytes: int = 0
    max_recent_events: int = 20
    recent_events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.started_at_ns:
            self.started_at_ns = time.time_ns()
        self._lock = Lock()

    def mark_received(self, event_id: str, payload_bytes: int = 0) -> None:
        with self._lock:
            self.received_events += 1
            self.last_event_id = event_id
            self.last_payload_bytes = int(payload_bytes)

    def mark_ack(self, event_id: str) -> None:
        with self._lock:
            self.acked_events += 1
            self.last_event_id = event_id
            self.last_error = ""
            self._append_recent_locked(event_id, "ack", "", self.last_payload_bytes)

    def mark_retry(self, event_id: str, detail: str) -> None:
        with self._lock:
            self.retry_events += 1
            self.last_event_id = event_id
            self.last_error = detail
            self._append_recent_locked(event_id, "retry", detail, self.last_payload_bytes)

    def mark_reject(self, event_id: str, detail: str) -> None:
        with self._lock:
            self.rejected_events += 1
            self.last_event_id = event_id
            self.last_error = detail
            self._append_recent_locked(event_id, "reject", detail, self.last_payload_bytes)

    def mark_malformed(self, detail: str) -> None:
        with self._lock:
            self.malformed_frames += 1
            self.last_error = detail
            self._append_recent_locked("unknown", "malformed", detail, 0)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            uptime_sec = max(0.0, (time.time_ns() - self.started_at_ns) / 1_000_000_000)
            return {
                "uptime_sec": round(uptime_sec, 3),
                "received_events": self.received_events,
                "acked_events": self.acked_events,
                "retry_events": self.retry_events,
                "rejected_events": self.rejected_events,
                "malformed_frames": self.malformed_frames,
                "last_event_id": self.last_event_id,
                "last_error": self.last_error,
                "last_payload_bytes": self.last_payload_bytes,
                "recent_events": list(self.recent_events),
            }

    def _append_recent_locked(self, event_id: str, status: str, detail: str, payload_bytes: int) -> None:
        self.recent_events.append(
            {
                "ts_ms": int(time.time() * 1000),
                "event_id": event_id,
                "status": status,
                "detail": detail,
                "payload_bytes": int(payload_bytes),
            }
        )
        if len(self.recent_events) > self.max_recent_events:
            del self.recent_events[: len(self.recent_events) - self.max_recent_events]
