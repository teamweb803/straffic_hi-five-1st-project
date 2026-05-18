from __future__ import annotations

import shutil
import subprocess
import threading
import os
import time
from dataclasses import dataclass
from collections import deque
from typing import Protocol


class VideoReceiverStats(Protocol):
    def mark_video_receiver(self, status: str, detail: dict) -> None: ...


@dataclass(frozen=True)
class SrtVideoReceiverOptions:
    host: str = "0.0.0.0"
    port: int = 0
    latency_ms: int = 120
    command: str = "ffmpeg"


class SrtVideoReceiver:
    def __init__(self, options: SrtVideoReceiverOptions, stats: VideoReceiverStats) -> None:
        self.options = options
        self.stats = stats
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._recent_logs: deque[str] = deque(maxlen=20)

    def start(self) -> None:
        if self.options.port <= 0:
            self.stats.mark_video_receiver(
                "DISABLED",
                {
                    "enabled": False,
                    "connected": False,
                    "transport": "SRT/H264",
                    "last_error": "",
                },
            )
            return
        self._thread = threading.Thread(target=self._run, name="hifive-srt-video-receiver", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        command_path = shutil.which(self.options.command)
        if command_path is None:
            self.stats.mark_video_receiver(
                "ERROR",
                {
                    "enabled": True,
                    "connected": False,
                    "transport": "SRT/H264",
                    "listen_uri": self._uri(),
                    "recent_logs": list(self._recent_logs),
                    "last_error": f"receiver command not found: {self.options.command}",
                },
            )
            return

        while True:
            returncode = self._run_once(command_path)
            if returncode != 0:
                time.sleep(0.5)

    def _run_once(self, command_path: str) -> int:
        args = self._ffmpeg_args(command_path)
        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            self.stats.mark_video_receiver(
                "ERROR",
                {
                    "enabled": True,
                    "connected": False,
                    "transport": "SRT/H264",
                    "listen_uri": self._uri(),
                    "recent_logs": list(self._recent_logs),
                    "last_error": str(exc),
                },
            )
            return -1

        self.stats.mark_video_receiver(
            "LISTENING",
            {
                "enabled": True,
                "connected": False,
                "transport": "SRT/H264",
                "listen_uri": self._uri(),
                "pid": self._process.pid,
                "recent_logs": list(self._recent_logs),
                "last_error": "",
            },
        )

        connected = False
        assert self._process.stderr is not None
        for line in self._process.stderr:
            line = line.strip()
            if not line:
                continue
            self._recent_logs.append(line[:500])
            lower = line.lower()
            if not connected and ("input #0" in lower or "stream #0" in lower):
                connected = True
                self.stats.mark_video_receiver(
                    "RUNNING",
                    {
                        "enabled": True,
                        "connected": True,
                        "transport": "SRT/H264",
                        "listen_uri": self._uri(),
                        "pid": self._process.pid,
                        "recent_logs": list(self._recent_logs),
                        "last_error": "",
                    },
                )
            elif "error" in lower or "failed" in lower:
                self.stats.mark_video_receiver(
                    "ERROR",
                    {
                        "enabled": True,
                        "connected": connected,
                        "transport": "SRT/H264",
                        "listen_uri": self._uri(),
                        "pid": self._process.pid,
                        "recent_logs": list(self._recent_logs),
                        "last_error": line[:500],
                    },
                )

        returncode = self._process.wait()
        status = "STOPPED" if returncode == 0 else "ERROR"
        self.stats.mark_video_receiver(
            status,
            {
                "enabled": True,
                "connected": False,
                "transport": "SRT/H264",
                "listen_uri": self._uri(),
                "pid": self._process.pid,
                "returncode": returncode,
                "recent_logs": list(self._recent_logs),
                "last_error": "" if returncode == 0 else f"receiver exited code={returncode}",
            },
        )
        self._process = None
        return returncode

    def _ffmpeg_args(self, command_path: str) -> list[str]:
        return [
            command_path,
            "-hide_banner",
            "-loglevel",
            "info",
            "-analyzeduration",
            "2000000",
            "-probesize",
            "10000000",
            "-i",
            self._uri(),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-f",
            "mpegts",
            os.devnull,
        ]

    def _uri(self) -> str:
        latency_us = max(20, int(self.options.latency_ms)) * 1000
        return f"srt://{self.options.host}:{self.options.port}?mode=listener&transtype=live&latency={latency_us}"
