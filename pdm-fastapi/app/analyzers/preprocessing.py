from __future__ import annotations

from datetime import timedelta
from statistics import median

from app.schemas.pdm import ProcessedMetric, QualityMetric


def normalize_percent(value: float) -> float:
    if 0 <= value <= 1:
        return value * 100
    return value


def preprocess_metrics(
    metrics: list[QualityMetric],
    event_count_min: int,
) -> list[ProcessedMetric]:
    normalized = []
    for metric in metrics:
        payload = metric.as_dict(by_alias=True)
        payload.update(
            {
                "eventCountValid": metric.event_count >= event_count_min,
                "missingBucket": False,
                "avgOcrConfidence": normalize_percent(metric.avg_ocr_confidence),
                "successRate": normalize_percent(metric.success_rate),
                "missingRate": normalize_percent(metric.missing_rate),
                "matchRate": normalize_percent(metric.match_rate)
                if metric.match_rate is not None
                else None,
                "mismatchRate": normalize_percent(metric.mismatch_rate),
            }
        )
        normalized.append(ProcessedMetric(**payload))
    normalized.sort(key=lambda item: (item.camera_id, item.lane_id, item.bucket_start))
    return restore_missing_buckets(normalized)


def restore_missing_buckets(metrics: list[ProcessedMetric]) -> list[ProcessedMetric]:
    restored: list[ProcessedMetric] = []
    groups: dict[tuple[int, int], list[ProcessedMetric]] = {}
    for metric in metrics:
        groups.setdefault((metric.camera_id, metric.lane_id), []).append(metric)

    for group_metrics in groups.values():
        if len(group_metrics) < 2:
            restored.extend(group_metrics)
            continue

        bucket_seconds = _infer_bucket_seconds(group_metrics)
        previous = group_metrics[0]
        restored.append(previous)

        for current in group_metrics[1:]:
            expected_start = previous.bucket_start + timedelta(seconds=bucket_seconds)
            while expected_start < current.bucket_start:
                restored.append(_build_missing_bucket(previous, expected_start, bucket_seconds))
                expected_start = expected_start + timedelta(seconds=bucket_seconds)
            restored.append(current)
            previous = current

    restored.sort(key=lambda item: (item.camera_id, item.lane_id, item.bucket_start))
    return restored


def _infer_bucket_seconds(metrics: list[ProcessedMetric]) -> int:
    gaps = [
        int((right.bucket_start - left.bucket_start).total_seconds())
        for left, right in zip(metrics, metrics[1:])
        if right.bucket_start > left.bucket_start
    ]
    if not gaps:
        duration = int((metrics[0].bucket_end - metrics[0].bucket_start).total_seconds())
        return max(duration, 60)
    return max(int(median(gaps)), 60)


def _build_missing_bucket(
    previous: ProcessedMetric,
    bucket_start,
    bucket_seconds: int,
) -> ProcessedMetric:
    return ProcessedMetric(
        cameraId=previous.camera_id,
        laneId=previous.lane_id,
        bucketStart=bucket_start,
        bucketEnd=bucket_start + timedelta(seconds=bucket_seconds),
        avgOcrConfidence=previous.avg_ocr_confidence,
        successRate=previous.success_rate,
        missingRate=previous.missing_rate,
        matchRate=previous.match_rate,
        mismatchRate=previous.mismatch_rate,
        eventCount=0,
        eventCountValid=False,
        missingBucket=True,
    )
