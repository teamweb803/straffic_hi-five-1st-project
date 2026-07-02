from __future__ import annotations

from datetime import datetime, timedelta
from math import sin
from random import Random
from typing import Any, Iterable

import httpx

from app.config import Settings
from app.pdm.analysis_job import AnalysisJob
from app.pdm.targets import parse_targets
from app.pdm.time_window import floor_to_bucket


REFERENCE_PATTERN_START_MINUTE = 9 * 60
REFERENCE_BUCKET_MINUTES = 10
REFERENCE_PATTERN_BUCKETS = 24
DEMO_CURVE_START_MINUTE = 9 * 60
DEMO_CURVE_BUCKETS = 36


def next_demo_analysis_end(job: AnalysisJob) -> datetime:
    settings = job.settings
    return floor_to_bucket(job.now_fn(), settings.bucket_minutes)


def seed_demo_window(
    settings: Settings,
    analysis_end: datetime,
    event_end: datetime | None = None,
) -> dict[str, Any]:
    spring_base_url = settings.spring_base_url.rstrip("/")
    quality_window_minutes = max(settings.analysis_window_minutes, settings.backfill_minutes)
    effective_event_end = event_end or analysis_end
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        quality_count = _post_quality_metrics(
            client, spring_base_url, settings, analysis_end, quality_window_minutes
        )
    return {
        "analysisEnd": analysis_end.isoformat(),
        "eventEnd": effective_event_end.isoformat(),
        "qualityMetricCount": quality_count,
        "passageEventCount": 0,
    }


def seed_compare_events(
    settings: Settings,
    event_end: datetime,
    pass_count: int | None = None,
) -> dict[str, Any]:
    spring_base_url = settings.spring_base_url.rstrip("/")
    effective_pass_count = pass_count or settings.compare_passes_per_tick
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        passage_count = _post_compare_events(
            client,
            spring_base_url,
            event_end,
            pass_count=effective_pass_count,
            recent=True,
        )
    return {
        "eventEnd": event_end.isoformat(),
        "passageEventCount": passage_count,
    }


def prepare_demo_run(job: AnalysisJob) -> tuple[datetime, dict[str, Any]]:
    now = job.now_fn()
    analysis_end = next_demo_analysis_end(job)
    return analysis_end, seed_demo_window(job.settings, analysis_end, event_end=now)


def backfill_quality_history(settings: Settings, end: datetime, minutes: int) -> int:
    """기동 시 서버가 꺼져 있던 구간의 품질지표 버킷을 메워 추세선을 연속으로 만든다.

    Spring 품질지표 저장은 (camera, lane, bucketStart) 기준 upsert라
    이미 존재하는 버킷은 갱신되고 빠진 버킷은 새로 생성된다.
    """
    if minutes <= 0:
        return 0

    spring_base_url = settings.spring_base_url.rstrip("/")
    last_bucket = floor_to_bucket(end, settings.bucket_minutes)
    span = timedelta(minutes=settings.bucket_minutes)
    count = 0
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        for camera_id, lane_id in parse_targets(settings.targets):
            bucket_start = last_bucket - timedelta(minutes=minutes)
            while bucket_start < last_bucket:
                bucket_end = bucket_start + span
                response = client.post(
                    f"{spring_base_url}/api/v1/pdm/quality-metrics",
                    json={
                        "cameraId": camera_id,
                        "laneId": lane_id,
                        "bucketStart": bucket_start.isoformat(),
                        "bucketEnd": bucket_end.isoformat(),
                        **_metric_values(camera_id, bucket_start),
                    },
                )
                response.raise_for_status()
                count += 1
                bucket_start = bucket_end
    return count


