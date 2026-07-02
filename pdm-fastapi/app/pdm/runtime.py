from __future__ import annotations

from functools import lru_cache

from app.pdm.analysis_job import AnalysisJob


@lru_cache
def get_analysis_job() -> AnalysisJob:
    """스케줄러와 수동 실행(run-once)이 공유하는 단일 Job 인스턴스.

    같은 인스턴스를 공유해야 중복 실행 방지 락(_lock)과 dedup 저장소가 함께 동작한다.
    """
    return AnalysisJob()
