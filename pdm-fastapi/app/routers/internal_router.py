from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

from app.pdm.demo_refresh import prepare_demo_run
from app.pdm.scheduler import get_scheduler
from app.pdm.runtime import get_analysis_job

router = APIRouter(prefix="/internal/pdm", tags=["PDM Internal"])


@router.post("/run-once")
def run_once(background_tasks: BackgroundTasks, now: datetime | None = None) -> dict[str, str]:
    """관리자/시연용 수동 실행(가이드 §10).

    분석 전체 결과를 길게 반환하지 않고 짧은 ack만 준다. 실제 분석은 백그라운드로 실행.
    """
    if now is None:
        background_tasks.add_task(get_analysis_job().run_once)
    else:
        background_tasks.add_task(get_analysis_job().run_once, now)
    return {"status": "STARTED", "message": "PDM analysis job started"}


@router.post("/demo-refresh")
def demo_refresh(background_tasks: BackgroundTasks) -> dict[str, object]:
    job = get_analysis_job()
    analysis_end, seed_result = prepare_demo_run(job)
    background_tasks.add_task(job.run_once, analysis_end)
    return {
        "status": "STARTED",
        "message": "PDM demo data seeded and analysis job started",
        **seed_result,
    }


@router.get("/status")
def status() -> dict[str, object]:
    """현재 스케줄러/분석 설정 확인용(관리자)."""
    settings = get_analysis_job().settings
    scheduler_status = get_scheduler().status_snapshot()
    return {
        "intervalSeconds": settings.analysis_interval_seconds,
        "targets": settings.targets,
        "analysisWindowMinutes": settings.analysis_window_minutes,
        "fetchHistoryMinutes": settings.fetch_history_minutes,
        "bucketMinutes": settings.bucket_minutes,
        "demoSeedEnabled": settings.demo_seed_enabled,
        "compareEventIntervalSeconds": settings.compare_event_interval_seconds,
        "comparePassesPerTick": settings.compare_passes_per_tick,
        **scheduler_status,
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP"}
