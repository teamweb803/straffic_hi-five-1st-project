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
    network_transition_events: int = 0
    edge_status_events: int = 0
    active_connections: int = 0
    total_connections: int = 0
    last_event_id: str = ""
    last_error: str = ""
    last_payload_bytes: int = 0
    last_connection_closed_ms: int = 0
    spring_forward: dict[str, Any] = field(default_factory=dict)
    last_network_transition: dict[str, Any] = field(default_factory=dict)
    last_edge_status: dict[str, Any] = field(default_factory=dict)
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

    def mark_connection_open(self) -> None:
        with self._lock:
            self.active_connections += 1
            self.total_connections += 1

    def mark_connection_closed(self) -> None:
        with self._lock:
            self.active_connections = max(0, self.active_connections - 1)
            self.last_connection_closed_ms = int(time.time() * 1000)

    def mark_spring_forward(
        self,
        event_id: str,
        status: str,
        status_code: int | None,
        detail: str,
    ) -> None:
        with self._lock:
            self.spring_forward = {
                "event_id": event_id,
                "status": status,
                "status_code": status_code,
                "detail": detail,
                "ts_ms": int(time.time() * 1000),
            }

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

    def mark_network_transition(
        self,
        event_id: str,
        detail: dict[str, Any],
        payload_bytes: int = 0,
    ) -> None:
        with self._lock:
            self.network_transition_events += 1
            self.acked_events += 1
            self.last_event_id = event_id
            self.last_error = ""
            self.last_payload_bytes = int(payload_bytes)
            self.last_network_transition = dict(detail)
            self._append_recent_locked(
                event_id,
                "network_transition",
                self._network_transition_detail(detail),
                self.last_payload_bytes,
            )

    def mark_edge_status(
        self,
        event_id: str,
        detail: dict[str, Any],
        payload_bytes: int = 0,
    ) -> None:
        with self._lock:
            self.edge_status_events += 1
            self.acked_events += 1
            self.last_event_id = event_id
            self.last_error = ""
            self.last_payload_bytes = int(payload_bytes)
            self.last_edge_status = dict(detail)
            self._append_recent_locked(
                event_id,
                "edge_status",
                self._edge_status_detail(detail),
                self.last_payload_bytes,
            )

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
                "network_transition_events": self.network_transition_events,
                "edge_status_events": self.edge_status_events,
                "active_connections": self.active_connections,
                "total_connections": self.total_connections,
                "last_event_id": self.last_event_id,
                "last_error": self.last_error,
                "last_payload_bytes": self.last_payload_bytes,
                "last_connection_closed_ms": self.last_connection_closed_ms,
                "spring_forward": dict(self.spring_forward),
                "last_network_transition": dict(self.last_network_transition),
                "last_edge_status": dict(self.last_edge_status),
                "latest_edge_status": dict(self.last_edge_status),
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

    @staticmethod
    def _network_transition_detail(detail: dict[str, Any]) -> str:
        outage_ms = detail.get("outage_ms", "")
        route_before = detail.get("route_before_failure", "")
        route_after = detail.get("route_after_recovery", "")
        recovered_event_id = detail.get("recovered_event_id", "")
        return (
            f"outage_ms={outage_ms} "
            f"recovered_event_id={recovered_event_id} "
            f"route_before={route_before} "
            f"route_after={route_after}"
        )[:600]

    @staticmethod
    def _edge_status_detail(detail: dict[str, Any]) -> str:
        runtime = detail.get("runtime") if isinstance(detail, dict) else {}
        transport = detail.get("transport") if isinstance(detail, dict) else {}
        if not isinstance(runtime, dict):
            runtime = {}
        if not isinstance(transport, dict):
            transport = {}
        return (
            f"device_id={detail.get('device_id', '')} "
            f"camera_id={detail.get('camera_id', '')} "
            f"frames={runtime.get('processed_frames', '')} "
            f"events={runtime.get('sent_events', '')} "
            f"active_path={transport.get('active_path', '')}"
        )[:600]