def _last_analysis_end(status: dict[str, Any]) -> datetime | None:
    raw = ((status.get("lastSummary") or {}).get("analysisEnd"))
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def _metric_values(camera_id: int, bucket_start: datetime) -> dict[str, float | int]:
    index = _demo_curve_index(bucket_start)
    ocr, success, missing, match, mismatch, event_count = _naturalize_values(
        camera_id, index, bucket_start, _reference_values(camera_id, index)
    )
    return {
        "avgOcrConfidence": _rate(ocr),
        "successRate": _rate(success),
        "missingRate": _rate(missing),
        "matchRate": _rate(match),
        "mismatchRate": _rate(mismatch),
        "eventCount": event_count,
    }


def _demo_curve_index(bucket_start: datetime) -> int:
    minute_of_day = bucket_start.hour * 60 + bucket_start.minute
    return (
        (minute_of_day - DEMO_CURVE_START_MINUTE) // REFERENCE_BUCKET_MINUTES
    ) % DEMO_CURVE_BUCKETS


def _reference_pattern_index(bucket_start: datetime) -> int:
    minute_of_day = bucket_start.hour * 60 + bucket_start.minute
    return (
        (minute_of_day - REFERENCE_PATTERN_START_MINUTE) // REFERENCE_BUCKET_MINUTES
    ) % REFERENCE_PATTERN_BUCKETS


