from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Callable

from app.config import Settings, get_settings
from app.pdm.dedup import DedupStore
from app.pdm.targets import parse_targets
from app.pdm.time_window import compute_analysis_window, compute_fetch_window
from app.pdm.wire import to_wire_payload
from app.schemas.pdm import AnalyzeRequest
from app.services.pdm_analysis_service import PdmAnalysisService
from app.services.spring_pdm_client import SpringFetchError, SpringPdmClient

logger = logging.getLogger("pdm.analysis_job")


class AnalysisJob:
    """주기 분석 Job 본체(가이드 §5).

    구간 계산 -> 카메라/차로 단위로 Spring 조회 -> 3개 모델 실행 ->
    모델별 결과 enum 경계 매핑 -> 중복 제거 -> Spring 저장(부분 실패 내성) -> 로그.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        service: PdmAnalysisService | None = None,
        client_factory: Callable[[], SpringPdmClient] | None = None,
        dedup: DedupStore | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.service = service or PdmAnalysisService()
        self.client_factory = client_factory or self._default_client_factory
        self.dedup = dedup if dedup is not None else DedupStore(self.settings.dedup_db_path)
        self.now_fn = now_fn or datetime.now
        # 중복 실행 방지용 락(스케줄러 max_instances와 별개로 애플리케이션 레벨 보장)
        self._lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._running = False
        self._last_started_at: datetime | None = None
        self._last_finished_at: datetime | None = None
        self._last_summary: dict[str, Any] | None = None
        self._last_error: str | None = None

    def _default_client_factory(self) -> SpringPdmClient:
        return SpringPdmClient(
            base_url=self.settings.spring_base_url,
            timeout_seconds=self.settings.request_timeout_seconds,
            max_retries=self.settings.request_max_retries,
            retry_backoff_seconds=self.settings.request_retry_backoff_seconds,
        )

    def run_once(self, now_override: datetime | None = None) -> dict[str, Any]:
        # 이전 Job이 아직 실행 중이면 이번 실행은 skip(겹쳐 실행 금지, 가이드 §4)
        if not self._lock.acquire(blocking=False):
            logger.warning("이전 분석 Job이 아직 실행 중 -> 이번 실행 skip")
            summary = {"status": "SKIPPED", "reason": "already_running"}
            self._record_skipped(summary)
            return summary
        self._record_started()
        try:
            summary = self._run(now_override)
            self._record_finished(summary, None)
            return summary
        except Exception as exc:
            self._record_finished({"status": "FAILED"}, str(exc))
            raise
        finally:
            self._lock.release()

    def status_snapshot(self) -> dict[str, Any]:
        with self._status_lock:
            return {
                "running": self._running,
                "lastStartedAt": self._last_started_at.isoformat() if self._last_started_at else None,
                "lastFinishedAt": self._last_finished_at.isoformat() if self._last_finished_at else None,
                "lastSummary": self._last_summary,
                "lastError": self._last_error,
            }

    def _record_started(self) -> None:
        with self._status_lock:
            self._running = True
            self._last_started_at = self.now_fn()
            self._last_error = None

    def _record_finished(self, summary: dict[str, Any], error: str | None) -> None:
        with self._status_lock:
            self._running = False
            self._last_finished_at = self.now_fn()
            self._last_summary = summary
            self._last_error = error

    def _record_skipped(self, summary: dict[str, Any]) -> None:
        with self._status_lock:
            self._last_finished_at = self.now_fn()
            self._last_summary = summary

    def _run(self, now_override: datetime | None = None) -> dict[str, Any]:
        now = now_override or self.now_fn()
        analysis_start, analysis_end = compute_analysis_window(
            now, self.settings.bucket_minutes, self.settings.analysis_window_minutes
        )
        fetch_from, fetch_to = compute_fetch_window(
            now, self.settings.bucket_minutes, self.settings.fetch_history_minutes
        )
        targets = parse_targets(self.settings.targets)
        logger.info(
            "분석 Job 시작 window=%s~%s fetch=%s~%s targets=%d",
            analysis_start, analysis_end, fetch_from, fetch_to, len(targets),
        )

        summary: dict[str, Any] = {
            "status": "DONE",
            "analysisStart": analysis_start.isoformat(),
            "analysisEnd": analysis_end.isoformat(),
            "fetchFrom": fetch_from.isoformat(),
            "fetchTo": fetch_to.isoformat(),
            "targetCount": len(targets),
            "savedCount": 0,
            "duplicateSkippedCount": 0,
            "failedSaveCount": 0,
            "noDataTargets": [],
            "fetchFailedTargets": [],
            "modelErrorTargets": [],
        }

        client = self.client_factory()
        try:
            for camera_id, lane_id in targets:
                self._run_target(
                    client, camera_id, lane_id,
                    fetch_from, fetch_to, analysis_start, analysis_end, summary,
                )
        finally:
            client.close()

        logger.info(
            "분석 Job 종료 saved=%d dup=%d failed=%d noData=%d fetchFail=%d modelErr=%d",
            summary["savedCount"], summary["duplicateSkippedCount"], summary["failedSaveCount"],
            len(summary["noDataTargets"]), len(summary["fetchFailedTargets"]),
            len(summary["modelErrorTargets"]),
        )
        return summary

    def _run_target(
        self,
        client: SpringPdmClient,
        camera_id: int,
        lane_id: int,
        fetch_from: datetime,
        fetch_to: datetime,
        analysis_start: datetime,
        analysis_end: datetime,
        summary: dict[str, Any],
    ) -> None:
        # 1) Spring에서 품질 지표 조회
        try:
            metrics = client.fetch_quality_metrics(camera_id, lane_id, fetch_from, fetch_to)
        except SpringFetchError:
            summary["fetchFailedTargets"].append({"cameraId": camera_id, "laneId": lane_id})
            return

        if not metrics:
            logger.warning(
                "데이터 없음 camera=%s lane=%s %s~%s", camera_id, lane_id, fetch_from, fetch_to
            )
            summary["noDataTargets"].append({"cameraId": camera_id, "laneId": lane_id})
            return

        # 2) 3개 모델 실행(엔진 재사용)
        try:
            analysis = self.service.analyze(
                AnalyzeRequest(
                    metrics=metrics,
                    eventCountMin=self.settings.event_count_min,
                    windowSize=self.settings.window_size,
                )
            )
        except Exception as exc:  # noqa: BLE001 - 한 대상 실패가 전체 Job을 막지 않도록
            logger.exception("모델 실행 실패 camera=%s lane=%s: %s", camera_id, lane_id, exc)
            summary["modelErrorTargets"].append({"cameraId": camera_id, "laneId": lane_id})
            return

        # 3) 모델별 payload 추출 + enum 경계 매핑 + 분석 구간을 공식 window로 통일
        #    (HIGH->CRITICAL, LSTM_AE->LSTM, analysisStart/End -> 공식 window, datetime->ISO)
        raw_payloads = [p for integrated in analysis for p in integrated.spring_save_payloads]
        wired = [
            to_wire_payload(p, self.settings, analysis_start=analysis_start, analysis_end=analysis_end)
            for p in raw_payloads
        ]

        # 4) 중복 제거(같은 구간/모델은 다시 저장하지 않음)
        fresh = self.dedup.filter_new(wired)
        summary["duplicateSkippedCount"] += len(wired) - len(fresh)
        if not fresh:
            return

        # 5) 저장(부분 실패 내성) + 6) 성공분만 중복키 기록(실패분은 다음 tick 재시도)
        save_batch = getattr(client, "save_analysis_results_batch_resilient", None)
        if save_batch is None:
            save_batch = client.save_analysis_results_resilient
        saved, failed = save_batch(fresh)
        for payload in saved:
            self.dedup.mark(payload)
        summary["savedCount"] += len(saved)
        summary["failedSaveCount"] += len(failed)
