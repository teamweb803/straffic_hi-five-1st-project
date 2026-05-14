from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime import EdgeServiceRuntimeOptions
from .status_sender import EDGE_STATUS_FILE


@dataclass
class EdgeServiceRun:
    source_kind: str
    source_value: str
    started_at_ms: int
    process: subprocess.Popen


class EdgeServiceManager:
    def __init__(self, base_options: EdgeServiceRuntimeOptions) -> None:
        self.base_options = base_options
        self._lock = threading.Lock()
        self._active: EdgeServiceRun | None = None
        self._completed_runs = 0
        self._last_error = ""
        self._last_source_kind = ""
        self._last_source_value = ""
        self._last_started_at_ms = 0
        self._last_stopped_at_ms = 0

    def start_video(
        self,
        *,
        video: str,
        start_sec: float = 0.0,
        limit: int = 0,
        display: bool = False,
        repeat: bool = False,
        repeat_delay_sec: float = 0.2,
    ) -> dict[str, Any]:
        if not video:
            return {"accepted": False, "detail": "video path is required", **self.status()}
        return self._start(
            "video",
            video,
            start_sec=start_sec,
            limit=limit,
            display=display,
            repeat=repeat,
            repeat_delay_sec=repeat_delay_sec,
        )

    def start_camera(
        self,
        *,
        camera_index: int = 0,
        display: bool = False,
        limit: int = 0,
    ) -> dict[str, Any]:
        return self._start("camera", str(camera_index), limit=limit, display=display)

    def stop(self, wait_sec: float = 3.0) -> dict[str, Any]:
        with self._lock:
            self._cleanup_finished_locked()
            active = self._active
            if active is None:
                return {"accepted": True, "detail": "no active source", **self._status_locked()}
            active.process.terminate()
        try:
            active.process.wait(timeout=max(0.0, wait_sec))
        except subprocess.TimeoutExpired:
            active.process.kill()
            active.process.wait(timeout=1.0)
        with self._lock:
            if self._active is active:
                self._complete_active_locked(error="")
            return {"accepted": True, "detail": "source stopped", **self._status_locked()}

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._cleanup_finished_locked()
            return self._status_locked()

    def _start(
        self,
        source_kind: str,
        source_value: str,
        *,
        start_sec: float = 0.0,
        limit: int = 0,
        display: bool = False,
        repeat: bool = False,
        repeat_delay_sec: float = 0.2,
    ) -> dict[str, Any]:
        with self._lock:
            self._cleanup_finished_locked()
            if self._active is not None and self._active.process.poll() is None:
                return {"accepted": False, "detail": "source already running", **self._status_locked()}

            started_at_ms = int(time.time() * 1000)
            process = subprocess.Popen(
                self._build_command(
                    source_kind=source_kind,
                    source_value=source_value,
                    start_sec=start_sec,
                    limit=limit,
                    display=display,
                    repeat=repeat,
                    repeat_delay_sec=repeat_delay_sec,
                ),
                cwd=str(self._app_dir()),
                env=self._subprocess_env(),
            )
            self._active = EdgeServiceRun(
                source_kind=source_kind,
                source_value=source_value,
                started_at_ms=started_at_ms,
                process=process,
            )
            self._last_error = ""
            self._last_source_kind = source_kind
            self._last_source_value = source_value
            self._last_started_at_ms = started_at_ms
            print(f"edge_service_source_started kind={source_kind} value={source_value} pid={process.pid}")
            return {
                "accepted": True,
                "detail": "source started",
                "warnings": self._start_warnings(start_sec=start_sec, limit=limit, display=display),
                **self._status_locked(),
            }

    def _status_locked(self) -> dict[str, Any]:
        active = self._active
        now_ms = int(time.time() * 1000)
        running = active is not None and active.process.poll() is None
        uptime_ms = now_ms - active.started_at_ms if active is not None else 0
        runtime_status = self._read_runtime_status()
        return {
            "running": running,
            "source_state": "running" if running else "idle",
            "runtime_runner": self.base_options.runtime_runner,
            "active_source_kind": active.source_kind if active is not None else "",
            "active_source_value": active.source_value if active is not None else "",
            "active_pid": active.process.pid if active is not None else 0,
            "active_uptime_ms": max(0, uptime_ms),
            "completed_runs": self._completed_runs,
            "last_error": self._last_error,
            "last_source_kind": self._last_source_kind,
            "last_source_value": self._last_source_value,
            "last_started_at_ms": self._last_started_at_ms,
            "last_stopped_at_ms": self._last_stopped_at_ms,
            "runtime_status_stale": bool(runtime_status.get("stale", False)),
            "runtime_status_age_ms": int(runtime_status.get("status_age_ms", 0) or 0),
            "runtime_status": runtime_status,
        }

    def _cleanup_finished_locked(self) -> None:
        active = self._active
        if active is not None and active.process.poll() is not None:
            returncode = active.process.returncode
            error = "" if returncode == 0 else f"process exited code={returncode}"
            self._complete_active_locked(error=error)

    def _complete_active_locked(self, error: str) -> None:
        active = self._active
        if active is None:
            return
        self._completed_runs += 1
        self._last_error = error
        self._last_stopped_at_ms = int(time.time() * 1000)
        print(
            f"edge_service_source_stopped kind={active.source_kind} "
            f"value={active.source_value} code={active.process.returncode} error={error}"
        )
        self._active = None

    def _build_command(
        self,
        *,
        source_kind: str,
        source_value: str,
        start_sec: float,
        limit: int,
        display: bool,
        repeat: bool,
        repeat_delay_sec: float,
    ) -> list[str]:
        options = self.base_options
        if options.runtime_runner == "deepstream-nvinfer":
            return self._build_deepstream_nvinfer_command(
                source_kind=source_kind,
                source_value=source_value,
                display=display,
                repeat=repeat,
                repeat_delay_sec=repeat_delay_sec,
            )
        return self._build_python_runtime_command(
            source_kind=source_kind,
            source_value=source_value,
            start_sec=start_sec,
            limit=limit,
            display=display,
        )

    def _build_python_runtime_command(
        self,
        *,
        source_kind: str,
        source_value: str,
        start_sec: float,
        limit: int,
        display: bool,
    ) -> list[str]:
        options = self.base_options
        command = [
            sys.executable,
            str(self._app_dir() / "run_edge_runtime.py"),
            "--config",
            options.config_path,
            "--display-scale",
            str(options.display_scale),
            "--input-backend",
            options.input_backend,
            "--height-threshold",
            str(options.height_threshold),
            "--ocr-stable-sec",
            str(options.ocr_stable_sec),
            "--track-memory-sec",
            str(options.track_memory_sec),
            "--reid-sec",
            str(options.reid_sec),
            "--queue-size",
            str(options.queue_size),
            "--transport-queue-size",
            str(options.transport_queue_size),
            "--transport-timeout-sec",
            str(options.transport_timeout_sec),
            "--retry-initial-sec",
            str(options.retry_initial_sec),
            "--retry-max-sec",
            str(options.retry_max_sec),
            "--output-dir",
            options.output_dir,
            "--status-interval-sec",
            str(options.status_interval_sec),
        ]
        if options.host_override:
            command.extend(["--host", options.host_override])
        if options.port_override > 0:
            command.extend(["--port", str(options.port_override)])
        if options.standby_host_override:
            command.extend(["--standby-host", options.standby_host_override])
        if options.standby_port_override > 0:
            command.extend(["--standby-port", str(options.standby_port_override)])
        if options.failover_recheck_sec > 0:
            command.extend(["--failover-recheck-sec", str(options.failover_recheck_sec)])
        if options.yolo_engine_override:
            command.extend(["--yolo-engine", options.yolo_engine_override])
        if options.ocr_engine_override:
            command.extend(["--ocr-engine", options.ocr_engine_override])
        if display:
            command.append("--display")
        if not options.save_event_images:
            command.append("--no-save-event-images")
        if source_kind == "video":
            command.extend(["--video", source_value, "--start-sec", str(start_sec)])
        elif source_kind == "camera":
            command.extend(["--camera-index", source_value])
        else:
            raise ValueError(f"unsupported source kind: {source_kind}")
        command.extend(["--limit", str(limit)])
        return command

    def _start_warnings(self, *, start_sec: float, limit: int, display: bool) -> list[str]:
        if self.base_options.runtime_runner != "deepstream-nvinfer":
            return []
        warnings: list[str] = []
        if start_sec > 0:
            warnings.append("start_sec is ignored by deepstream-nvinfer")
        if limit > 0:
            warnings.append("limit is ignored by deepstream-nvinfer")
        return warnings

    def _build_deepstream_nvinfer_command(
        self,
        *,
        source_kind: str,
        source_value: str,
        display: bool,
        repeat: bool,
        repeat_delay_sec: float,
    ) -> list[str]:
        options = self.base_options
        command = [
            sys.executable,
            str(self._app_dir() / "run_deepstream_nvinfer.py"),
            "--config",
            options.config_path,
            "--transport-queue-size",
            str(options.transport_queue_size),
            "--status-interval-sec",
            str(options.status_interval_sec),
            "--preview-datagram-fps",
            str(options.preview_datagram_fps),
            "--preview-jpeg-quality",
            str(options.preview_jpeg_quality),
            "--evidence-jpeg-quality",
            str(options.evidence_jpeg_quality),
            "--output-dir",
            options.output_dir,
            "--height-threshold",
            str(options.height_threshold),
            "--ocr-stable-sec",
            str(options.ocr_stable_sec),
            "--track-memory-sec",
            str(options.track_memory_sec),
            "--reid-sec",
            str(options.reid_sec),
            "--queue-size",
            str(options.queue_size),
            "--parser-lib",
            options.parser_lib,
            "--yolo-parser-func",
            options.yolo_parser_func,
            "--ocr-parser-func",
            options.ocr_parser_func,
            "--tracker-lib",
            options.tracker_lib,
            "--tracker-config",
            options.tracker_config,
            "--transport-timeout-sec",
            str(options.transport_timeout_sec),
            "--retry-initial-sec",
            str(options.retry_initial_sec),
            "--retry-max-sec",
            str(options.retry_max_sec),
        ]
        if options.host_override:
            command.extend(["--host", options.host_override])
        if options.port_override > 0:
            command.extend(["--port", str(options.port_override)])
        if options.standby_host_override:
            command.extend(["--standby-host", options.standby_host_override])
        if options.standby_port_override > 0:
            command.extend(["--standby-port", str(options.standby_port_override)])
        if options.failover_recheck_sec > 0:
            command.extend(["--failover-recheck-sec", str(options.failover_recheck_sec)])
        if options.yolo_engine_override:
            command.extend(["--yolo-engine", options.yolo_engine_override])
        if options.ocr_engine_override:
            command.extend(["--ocr-engine", options.ocr_engine_override])
        if options.evidence_upload:
            command.append("--evidence-upload")
        if not options.save_event_images:
            command.append("--no-save-event-images")
        if display:
            command.extend(
                [
                    "--display",
                    "--display-scale",
                    str(options.display_scale),
                    "--display-sink",
                    options.display_sink,
                ]
            )
        if options.yolo_parser_lib:
            command.extend(["--yolo-parser-lib", options.yolo_parser_lib])
        if options.ocr_parser_lib:
            command.extend(["--ocr-parser-lib", options.ocr_parser_lib])
        if source_kind == "video":
            command.extend(["--source", source_value])
            if repeat:
                command.extend(["--repeat", "--repeat-delay-sec", str(repeat_delay_sec)])
        elif source_kind == "camera":
            command.extend(["--camera-index", source_value])
        else:
            raise ValueError(f"unsupported source kind: {source_kind}")
        return command

    def _subprocess_env(self) -> dict[str, str]:
        env = dict(os.environ)
        app_dir = str(self._app_dir())
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = app_dir if not current else f"{app_dir}{os.pathsep}{current}"
        return env

    def _app_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _read_runtime_status(self) -> dict[str, Any]:
        status_path = Path(self.base_options.output_dir) / EDGE_STATUS_FILE
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except Exception as exc:
            return {"read_error": str(exc)}
        now_ms = int(time.time() * 1000)
        ts_ms = int(status.get("ts_ms", 0) or 0)
        age_ms = max(0, now_ms - ts_ms) if ts_ms > 0 else 0
        status["status_age_ms"] = age_ms
        status["stale"] = ts_ms <= 0 or age_ms > 5000
        return status