def _reference_values(camera_id: int, index: int) -> tuple[float, float, float, float, float, int]:
    if camera_id == 1:
        ocr = _curve(index, (
            (0, 90.2), (4, 91.8), (6, 93.2), (7, 90.3),
            (12, 92.3), (14, 93.6), (15, 90.4), (21, 93.4),
            (22, 90.6), (28, 92.9), (31, 93.5), (35, 91.0),
        ))
        success = _curve(index, (
            (0, 95.8), (5, 96.9), (7, 95.1), (13, 96.7),
            (16, 95.6), (22, 96.8), (25, 95.4), (31, 96.5),
            (35, 95.9),
        ))
        match = _curve(index, (
            (0, 96.1), (5, 95.4), (8, 96.7), (14, 95.3),
            (18, 96.6), (23, 95.1), (29, 96.8), (35, 95.7),
        ))
        missing = _curve(index, (
            (0, 2.4), (6, 1.6), (8, 2.8), (14, 1.7),
            (16, 2.6), (22, 1.8), (25, 2.7), (31, 1.9), (35, 2.5),
        ))
        mismatch = 100.0 - match
        return ocr, success, missing, match, mismatch, 48 + (index * 2) % 7

    if camera_id == 2:
        ocr = _curve(index, (
            (0, 88.6), (5, 90.7), (9, 89.3), (11, 91.0),
            (12, 83.5), (13, 48.0), (14, 84.5), (16, 90.4),
            (21, 91.1), (25, 89.0), (30, 90.3), (35, 89.2),
        ))
        success = _curve(index, (
            (0, 93.2), (5, 95.1), (9, 93.8), (11, 94.8),
            (12, 88.5), (13, 58.0), (14, 89.0), (16, 94.9),
            (21, 95.3), (25, 93.5), (30, 94.5), (35, 93.8),
        ))
        missing = _curve(index, (
            (0, 3.1), (6, 2.4), (10, 3.3), (12, 8.0),
            (13, 34.0), (14, 7.5), (17, 2.8), (24, 3.4),
            (30, 2.8), (35, 3.2),
        ))
        match = _curve(index, (
            (0, 93.7), (5, 94.8), (9, 93.1), (11, 94.2),
            (12, 86.0), (13, 59.0), (14, 87.0), (16, 94.5),
            (22, 95.0), (27, 93.2), (32, 94.4), (35, 93.8),
        ))
        mismatch = _curve(index, (
            (0, 6.3), (8, 6.8), (12, 14.0), (13, 41.0),
            (14, 13.0), (17, 5.8), (27, 6.8), (35, 6.2),
        ))
        return ocr, success, missing, match, mismatch, 45 + (index * 3) % 8

    if camera_id == 3:
        ocr = _curve(index, (
            (0, 87.5), (5, 90.2), (9, 88.4), (11, 89.1),
            (12, 80.5), (13, 87.2), (14, 85.3), (15, 85.8),
            (16, 87.4), (18, 89.0), (24, 87.8), (31, 86.6), (35, 88.4),
        ))
        success = _curve(index, (
            (0, 92.4), (5, 94.1), (10, 93.0), (12, 84.0),
            (13, 91.2), (14, 89.0), (15, 89.4), (16, 91.0),
            (18, 93.5), (25, 92.4), (31, 91.6), (35, 93.2),
        ))
        missing = _curve(index, (
            (0, 4.0), (6, 3.2), (11, 4.4), (12, 8.2),
            (13, 7.2), (14, 9.5), (15, 9.0), (16, 7.0),
            (18, 4.6), (26, 5.2), (31, 6.0), (35, 4.2),
        ))
        match = _curve(index, (
            (0, 91.8), (5, 93.4), (10, 92.0), (12, 84.5),
            (13, 86.0), (14, 82.0), (15, 83.0), (16, 87.2),
            (18, 92.4), (25, 90.8), (31, 89.8), (35, 92.0),
        ))
        mismatch = _curve(index, (
            (0, 6.4), (10, 6.8), (12, 13.2), (13, 14.0),
            (14, 15.5), (15, 14.8), (16, 12.8), (18, 7.0),
            (31, 8.4), (35, 6.8),
        ))
        return ocr, success, missing, match, mismatch, 42 + (index * 5) % 9

    if camera_id == 4:
        ocr = _curve(index, (
            (0, 92.2), (5, 90.5), (9, 88.8), (12, 87.0),
            (15, 88.6), (18, 88.0), (22, 87.2), (26, 86.4),
            (29, 88.8), (32, 87.4), (35, 91.4),
        ))
        success = _curve(index, (
            (0, 95.0), (5, 93.8), (9, 92.6), (12, 91.4),
            (15, 93.0), (18, 92.5), (22, 91.8), (26, 91.1),
            (29, 92.8), (32, 92.0), (35, 94.6),
        ))
        missing = _curve(index, (
            (0, 2.6), (5, 4.0), (9, 5.5), (12, 8.6),
            (14, 10.3), (18, 11.2), (22, 12.1), (26, 13.2),
            (29, 10.8), (32, 11.7), (35, 3.2),
        ))
        match = _curve(index, (
            (0, 95.0), (5, 93.8), (9, 92.6), (12, 91.2),
            (15, 93.0), (18, 92.6), (22, 92.0), (26, 91.4),
            (29, 92.8), (32, 92.0), (35, 94.8),
        ))
        mismatch = _curve(index, (
            (0, 4.8), (5, 6.0), (9, 7.2), (12, 8.4),
            (18, 7.0), (26, 8.0), (32, 7.0), (35, 5.0),
        ))
        return ocr, success, missing, match, mismatch, 46 + (index * 2) % 6

    if camera_id == 5:
        ocr = _curve(index, (
            (0, 86.0), (5, 89.8), (7, 87.2), (8, 77.0),
            (9, 72.0), (10, 68.0), (11, 69.0), (12, 70.0),
            (13, 77.5), (15, 88.0), (21, 90.8), (23, 88.8),
            (30, 89.8), (33, 87.8), (35, 90.4),
        ))
        success = _curve(index, (
            (0, 90.8), (5, 92.8), (7, 90.6), (8, 78.0),
            (9, 78.0), (10, 74.0), (11, 75.0), (12, 76.0),
            (13, 81.0), (15, 90.8), (21, 94.2), (23, 90.5),
            (30, 92.0), (35, 90.8),
        ))
        missing = _curve(index, (
            (0, 5.2), (6, 4.0), (8, 17.0), (9, 18.0),
            (10, 19.5), (11, 18.5), (12, 17.8), (13, 14.0),
            (15, 5.0), (24, 4.2), (35, 5.2),
        ))
        match = _curve(index, (
            (0, 91.4), (5, 93.2), (7, 90.8), (8, 79.0),
            (9, 78.0), (10, 82.0), (11, 81.0), (12, 80.0),
            (13, 86.0), (15, 92.0), (21, 94.6), (23, 90.4),
            (30, 92.6), (35, 91.2),
        ))
        mismatch = _curve(index, (
            (0, 8.6), (6, 6.8), (8, 21.0), (9, 22.0),
            (10, 18.0), (11, 19.0), (12, 20.0), (13, 14.0),
            (15, 8.0), (24, 6.6), (35, 8.8),
        ))
        event_count = 3 if 8 <= index <= 12 else 38 + (index * 2) % 6
        return ocr, success, missing, match, mismatch, event_count

    return 90.5, 96.0, 2.6, 96.4, 3.6, 48


