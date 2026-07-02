from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from typing import Iterable

import httpx


TARGETS = [
    (1, 1, "normal"),
    (2, 1, "critical"),
    (3, 3, "warning"),
    (4, 3, "warning"),
    (5, 5, "normal"),
]


def floor_to_bucket(moment: datetime, bucket_minutes: int) -> datetime:
    return moment.replace(second=0, microsecond=0) - timedelta(
        minutes=moment.minute % bucket_minutes
    )


def metric_values(profile: str, bucket_index: int, step: int) -> dict[str, float | int]:
    drift = min(0.12, step * 0.04 + bucket_index * 0.005)
    if profile == "critical":
        return {
            "avgOcrConfidence": round(max(0.35, 0.58 - drift), 4),
            "successRate": round(max(0.45, 0.62 - drift), 4),
            "missingRate": round(min(0.40, 0.22 + drift), 4),
            "matchRate": round(max(0.45, 0.64 - drift), 4),
            "mismatchRate": round(min(0.45, 0.24 + drift), 4),
            "eventCount": 22,
        }
    if profile == "warning":
        return {
            "avgOcrConfidence": round(max(0.62, 0.75 - drift), 4),
            "successRate": round(max(0.68, 0.82 - drift), 4),
            "missingRate": round(min(0.24, 0.10 + drift), 4),
            "matchRate": round(max(0.68, 0.82 - drift), 4),
            "mismatchRate": round(min(0.24, 0.10 + drift), 4),
            "eventCount": 24,
        }
    return {
        "avgOcrConfidence": 0.94,
        "successRate": 0.96,
        "missingRate": 0.02,
        "matchRate": 0.96,
        "mismatchRate": 0.02,
        "eventCount": 26,
    }


def iter_window_buckets(
    analysis_end: datetime,
    window_minutes: int,
    bucket_minutes: int,
) -> Iterable[tuple[datetime, datetime, int]]:
    bucket_count = window_minutes // bucket_minutes
    analysis_start = analysis_end - timedelta(minutes=window_minutes)
    for index in range(bucket_count):
        start = analysis_start + timedelta(minutes=bucket_minutes * index)
        yield start, start + timedelta(minutes=bucket_minutes), index


def post_quality_metrics(
    client: httpx.Client,
    spring_base_url: str,
    analysis_end: datetime,
    window_minutes: int,
    bucket_minutes: int,
    step: int,
) -> int:
    count = 0
    for camera_id, lane_id, profile in TARGETS:
        for bucket_start, bucket_end, bucket_index in iter_window_buckets(
            analysis_end, window_minutes, bucket_minutes
        ):
            payload = {
                "cameraId": camera_id,
                "laneId": lane_id,
                "bucketStart": bucket_start.isoformat(),
                "bucketEnd": bucket_end.isoformat(),
                **metric_values(profile, bucket_index, step),
            }
            response = client.post(f"{spring_base_url}/api/v1/pdm/quality-metrics", json=payload)
            response.raise_for_status()
            count += 1
    return count


def trigger_analysis(client: httpx.Client, fastapi_base_url: str, analysis_end: datetime) -> None:
    response = client.post(
        f"{fastapi_base_url}/internal/pdm/run-once",
        params={"now": analysis_end.isoformat()},
    )
    response.raise_for_status()


def wait_for_analysis(
    client: httpx.Client,
    fastapi_base_url: str,
    analysis_end: datetime,
    timeout_seconds: int,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    expected_end = analysis_end.isoformat()
    last_status: dict = {}
    while time.monotonic() < deadline:
        status = client.get(f"{fastapi_base_url}/internal/pdm/status")
        status.raise_for_status()
        last_status = status.json()
        job = last_status.get("job") or {}
        summary = job.get("lastSummary") or {}
        if not job.get("running") and summary.get("analysisEnd") == expected_end:
            return last_status
        time.sleep(1)
    return last_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay PDM demo quality metrics.")
    parser.add_argument("--spring-base-url", default="http://localhost:8585")
    parser.add_argument("--fastapi-base-url", default="http://localhost:8001")
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=5.0)
    parser.add_argument("--bucket-minutes", type=int, default=10)
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--wait-timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    base_end = floor_to_bucket(datetime.now(), args.bucket_minutes)
    with httpx.Client(timeout=15.0) as client:
        for step in range(args.steps):
            analysis_end = base_end + timedelta(minutes=args.bucket_minutes * step)
            metric_count = post_quality_metrics(
                client,
                args.spring_base_url.rstrip("/"),
                analysis_end,
                args.window_minutes,
                args.bucket_minutes,
                step,
            )
            trigger_analysis(client, args.fastapi_base_url.rstrip("/"), analysis_end)
            status = wait_for_analysis(
                client,
                args.fastapi_base_url.rstrip("/"),
                analysis_end,
                args.wait_timeout_seconds,
            )
            summary = (status.get("job") or {}).get("lastSummary") or {}
            print(
                f"step={step + 1}/{args.steps} analysisEnd={analysis_end.isoformat()} "
                f"metrics={metric_count} saved={summary.get('savedCount')} "
                f"dup={summary.get('duplicateSkippedCount')} failed={summary.get('failedSaveCount')}"
            )
            if step < args.steps - 1:
                time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