def build_edge_service_app(manager: EdgeServiceManager):
    from fastapi import FastAPI

    app = FastAPI(title="HI-FIVE Jetson Edge Service")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict[str, Any]:
        return manager.status()

    @app.post("/source/video")
    async def start_video(
        video: str,
        start_sec: float = 0.0,
        limit: int = 0,
        display: bool = False,
        repeat: bool = False,
        repeat_delay_sec: float = 0.2,
    ) -> dict[str, Any]:
        return manager.start_video(
            video=video,
            start_sec=start_sec,
            limit=limit,
            display=display,
            repeat=repeat,
            repeat_delay_sec=repeat_delay_sec,
        )

    @app.post("/start-video")
    async def start_video_alias(
        video: str,
        start_sec: float = 0.0,
        limit: int = 0,
        display: bool = False,
        repeat: bool = False,
        repeat_delay_sec: float = 0.2,
    ) -> dict[str, Any]:
        return manager.start_video(
            video=video,
            start_sec=start_sec,
            limit=limit,
            display=display,
            repeat=repeat,
            repeat_delay_sec=repeat_delay_sec,
        )

    @app.post("/source/camera")
    async def start_camera(
        camera_index: int = 0,
        limit: int = 0,
        display: bool = False,
    ) -> dict[str, Any]:
        return manager.start_camera(camera_index=camera_index, limit=limit, display=display)

    @app.post("/start-camera")
    async def start_camera_alias(
        camera_index: int = 0,
        limit: int = 0,
        display: bool = False,
    ) -> dict[str, Any]:
        return manager.start_camera(camera_index=camera_index, limit=limit, display=display)

    @app.post("/source/stop")
    async def stop_source(wait_sec: float = 3.0) -> dict[str, Any]:
        return manager.stop(wait_sec=wait_sec)

    @app.post("/stop-source")
    async def stop_source_alias(wait_sec: float = 3.0) -> dict[str, Any]:
        return manager.stop(wait_sec=wait_sec)

    return app