def _curve(index: int, points: tuple[tuple[int, float], ...]) -> float:
    for pos, value in points:
        if index == pos:
            return value
    for left, right in zip(points, points[1:]):
        left_pos, left_value = left
        right_pos, right_value = right
        if left_pos <= index <= right_pos:
            ratio = (index - left_pos) / (right_pos - left_pos)
            eased = ratio * ratio * (3 - 2 * ratio)
            return left_value + (right_value - left_value) * eased
    return points[-1][1]


def _naturalize_values(
    camera_id: int,
    index: int,
    bucket_start: datetime,
    values: tuple[float, float, float, float, float, int],
) -> tuple[float, float, float, float, float, int]:
    """Add deterministic correlated variation without hiding the camera scenario."""
    ocr, success, missing, match, mismatch, event_count = values
    cycle_no = (
        (bucket_start.toordinal() * 24 * 60 + bucket_start.hour * 60 + bucket_start.minute)
        // (REFERENCE_BUCKET_MINUTES * DEMO_CURVE_BUCKETS)
    )
    seed = (
        camera_id * 1_000_003
        + index * 9_176
        + cycle_no * 65_537
        + bucket_start.toordinal() * 131
        + bucket_start.hour * 60
        + bucket_start.minute
    ) & 0xFFFFFFFF
    rng = Random(seed)

    scenario_scale = _scenario_noise_scale(camera_id, index)
    shared_wave = sin(index * 0.47 + camera_id * 1.31 + cycle_no * 0.73)
    slow_wave = sin(index * 0.17 + camera_id * 0.91 + cycle_no * 0.41)
    match_wave = sin(index * 0.53 + camera_id * 1.77 + cycle_no * 0.29)

    ocr += (shared_wave * 0.28 + slow_wave * 0.18 + rng.uniform(-0.16, 0.16)) * scenario_scale
    success += (shared_wave * 0.20 + slow_wave * 0.14 + rng.uniform(-0.14, 0.14)) * scenario_scale
    missing += (-shared_wave * 0.18 - slow_wave * 0.08 + rng.uniform(-0.12, 0.12)) * scenario_scale
    match += (match_wave * 0.24 + shared_wave * 0.12 + rng.uniform(-0.14, 0.14)) * scenario_scale
    mismatch += (-match_wave * 0.20 - shared_wave * 0.08 + rng.uniform(-0.12, 0.12)) * scenario_scale
    if event_count > 6:
        event_count = max(0, event_count + rng.choice((-1, 0, 0, 1)))
    else:
        event_count = max(0, event_count + rng.choice((-1, 0, 1)))
    if camera_id == 5 and 8 <= index <= 12:
        event_count = min(event_count, 3)

    return (
        round(_clamp(ocr, 0.0, 100.0), 1),
        round(_clamp(success, 0.0, 100.0), 1),
        round(_clamp(missing, 0.0, 100.0), 1),
        round(_clamp(match, 0.0, 100.0), 1),
        round(_clamp(mismatch, 0.0, 100.0), 1),
        event_count,
    )


def _scenario_noise_scale(camera_id: int, index: int) -> float:
    if camera_id == 2 and index == 13:
        return 0.15
    if _is_scenario_bucket(camera_id, index):
        return 0.45
    return 1.0


def _is_scenario_bucket(camera_id: int, index: int) -> bool:
    return (
        (camera_id == 2 and index in {12, 13, 14})
        or (camera_id == 3 and 12 <= index <= 16)
        or (camera_id == 4 and 14 <= index <= 29)
        or (camera_id == 5 and 8 <= index <= 13)
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))

