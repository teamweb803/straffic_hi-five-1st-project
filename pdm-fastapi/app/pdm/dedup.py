from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any

DedupKey = tuple[int, int, str, str, str]


def payload_key(payload: dict[str, Any]) -> DedupKey:
    """중복 방지 기준 키: (cameraId, laneId, analysisStart, analysisEnd, modelType)."""
    return (
        int(payload["cameraId"]),
        int(payload["laneId"]),
        str(payload["analysisStart"]),
        str(payload["analysisEnd"]),
        str(payload["modelType"]),
    )


class DedupStore:
    """동일 분석 구간 결과의 중복 저장을 막는다.

    SQLite로 영속화하여 **서버 재시작 후에도** 같은 구간을 다시 저장하지 않는다(가이드 §4, §9).
    db_path=":memory:" 이면 휘발성(테스트용).
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        if db_path not in (":memory:", ""):
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        # APScheduler가 워커 스레드에서 호출하므로 check_same_thread=False + lock 보호
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_keys (
                camera_id INTEGER NOT NULL,
                lane_id INTEGER NOT NULL,
                analysis_start TEXT NOT NULL,
                analysis_end TEXT NOT NULL,
                model_type TEXT NOT NULL,
                PRIMARY KEY (camera_id, lane_id, analysis_start, analysis_end, model_type)
            )
            """
        )
        self._conn.commit()

    def seen(self, payload: dict[str, Any]) -> bool:
        key = payload_key(payload)
        with self._lock:
            cursor = self._conn.execute(
                "SELECT 1 FROM saved_keys WHERE camera_id=? AND lane_id=? "
                "AND analysis_start=? AND analysis_end=? AND model_type=?",
                key,
            )
            return cursor.fetchone() is not None

    def mark(self, payload: dict[str, Any]) -> None:
        key = payload_key(payload)
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO saved_keys "
                "(camera_id, lane_id, analysis_start, analysis_end, model_type) "
                "VALUES (?, ?, ?, ?, ?)",
                key,
            )
            self._conn.commit()

    def filter_new(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """아직 저장된 적 없는 payload만 반환."""
        return [p for p in payloads if not self.seen(p)]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
