from __future__ import annotations

import logging
from functools import lru_cache

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings, get_settings
from app.pdm.analysis_job import AnalysisJob
from app.pdm.demo_refresh import backfill_quality_history, prepare_demo_run, seed_compare_events
from app.pdm.runtime import get_analysis_job

logger = logging.getLogger("pdm.scheduler")


class PdmScheduler:
    """APScheduler 기반 주기 실행 관리(가이드 §4)."""

    def __init__(self, job: AnalysisJob | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.job = job or get_analysis_job()
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.add_job(
            self._run_scheduled_analysis,
            trigger="interval",
            seconds=self.settings.analysis_interval_seconds,
            id="pdm_analysis",
            max_instances=1,   # 동시에 한 번만
            coalesce=True,     # 밀린 실행은 하나로 합침
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(
            "PDM 스케줄러 시작 interval=%ds targets=%s",
            self.settings.analysis_interval_seconds, self.settings.targets,
        )
        if self.settings.demo_seed_enabled and self.settings.backfill_on_start:
            # 기동 직후 1회: 공백 구간을 메워 추세선을 연속으로 (앱 시작은 막지 않음)
            self.scheduler.add_job(
                self._run_startup_backfill,
                trigger="date",
                id="pdm_backfill",
                replace_existing=True,
            )
        if self.settings.demo_seed_enabled:
            self.scheduler.add_job(
                self._run_scheduled_compare_events,
                trigger="interval",
                seconds=self.settings.compare_event_interval_seconds,
                id="pdm_compare_events",
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )

    def _run_startup_backfill(self) -> None:
        try:
            count = backfill_quality_history(
                self.settings, self.job.now_fn(), self.settings.backfill_minutes
            )
            logger.info(
                "PDM 시작 백필 완료 buckets=%s minutes=%s",
                count, self.settings.backfill_minutes,
            )
        except Exception as exc:  # noqa: BLE001 - Spring 미기동 등은 치명적 아님
            logger.warning("PDM 시작 백필 건너뜀: %s", exc)

    def _run_scheduled_analysis(self) -> dict[str, object]:
        if not self.settings.demo_seed_enabled:
            return self.job.run_once()

        if self.job.status_snapshot().get("running"):
            return self.job.run_once()

        analysis_end, seed_result = prepare_demo_run(self.job)
        logger.info(
            "PDM 데모 데이터 생성 analysisEnd=%s quality=%s passage=%s",
            seed_result["analysisEnd"],
            seed_result["qualityMetricCount"],
            seed_result["passageEventCount"],
        )
        return self.job.run_once(analysis_end)

    def _run_scheduled_compare_events(self) -> dict[str, object]:
        if not self.settings.demo_seed_enabled:
            return {"status": "SKIPPED", "reason": "demo_seed_disabled"}

        result = seed_compare_events(
            self.settings,
            self.job.now_fn(),
            self.settings.compare_passes_per_tick,
        )
        logger.info(
            "PDM 비교 이벤트 생성 eventEnd=%s passage=%s",
            result["eventEnd"],
            result["passageEventCount"],
        )
        return result

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("PDM 스케줄러 종료")

    def status_snapshot(self) -> dict[str, object]:
        job = self.scheduler.get_job("pdm_analysis")
        compare_job = self.scheduler.get_job("pdm_compare_events")
        next_run_time = getattr(job, "next_run_time", None) if job else None
        compare_next_run_time = getattr(compare_job, "next_run_time", None) if compare_job else None
        return {
            "schedulerRunning": self.scheduler.running,
            "schedulerAutostart": self.settings.scheduler_autostart,
            "nextRunAt": next_run_time.isoformat() if next_run_time else None,
            "compareNextRunAt": compare_next_run_time.isoformat() if compare_next_run_time else None,
            "job": self.job.status_snapshot(),
        }


@lru_cache
def get_scheduler() -> PdmScheduler:
    return PdmScheduler()
