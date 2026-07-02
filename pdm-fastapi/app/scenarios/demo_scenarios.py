from __future__ import annotations

from datetime import timedelta
from random import Random

from app.schemas.pdm import DemoScenarioRequest, QualityMetric


def build_demo_metrics(request: DemoScenarioRequest) -> list[QualityMetric]:
    random = Random(42)
    bucket_minutes = 5
    bucket_count = max(6, request.duration_minutes // bucket_minutes)
    metrics: list[QualityMetric] = []

    for index in range(bucket_count):
        bucket_start = request.start_time + timedelta(minutes=bucket_minutes * index)
        bucket_end = bucket_start + timedelta(minutes=bucket_minutes)
        degraded = _degradation_factor(request.scenario_type, index, bucket_count)
        event_count = _event_count(request.scenario_type, random)
        mismatch_rate = min(45.0, 4.0 + degraded * 22 + random.uniform(-1.5, 1.5))
        match_rate = max(0.0, 100.0 - mismatch_rate)
        metrics.append(
            QualityMetric(
                cameraId=2,
                laneId=1,
                bucketStart=bucket_start,
                bucketEnd=bucket_end,
                avgOcrConfidence=max(45.0, 94.0 - degraded * 30 + random.uniform(-2, 2)),
                successRate=max(50.0, 96.0 - degraded * 28 + random.uniform(-2, 2)),
                missingRate=max(0.0, 2.0 + degraded * 18 + random.uniform(-1, 1)),
                matchRate=match_rate,
                mismatchRate=mismatch_rate,
                eventCount=event_count,
            )
        )
    return metrics


def _degradation_factor(scenario_type: str, index: int, bucket_count: int) -> float:
    progress = index / max(1, bucket_count - 1)
    if scenario_type == "NORMAL":
        return 0.05
    if scenario_type == "REAR_DEGRADED":
        return 0.2 + progress * 0.9
    if scenario_type == "MISMATCH_SPIKE":
        return 1.0 if index >= bucket_count - 2 else 0.15
    if scenario_type == "LOW_TRAFFIC":
        return 0.2
    return 0.0


def _event_count(scenario_type: str, random: Random) -> int:
    if scenario_type == "LOW_TRAFFIC":
        return random.randint(1, 6)
    return random.randint(15, 45)