def _rate(percent: float) -> float:
    return round(percent / 100, 4)


def _window_buckets(
    analysis_end: datetime,
    window_minutes: int,
    bucket_minutes: int,
) -> Iterable[tuple[datetime, datetime, int]]:
    bucket_count = window_minutes // bucket_minutes
    analysis_start = analysis_end - timedelta(minutes=window_minutes)
    for index in range(bucket_count):
        start = analysis_start + timedelta(minutes=bucket_minutes * index)
        yield start, start + timedelta(minutes=bucket_minutes), index


def _post_quality_metrics(
    client: httpx.Client,
    spring_base_url: str,
    settings: Settings,
    analysis_end: datetime,
    window_minutes: int,
) -> int:
    count = 0
    for camera_id, lane_id in parse_targets(settings.targets):
        for bucket_start, bucket_end, _ in _window_buckets(
            analysis_end,
            window_minutes,
            settings.bucket_minutes,
        ):
            response = client.post(
                f"{spring_base_url}/api/v1/pdm/quality-metrics",
                json={
                    "cameraId": camera_id,
                    "laneId": lane_id,
                    "bucketStart": bucket_start.isoformat(),
                    "bucketEnd": bucket_end.isoformat(),
                    **_metric_values(camera_id, bucket_start),
                },
            )
            response.raise_for_status()
            count += 1
    return count


def _post_compare_events(
    client: httpx.Client,
    spring_base_url: str,
    event_end: datetime,
    pass_count: int | None = None,
    recent: bool = False,
) -> int:
    passes = (
        _recent_compare_passes(event_end, pass_count or 2)
        if recent
        else _compare_passes(event_end)
    )
    count = 0
    stamp = event_end.strftime("%Y%m%d%H%M%S%f")
    for (
        sequence,
        lane_id,
        front_camera,
        rear_camera,
        front_plate,
        rear_plate,
        front_conf,
        rear_conf,
        age_seconds,
        rear_delay_seconds,
    ) in passes:
        for role, camera_code, plate, confidence, offset in [
            ("front", front_camera, front_plate, front_conf, 0),
            ("rear", rear_camera, rear_plate, rear_conf, rear_delay_seconds),
        ]:
            needs_review = plate != front_plate or confidence < 0.8
            response = client.post(
                f"{spring_base_url}/api/v1/pdm/passage-events",
                json={
                    "eventUuid": (
                        f"pdm-demo-{stamp}-{sequence:02d}-{lane_id}-{camera_code}-{role}"
                    ),
                    "deviceId": f"demo-device-{camera_code}",
                    "cameraCode": camera_code,
                    "laneId": lane_id,
                    "plateText": plate,
                    "plateConfidence": confidence,
                    "candidateCount": 1 if confidence < 0.75 else 3,
                    "agreementRatio": confidence,
                    "needsReview": needs_review,
                    "eventStatus": "REVIEW" if needs_review else "ACCEPT",
                    "eventTime": (
                        event_end - timedelta(seconds=age_seconds - offset)
                    ).isoformat(),
                },
            )
            if response.status_code != 409:
                response.raise_for_status()
                count += 1
    return count


# 실제 DB에 존재하는 (차로 -> 전방/후방 카메라) 매핑.
# CAM-F-03(5차로)은 후방 카메라가 없어 전후방 비교 대상에서 제외한다.
_COMPARE_LANES = (
    (1, "CAM-F-01", "CAM-R-01"),
    (2, "CAM-F-01", "CAM-R-01"),
    (3, "CAM-F-02", "CAM-R-02"),
    (4, "CAM-F-02", "CAM-R-02"),
)

_PLATE_HANGUL = (
    "가", "나", "다", "라", "마", "거", "너", "더", "러", "머",
    "버", "서", "어", "저", "고", "노", "도", "로", "모", "보",
)

