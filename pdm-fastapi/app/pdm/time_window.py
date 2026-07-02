from __future__ import annotations

from datetime import datetime, timedelta


def floor_to_bucket(moment: datetime, bucket_minutes: int) -> datetime:
    """시각을 bucket 경계로 내림한다. 예: 10:37, bucket=10 → 10:30."""
    moment = moment.replace(second=0, microsecond=0)
    return moment - timedelta(minutes=moment.minute % bucket_minutes)


def compute_analysis_window(
    now: datetime,
    bucket_minutes: int,
    window_minutes: int,
) -> tuple[datetime, datetime]:
    """가이드 §6 기준 공식 분석 구간.

    analysisEnd = 현재 시각을 bucket 단위로 내림(집계 미완 현재 구간 제외)
    analysisStart = analysisEnd - window
    예: 10:37, bucket=10, window=60 → (09:30, 10:30)
    """
    analysis_end = floor_to_bucket(now, bucket_minutes)
    analysis_start = analysis_end - timedelta(minutes=window_minutes)
    return analysis_start, analysis_end


def compute_fetch_window(
    now: datetime,
    bucket_minutes: int,
    history_minutes: int,
) -> tuple[datetime, datetime]:
    """Spring 조회용 구간. LSTM-AE가 연속 window를 확보하도록 history를 길게 가져온다.

    history_minutes는 analysis_window_minutes보다 크게 둔다(기본 240분).
    LSTM-AE는 windows = buckets - window_size + 1 ≥ 3 이 필요하므로,
    bucket=10분/window_size=6이면 최소 8개 bucket(=80분) 이상이 있어야 한다.
    """
    fetch_to = floor_to_bucket(now, bucket_minutes)
    fetch_from = fetch_to - timedelta(minutes=history_minutes)
    return fetch_from, fetch_to
