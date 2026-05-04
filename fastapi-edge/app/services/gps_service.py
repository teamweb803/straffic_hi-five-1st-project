"""GPS telemetry cache.

Keeps the latest GPS telemetry by track and lane. The demo receives
real phone GPS/LTE telemetry through FastAPI endpoints, then uses this
cache as fallback data when a YOLO detection does not include GPS.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from app.models.schemas import GpsTelemetry

logger = logging.getLogger(__name__)


class GpsCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_track: dict[int, GpsTelemetry] = {}
        self._by_lane: dict[str, GpsTelemetry] = {}

    def upsert_for_track(self, track_id: int, telemetry: GpsTelemetry) -> None:
        with self._lock:
            self._by_track[track_id] = telemetry

    def upsert_for_lane(self, lane_id: str, telemetry: GpsTelemetry) -> None:
        with self._lock:
            self._by_lane[lane_id] = telemetry

    def latest_for(self, track_id: int, lane_id: str) -> Optional[GpsTelemetry]:
        with self._lock:
            return self._by_track.get(track_id) or self._by_lane.get(lane_id)