# 우리 OCR이 실제로 헷갈릴 수 있는 숫자 쌍만 모았다.
# (형태가 닮은 숫자끼리만 치환 → "고↔후" 같이 안 닮은 오류는 만들지 않는다)
_OCR_DIGIT_CONFUSIONS = {
    "0": ("8", "6"),
    "1": ("7",),
    "2": ("7",),
    "3": ("8",),
    "4": ("9",),
    "5": ("6",),
    "6": ("8", "5"),
    "7": ("1",),
    "8": ("6", "0", "3"),
    "9": ("4",),
}


def _demo_plate(seed: int) -> str:
    """버킷/차로마다 고정이되 순번처럼 보이지 않는 한국식 번호판.

    우리 OCR이 인식하는 2숫자/3숫자 앞자리를 섞어 더 현실적으로 만든다.
    """
    rng = Random((seed * 2654435761) & 0xFFFFFFFF)
    width = rng.choice((2, 3))
    region = rng.randint(10 ** (width - 1), 10 ** width - 1)
    return f"{region}{rng.choice(_PLATE_HANGUL)}{rng.randint(1000, 9999)}"


def _ocr_misread(plate: str, rng: Random) -> str:
    """원본 번호판에서 시각적으로 닮은 숫자 1~2자만 틀리게 읽은 결과.

    완전히 다른 번호판이 아니라 '같은 차를 OCR이 조금 잘못 읽은' 형태라
    전후방 불일치가 그럴듯하게 보인다.
    """
    chars = list(plate)
    digit_positions = [i for i, ch in enumerate(chars) if ch.isdigit()]
    if not digit_positions:
        return plate

    count = min(rng.choice((1, 2)), len(digit_positions))
    for pos in rng.sample(digit_positions, count):
        options = _OCR_DIGIT_CONFUSIONS.get(chars[pos])
        if options:
            chars[pos] = rng.choice(options)

    corrupted = "".join(chars)
    if corrupted == plate:
        # 우연히 동일하면 한 자리는 반드시 비틀어 불일치를 보장
        for pos in digit_positions:
            options = _OCR_DIGIT_CONFUSIONS.get(chars[pos])
            if options:
                chars[pos] = options[0]
                break
        corrupted = "".join(chars)
    return corrupted


def _compare_pairs(
    analysis_end: datetime,
) -> list[tuple[int, str, str, str, str, float, float]]:
    bucket_start = analysis_end - timedelta(minutes=REFERENCE_BUCKET_MINUTES)
    index = _reference_pattern_index(bucket_start)

    pairs: list[tuple[int, str, str, str, str, float, float]] = []
    for sequence, (lane_id, front_camera, rear_camera) in enumerate(_COMPARE_LANES, start=1):
        pairs.append(_compare_pair(lane_id, front_camera, rear_camera, index, sequence))

    return pairs


def _compare_passes(
    analysis_end: datetime,
) -> list[tuple[int, int, str, str, str, str, float, float, int, int]]:
    bucket_start = analysis_end - timedelta(minutes=REFERENCE_BUCKET_MINUTES)
    index = _reference_pattern_index(bucket_start)
    lane_camera_map = {
        lane_id: (front_camera, rear_camera)
        for lane_id, front_camera, rear_camera in _COMPARE_LANES
    }
    lane_timeline = (
        (2, 18),
        (1, 31),
        (4, 46),
        (3, 64),
        (2, 83),
        (1, 104),
        (4, 126),
        (3, 147),
        (1, 171),
        (2, 194),
        (4, 217),
        (3, 239),
        (2, 262),
        (1, 284),
        (4, 307),
        (3, 329),
    )

    passes: list[tuple[int, int, str, str, str, str, float, float, int, int]] = []
    for sequence, (lane_id, age_seconds) in enumerate(lane_timeline, start=1):
        front_camera, rear_camera = lane_camera_map[lane_id]
        lane_id, front_camera, rear_camera, front_plate, rear_plate, front_conf, rear_conf = (
            _compare_pair(lane_id, front_camera, rear_camera, index, sequence)
        )
        rear_delay_seconds = 2 + (sequence % 3)
        passes.append(
            (
                sequence,
                lane_id,
                front_camera,
                rear_camera,
                front_plate,
                rear_plate,
                front_conf,
                rear_conf,
                age_seconds,
                rear_delay_seconds,
            )
        )
    return passes


