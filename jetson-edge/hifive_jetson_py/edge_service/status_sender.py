from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hifive_jetson_py.config import CameraConfig, RuntimeConfig
from hifive_jetson_py.spool import FileSpool
from hifive_jetson_py.transport import Sender

from .types import SharedState


EDGE_STATUS_EVENT_PREFIX = "edge-status-"
EDGE_STATUS_FILE = "edge_status_latest.json"


@dataclass
class EdgeStatusSender:
    config: RuntimeConfig
    camera: CameraConfig
    sender: Sender
    shared: SharedState
    spool: FileSpool
    output_dir: Path
    interval_sec: float
    source_mode: str
    source_value: str
    started_at_ms: int

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run_forever, name="hifive-edge-status-sender", daemon=True)
        thread.start()
        return thread

    def run_forever(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        while not self.shared.stop_event.is_set():
            status = self.snapshot()
            self.write_latest(status)
            event_id = f"{EDGE_STATUS_EVENT_PREFIX}{status['ts_ms']}-{self.config.device_id}"
            accepted = self.sender.submit_latest(
                json.dumps(status, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                event_id,
            )
            with self.shared.lock:
                if accepted:
                    self.shared.status_send_ok += 1
                    self.shared.last_status_send_ms = int(status["ts_ms"])
                else:
                    self.shared.status_send_fail += 1
            self.shared.stop_event.wait(max(0.2, self.interval_sec))

    def snapshot(self) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        with self.shared.lock:
            runtime = {
                "uptime_ms": max(0, now_ms - self.started_at_ms),
                "latest_fps": round(float(self.shared.latest_fps), 3),
                "latest_yolo_ms": round(float(self.shared.latest_yolo_ms), 3),
                "latest_ocr_ms": round(float(self.shared.latest_ocr_ms), 3),
                "processed_frames": int(self.shared.processed_frames),
                "processed_ocr_tasks": int(self.shared.processed_ocr_tasks),
                "dropped_ocr_tasks": int(self.shared.dropped_ocr_tasks),
                "yolo_detections": int(self.shared.yolo_detections),
                "sent_events": int(self.shared.sent_events),
                "last_error": self.shared.last_error,
            }
            status_send = {
                "ok": int(self.shared.status_send_ok),
                "fail": int(self.shared.status_send_fail),
                "last_send_ms": int(self.shared.last_status_send_ms),
            }

        return {
            "type": "edge_status",
            "schema_version": "hifive.edge_status.v1",
            "ts_ms": now_ms,
            "device_id": self.config.device_id,
            "camera_id": self.camera.camera_id,
            "camera_role": self.camera.camera_role,
            "source": {
                "mode": self.source_mode,
                "value": self.source_value,
                "source_id": self.camera.source_id,
                "state": "stopping" if self.shared.stop_event.is_set() else "running",
            },
            "runtime": runtime,
            "transport": self.sender.snapshot(),
            "spool": {"count": self.spool.count()},
            "status_send": status_send,
        }

    def write_latest(self, status: dict[str, Any]) -> None:
        target = self.output_dir / EDGE_STATUS_FILE
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)
