"""Small REST client for Spring Boot ingestion APIs."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any
from urllib import error, request

from app.core.config import Settings
from app.models.schemas import GpsTelemetry

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _camel_payload(telemetry: GpsTelemetry, *, lane_id: str | None, track_id: int | None, edge_node_id: str) -> dict[str, Any]:
    return {
        "gpsDeviceId": telemetry.gps_device_id or "PHONE-DEMO-01",
        "plateNumber": telemetry.plate_number,
        "edgeNodeId": telemetry.edge_node_id or edge_node_id,
        "laneId": telemetry.lane_id or lane_id,
        "trackId": telemetry.track_id if telemetry.track_id is not None else track_id,
        "latitude": telemetry.latitude,
        "longitude": telemetry.longitude,
        "speedKmh": telemetry.speed_kmh,
        "heading": telemetry.heading,
        "altitudeM": telemetry.altitude_m,
        "accuracyM": telemetry.accuracy_m,
        "provider": telemetry.provider,
        "capturedAt": telemetry.captured_at,
    }


class SpringRestClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_gps_telemetry(
        self,
        telemetry: GpsTelemetry,
        *,
        lane_id: str | None = None,
        track_id: int | None = None,
    ) -> None:
        payload = _camel_payload(
            telemetry,
            lane_id=lane_id,
            track_id=track_id,
            edge_node_id=self._settings.edge_node_id,
        )
        await asyncio.to_thread(self._post_json, "/api/gps/telemetry", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> None:
        url = self._settings.spring_rest_base_url.rstrip("/") + path
        body = json.dumps(payload, default=_json_default).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._settings.spring_rest_timeout_sec) as resp:
                if resp.status >= 400:
                    logger.warning("Spring REST ingest failed status=%s url=%s", resp.status, url)
        except (error.URLError, TimeoutError) as exc:
            logger.warning("Spring REST ingest unavailable: %s", exc)