def _recent_compare_passes(
    event_end: datetime,
    pass_count: int,
) -> list[tuple[int, int, str, str, str, str, float, float, int, int]]:
    bucket_start = event_end - timedelta(minutes=REFERENCE_BUCKET_MINUTES)
    index = _reference_pattern_index(bucket_start)
    lane_camera_map = {
        lane_id: (front_camera, rear_camera)
        for lane_id, front_camera, rear_camera in _COMPARE_LANES
    }
    patterns = (
        (1, 3),
        (2, 4),
        (1, 4),
        (2, 3),
        (1, 2),
        (3, 4),
    )
    slot = _compare_tick_slot(event_end)
    lane_ids = list(patterns[slot % len(patterns)])
    if pass_count > len(lane_ids):
        rotated = [1, 2, 3, 4]
        start = slot % len(rotated)
        for lane_id in rotated[start:] + rotated[:start]:
            if lane_id not in lane_ids:
                lane_ids.append(lane_id)
            if len(lane_ids) >= pass_count:
                break

    ages = (8, 4, 6, 2)
    passes: list[tuple[int, int, str, str, str, str, float, float, int, int]] = []
    for position, lane_id in enumerate(lane_ids[:max(0, pass_count)], start=1):
        front_camera, rear_camera = lane_camera_map[lane_id]
        sequence = slot * 10 + position
        lane_id, front_camera, rear_camera, front_plate, rear_plate, front_conf, rear_conf = (
            _compare_pair(lane_id, front_camera, rear_camera, index, sequence)
        )
        passes.append(
            (
                sequence,
                lane_id,
                front_camera,
                rear_camera,
                front_plate,
                rear_plate,
                front_conf,
                rear_conf,
                ages[(position - 1) % len(ages)],
                1,
            )
        )
    return passes


def _compare_tick_slot(event_end: datetime) -> int:
    seconds = (
        event_end.toordinal() * 24 * 60 * 60
        + event_end.hour * 60 * 60
        + event_end.minute * 60
        + event_end.second
    )
    return seconds // 10


def _compare_pair(
    lane_id: int,
    front_camera: str,
    rear_camera: str,
    index: int,
    sequence: int,
) -> tuple[int, str, str, str, str, float, float]:
    rng = Random((lane_id * 9973 + index * 131 + sequence * 17) & 0xFFFFFFFF)
    front_plate = _demo_plate(lane_id * 10000 + index * 100 + sequence)
    rear_plate = front_plate
    front_conf = round(0.93 + rng.uniform(-0.04, 0.03), 3)
    rear_conf = round(0.92 + rng.uniform(-0.04, 0.03), 3)

    mismatch = False
    if lane_id == 1 and index == 13:
        # Rear OCR drop scenario.
        mismatch = True
        rear_conf = 0.58
    elif lane_id == 3 and 14 <= index <= 18:
        # Front quality drop scenario.
        mismatch = True
        front_conf = round(0.74 - (index - 14) * 0.015, 3)
        rear_conf = round(0.79 - (index - 14) * 0.02, 3)
    elif lane_id == 4 and index >= 19:
        # Slow rear degradation scenario.
        mismatch = True
        rear_conf = round(0.72 - (index - 19) * 0.02, 3)
    elif sequence == (index % 5) + 5 or (index * 7 + lane_id + sequence) % 19 == 0:
        # Sparse natural OCR mismatch.
        mismatch = True
        rear_conf = round(min(rear_conf, 0.70), 3)

    if mismatch:
        rear_plate = _ocr_misread(front_plate, rng)

    return lane_id, front_camera, rear_camera, front_plate, rear_plate, front_conf, rear_conf
