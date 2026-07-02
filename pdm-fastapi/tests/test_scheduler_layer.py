from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.pdm.analysis_job import AnalysisJob
from app.pdm.dedup import DedupStore
from app.pdm.targets import parse_targets
from app.pdm.time_window import (
    compute_analysis_window,
    compute_fetch_window,
    floor_to_bucket,
)
from app.pdm.wire import to_wire_payload
from app.schemas.pdm import QualityMetric
from app.services.spring_pdm_client import SpringPdmClient


# --------------------------------------------------------------------------- #
# 헬퍼
# --------------------------------------------------------------------------- #
def make_settings(**overrides) -> Settings:
    base = dict(
        scheduler_autostart=False,
        targets="1:1,2:1,3:3,4:3,5:5",
        event_count_min=10,
        window_size=6,
        analysis_window_minutes=60,
        fetch_history_minutes=2880,
        bucket_minutes=10,
    )
    base.update(overrides)
    return Settings(**base)


def sample_metric(camera_id: int = 1, lane_id: int = 1) -> QualityMetric:
    return QualityMetric(
        cameraId=camera_id,
        laneId=lane_id,
        bucketStart=datetime(2026, 6, 16, 10, 0, 0),
        bucketEnd=datetime(2026, 6, 16, 10, 10, 0),
        avgOcrConfidence=90.0,
        successRate=95.0,
        missingRate=2.0,
        matchRate=96.0,
        mismatchRate=4.0,
        eventCount=30,
    )


def model_payloads() -> list[dict]:
    """팀원 엔진이 만들어내는 raw payload 모양.

    HIGH / LSTM_AE 포함, 그리고 모델마다 analysisStart가 제각각(실제 버그 모사:
    rule=최신버킷, iforest=fetch시작, lstm=window시작)인 상태를 일부러 만든다.
    """
    common = {
        "cameraId": 1,
        "laneId": 1,
        "analysisEnd": "2026-06-16T10:30:00",
        "healthScore": 70.0,
        "modelVersion": "v1",
        "reasonCode": "X",
        "reasonText": "x",
        "recommendedAction": "x",
        "trendSummary": "x",
    }
    return [
        {**common, "modelType": "RULE_BASED", "riskLevel": "NORMAL",
         "analysisStart": "2026-06-16T10:20:00"},
        {**common, "modelType": "ISOLATION_FOREST", "riskLevel": "HIGH",
         "analysisStart": "2026-06-16T06:30:00"},
        {**common, "modelType": "LSTM_AE", "riskLevel": "WARNING",
         "analysisStart": "2026-06-16T09:30:00"},
    ]


class FakeService:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads
        self.calls = 0

    def analyze(self, request):  # noqa: ANN001 - 테스트 더블
        self.calls += 1
        return [SimpleNamespace(spring_save_payloads=list(self._payloads))]


class FakeClient:
    def __init__(self, metrics: list[QualityMetric]) -> None:
        self._metrics = metrics
        self.saved: list[dict] = []
        self.closed = False

    def fetch_quality_metrics(self, camera_id, lane_id, query_from, query_to):  # noqa: ANN001
        return list(self._metrics)

    def save_analysis_results_resilient(self, payloads):  # noqa: ANN001
        self.saved.extend(payloads)
        return list(payloads), []

    def close(self):
        self.closed = True


# --------------------------------------------------------------------------- #
# 1) 시간 구간 계산 (가이드 §6)
# --------------------------------------------------------------------------- #
def test_floor_to_bucket():
    assert floor_to_bucket(datetime(2026, 6, 16, 10, 37, 12), 10) == datetime(2026, 6, 16, 10, 30)


def test_compute_analysis_window_matches_guide_example():
    # 가이드 예시: 현재 10:37, bucket 10분 -> end 10:30, start 09:30 (window 60)
    start, end = compute_analysis_window(datetime(2026, 6, 16, 10, 37), 10, 60)
    assert end == datetime(2026, 6, 16, 10, 30)
    assert start == datetime(2026, 6, 16, 9, 30)


def test_fetch_window_is_longer_than_analysis_window_for_lstm():
    # LSTM-AE가 연속 window를 확보하도록 조회 history가 분석창보다 길어야 한다.
    _, a_end = compute_analysis_window(datetime(2026, 6, 16, 10, 37), 10, 60)
    f_from, f_to = compute_fetch_window(datetime(2026, 6, 16, 10, 37), 10, 240)
    assert f_to == a_end
    assert (f_to - f_from).total_seconds() / 60 == 240  # 충분한 bucket 수 확보


# --------------------------------------------------------------------------- #
# 2) 대상 파싱
# --------------------------------------------------------------------------- #
def test_parse_targets():
    assert parse_targets("1:1,1:2, 2:1 ") == [(1, 1), (1, 2), (2, 1)]


def test_parse_targets_skips_invalid():
    assert parse_targets("1:1,bad,3,4:x,2:2") == [(1, 1), (2, 2)]


# --------------------------------------------------------------------------- #
# 3) enum 경계 매핑 (Spring DB 계약)
# --------------------------------------------------------------------------- #
def test_wire_maps_high_to_critical_and_keeps_lstm_ae():
    settings = make_settings()
    high = to_wire_payload({"riskLevel": "HIGH", "modelType": "ISOLATION_FOREST"}, settings)
    lstm = to_wire_payload({"riskLevel": "WARNING", "modelType": "LSTM_AE"}, settings)
    assert high["riskLevel"] == "CRITICAL"
    assert lstm["modelType"] == "LSTM_AE"


def test_wire_overrides_window_to_official():
    settings = make_settings()
    wired = to_wire_payload(
        {
            "riskLevel": "NORMAL", "modelType": "RULE_BASED",
            "analysisStart": "2026-06-16T10:20:00", "analysisEnd": "2026-06-16T10:30:00",
        },
        settings,
        analysis_start=datetime(2026, 6, 16, 9, 30),
        analysis_end=datetime(2026, 6, 16, 10, 30),
    )
    assert wired["analysisStart"] == "2026-06-16T09:30:00"  # 공식 window로 덮어씀
    assert wired["analysisEnd"] == "2026-06-16T10:30:00"


def test_wire_serializes_datetime_to_iso():
    settings = make_settings()
    wired = to_wire_payload(
        {"analysisStart": datetime(2026, 6, 16, 9, 30), "analysisEnd": datetime(2026, 6, 16, 10, 30)},
        settings,
    )
    assert wired["analysisStart"] == "2026-06-16T09:30:00"
    assert isinstance(wired["analysisEnd"], str)


# --------------------------------------------------------------------------- #
# 4) 중복 방지 (재시작 내성 포함)
# --------------------------------------------------------------------------- #
def test_dedup_seen_and_mark():
    store = DedupStore(":memory:")
    payload = model_payloads()[0]
    assert store.seen(payload) is False
    store.mark(payload)
    assert store.seen(payload) is True


def test_dedup_persists_across_restart(tmp_path):
    db = str(tmp_path / "dedup.sqlite3")
    payload = model_payloads()[0]

    store1 = DedupStore(db)
    store1.mark(payload)
    store1.close()

    # 새 인스턴스(서버 재시작 시나리오)에서도 기억해야 한다.
    store2 = DedupStore(db)
    assert store2.seen(payload) is True


# --------------------------------------------------------------------------- #
# 5) 분석 Job (전 흐름 + 중복 방지)
# --------------------------------------------------------------------------- #
def test_analysis_job_runs_three_models_and_wires_payloads():
    fake_client = FakeClient([sample_metric()])
    job = AnalysisJob(
        settings=make_settings(targets="1:1"),
        service=FakeService(model_payloads()),
        client_factory=lambda: fake_client,
        dedup=DedupStore(":memory:"),
        now_fn=lambda: datetime(2026, 6, 16, 10, 37),
    )

    summary = job.run_once()

    assert summary["status"] == "DONE"
    assert summary["savedCount"] == 3
    saved_models = {p["modelType"] for p in fake_client.saved}
    assert saved_models == {"RULE_BASED", "ISOLATION_FOREST", "LSTM_AE"}
    risk_by_model = {p["modelType"]: p["riskLevel"] for p in fake_client.saved}
    assert risk_by_model["ISOLATION_FOREST"] == "CRITICAL"  # HIGH -> CRITICAL
    # 모델별로 달랐던 분석 구간이 공식 window(09:30~10:30)로 통일되어야 한다
    assert {p["analysisStart"] for p in fake_client.saved} == {"2026-06-16T09:30:00"}
    assert {p["analysisEnd"] for p in fake_client.saved} == {"2026-06-16T10:30:00"}
    assert fake_client.closed is True


def test_analysis_job_dedup_on_second_run():
    dedup = DedupStore(":memory:")
    service = FakeService(model_payloads())

    def run():
        return AnalysisJob(
            settings=make_settings(targets="1:1"),
            service=service,
            client_factory=lambda: FakeClient([sample_metric()]),
            dedup=dedup,
            now_fn=lambda: datetime(2026, 6, 16, 10, 37),
        ).run_once()

    first = run()
    second = run()

    assert first["savedCount"] == 3
    assert second["savedCount"] == 0
    assert second["duplicateSkippedCount"] == 3


def test_analysis_job_skips_when_already_running():
    job = AnalysisJob(
        settings=make_settings(targets="1:1"),
        service=FakeService(model_payloads()),
        client_factory=lambda: FakeClient([sample_metric()]),
        dedup=DedupStore(":memory:"),
        now_fn=lambda: datetime(2026, 6, 16, 10, 37),
    )
    job._lock.acquire()  # 이전 Job이 실행 중인 상황을 모사
    try:
        result = job.run_once()
    finally:
        job._lock.release()
    assert result["status"] == "SKIPPED"


def test_analysis_job_handles_no_data():
    job = AnalysisJob(
        settings=make_settings(targets="1:1"),
        service=FakeService(model_payloads()),
        client_factory=lambda: FakeClient([]),  # 빈 응답
        dedup=DedupStore(":memory:"),
        now_fn=lambda: datetime(2026, 6, 16, 10, 37),
    )
    summary = job.run_once()
    assert summary["savedCount"] == 0
    assert summary["noDataTargets"] == [{"cameraId": 1, "laneId": 1}]


def test_scheduler_seeds_demo_data_before_scheduled_analysis(monkeypatch):
    from app.pdm.scheduler import PdmScheduler

    analysis_end = datetime(2026, 6, 16, 10, 40)

    class FakeJob:
        settings = make_settings(demo_seed_enabled=True)

        def __init__(self) -> None:
            self.calls = []

        def status_snapshot(self):
            return {"running": False}

        def run_once(self, now_override=None):  # noqa: ANN001
            self.calls.append(now_override)
            return {"status": "DONE"}

    fake_job = FakeJob()
    monkeypatch.setattr(
        "app.pdm.scheduler.prepare_demo_run",
        lambda job: (analysis_end, {"analysisEnd": analysis_end.isoformat(), "qualityMetricCount": 30, "passageEventCount": 4}),
    )

    scheduler = PdmScheduler(job=fake_job, settings=make_settings(demo_seed_enabled=True))
    scheduler._run_scheduled_analysis()

    assert fake_job.calls == [analysis_end]


def test_scheduler_can_run_without_demo_seed():
    from app.pdm.scheduler import PdmScheduler

    class FakeJob:
        def __init__(self) -> None:
            self.calls = []

        def run_once(self, now_override=None):  # noqa: ANN001
            self.calls.append(now_override)
            return {"status": "DONE"}

    fake_job = FakeJob()
    scheduler = PdmScheduler(job=fake_job, settings=make_settings(demo_seed_enabled=False))
    scheduler._run_scheduled_analysis()

    assert fake_job.calls == [None]


def test_scheduler_runs_compare_events_on_short_tick(monkeypatch):
    from app.pdm.scheduler import PdmScheduler

    now = datetime(2026, 6, 16, 20, 27, 30)
    calls = []

    class FakeJob:
        def now_fn(self):
            return now

    monkeypatch.setattr(
        "app.pdm.scheduler.seed_compare_events",
        lambda settings, event_end, pass_count: calls.append((settings, event_end, pass_count)) or {
            "eventEnd": event_end.isoformat(),
            "passageEventCount": 4,
        },
    )

    settings = make_settings(
        demo_seed_enabled=True,
        compare_event_interval_seconds=10,
        compare_passes_per_tick=2,
    )
    scheduler = PdmScheduler(job=FakeJob(), settings=settings)
    result = scheduler._run_scheduled_compare_events()

    assert result["passageEventCount"] == 4
    assert calls == [(settings, now, 2)]


def test_demo_refresh_metrics_follow_reference_camera_patterns():
    from app.pdm.demo_refresh import _metric_values

    cam1_start = _metric_values(1, datetime(2026, 6, 16, 9, 0))
    assert _metric_values(1, datetime(2026, 6, 16, 9, 0)) == cam1_start
    assert 0.90 <= cam1_start["avgOcrConfidence"] <= 0.91
    assert 0.95 <= cam1_start["successRate"] <= 0.97
    assert 0.02 <= cam1_start["missingRate"] <= 0.04
    cam1_series = [
        _metric_values(1, datetime(2026, 6, 16, 9, 0) + timedelta(minutes=10 * idx))
        for idx in range(12)
    ]
    assert len({m["avgOcrConfidence"] for m in cam1_series}) >= 6

    rear_spike = _metric_values(2, datetime(2026, 6, 16, 11, 10))
    assert rear_spike["avgOcrConfidence"] < 0.50
    assert rear_spike["successRate"] < 0.60
    assert rear_spike["matchRate"] < 0.60

    # camera3: Isolation Forest 예시 — 각 지표는 정상범위인데 짧은 구간의 '조합'만 비정상인 다변량 이상치
    cam3_normal = _metric_values(3, datetime(2026, 6, 16, 12, 0))      # index 18 (정상)
    cam3_outlier = _metric_values(3, datetime(2026, 6, 16, 11, 20))    # index 14 (단기 이상 시작)
    cam3_outlier_next = _metric_values(3, datetime(2026, 6, 16, 11, 30))  # index 15 (단기 이상 지속)
    assert cam3_normal["avgOcrConfidence"] >= 0.85 and cam3_normal["mismatchRate"] <= 0.10
    # OCR·성공률은 정상인데 누락·불일치 조합이 평소 상관을 깨고 2버킷 이어진다 → 단기 다변량 이상치
    assert cam3_outlier["avgOcrConfidence"] >= 0.85 and cam3_outlier["successRate"] >= 0.85
    assert cam3_outlier["mismatchRate"] > 0.15
    assert cam3_outlier_next["avgOcrConfidence"] >= 0.85 and cam3_outlier_next["successRate"] >= 0.85
    assert cam3_outlier_next["missingRate"] > 0.08

    # camera4: LSTM-AE 예시 — 느린 지속 드리프트. 누락률이 임계 부근으로 '지속적으로' 올라가지만
    # OCR 등은 정상범위에 머물러, 점 단위(Rule/IF)로는 또렷하지 않고 추세(LSTM)로만 드러난다.
    cam4_normal = _metric_values(4, datetime(2026, 6, 16, 9, 0))       # index 0
    assert cam4_normal["avgOcrConfidence"] >= 0.90 and cam4_normal["missingRate"] <= 0.05
    block = [
        _metric_values(4, datetime(2026, 6, 16, (540 + 10 * idx) // 60, (540 + 10 * idx) % 60))
        for idx in range(11, 21)
    ]
    avg_ocr = sum(m["avgOcrConfidence"] for m in block) / len(block)
    avg_missing = sum(m["missingRate"] for m in block) / len(block)
    assert avg_missing > 0.10   # 누락률이 지속적으로 임계 위
    assert avg_ocr >= 0.85      # OCR은 정상범위 → 개별 버킷은 정상처럼 보임

    low_traffic = _metric_values(5, datetime(2026, 6, 16, 10, 30))
    assert low_traffic["eventCount"] <= 3
    assert 0.70 <= low_traffic["avgOcrConfidence"] <= 0.73


def test_demo_refresh_compare_pairs_follow_reference_scenarios():
    import re

    from app.pdm.demo_refresh import _compare_pairs

    plate_re = re.compile(r"^\d{2,3}[가-힣]\d{4}$")

    def lane(pairs, lane_id):
        return next(p for p in pairs if p[0] == lane_id)

    # 실제 DB에 매핑된 차로 1~4만 전후방 비교 대상이다.
    normal_pairs = _compare_pairs(datetime(2026, 6, 16, 10, 10))  # index 6
    assert [p[0] for p in normal_pairs] == [1, 2, 3, 4]
    for _, front_cam, rear_cam, front_plate, rear_plate, front_conf, rear_conf in normal_pairs:
        assert front_cam.startswith("CAM-F-") and rear_cam.startswith("CAM-R-")
        assert plate_re.match(front_plate) and plate_re.match(rear_plate)
        # 번호판이 순번처럼 증가하지 않는다 (시드 기반 난수)
        assert not front_plate.startswith("12A")

    def assert_near_miss(front_plate, rear_plate):
        # 불일치는 완전히 다른 번호판이 아니라 1~2자만 틀린 OCR 오인식이어야 한다.
        assert front_plate != rear_plate
        assert len(front_plate) == len(rear_plate)
        diff = [(a, b) for a, b in zip(front_plate, rear_plate) if a != b]
        assert 1 <= len(diff) <= 2
        # 틀린 자리는 숫자 ↔ 닮은 숫자 치환뿐 (한글 위치는 그대로)
        for a, b in diff:
            assert a.isdigit() and b.isdigit()

    # 후방 OCR 급락 시나리오: 1차로 전후방 불일치 + 후방 신뢰도 0.58
    rear_spike = lane(_compare_pairs(datetime(2026, 6, 16, 11, 20)), 1)  # index 13
    assert_near_miss(rear_spike[3], rear_spike[4])
    assert rear_spike[6] == 0.58

    # 전방 카메라 품질 저하 시나리오: 3차로 전후방 불일치 + 전방 신뢰도 0.71
    front_drop = lane(_compare_pairs(datetime(2026, 6, 16, 11, 50)), 3)  # index 16
    assert_near_miss(front_drop[3], front_drop[4])
    assert front_drop[5] == 0.71


def test_demo_refresh_compare_passes_are_dense_but_not_round_robin():
    from app.pdm.demo_refresh import _compare_passes

    passes = _compare_passes(datetime(2026, 6, 16, 10, 10))
    lane_ids = [item[1] for item in passes]
    ages = [item[8] for item in passes]

    assert len(passes) == 16
    assert lane_ids == [2, 1, 4, 3, 2, 1, 4, 3, 1, 2, 4, 3, 2, 1, 4, 3]
    assert ages == sorted(ages)
    assert max(ages) - min(ages) < 330
    assert any(item[4] != item[5] for item in passes)

    for lane_id in {1, 2, 3, 4}:
        lane_ages = [age for lane, age in zip(lane_ids, ages) if lane == lane_id]
        assert all(
            later - earlier > 10
            for earlier, later in zip(lane_ages, lane_ages[1:])
        )


def test_next_demo_analysis_end_never_moves_past_current_bucket():
    from app.pdm.demo_refresh import next_demo_analysis_end

    class FakeJob:
        settings = make_settings(bucket_minutes=10)

        def now_fn(self):
            return datetime(2026, 6, 16, 20, 27, 30)

        def status_snapshot(self):
            return {
                "lastSummary": {
                    "analysisEnd": "2026-06-16T21:20:00",
                }
            }

    assert next_demo_analysis_end(FakeJob()) == datetime(2026, 6, 16, 20, 20)


def test_seed_compare_events_uses_current_time_and_small_batch(monkeypatch):
    from app.pdm import demo_refresh

    event_end = datetime(2026, 6, 16, 20, 27, 30)
    posted = []

    class FakeResp:
        status_code = 201

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):  # noqa: A002
            posted.append((url, json))
            return FakeResp()

    monkeypatch.setattr(demo_refresh.httpx, "Client", FakeClient)

    demo_refresh.seed_compare_events(
        make_settings(targets="1:1", bucket_minutes=10),
        event_end,
        pass_count=2,
    )

    passage_events = [
        payload for url, payload in posted if url.endswith("/api/v1/pdm/passage-events")
    ]
    event_times = [datetime.fromisoformat(payload["eventTime"]) for payload in passage_events]

    assert len(passage_events) == 4
    assert max(event_times) <= event_end
    assert min(event_times) >= event_end - timedelta(seconds=10)


def test_backfill_quality_history_fills_missing_buckets(monkeypatch):
    from app.pdm import demo_refresh

    posted = []

    class FakeResp:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):  # noqa: A002
            posted.append(json)
            return FakeResp()

    monkeypatch.setattr(demo_refresh.httpx, "Client", FakeClient)

    settings = make_settings(targets="1:1", bucket_minutes=10)
    count = demo_refresh.backfill_quality_history(
        settings, datetime(2026, 6, 16, 10, 5), minutes=30
    )

    # 10:00로 floor → 09:30/09:40/09:50 3개 버킷 × 타깃 1개
    assert count == 3
    assert [p["bucketStart"] for p in posted] == [
        "2026-06-16T09:30:00",
        "2026-06-16T09:40:00",
        "2026-06-16T09:50:00",
    ]
    assert all(0.0 <= p["matchRate"] <= 1.0 for p in posted)


# --------------------------------------------------------------------------- #
# 6) Spring 클라이언트: 부분 실패 내성 + 409 처리 + 재시도
# --------------------------------------------------------------------------- #
def test_resilient_save_continues_after_failure_and_treats_409_as_saved():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        if '"ISOLATION_FOREST"' in body:
            return httpx.Response(500, json={"error": "boom"})   # 영구 실패
        if '"LSTM_AE"' in body:
            return httpx.Response(409, json={"error": "exists"})  # 중복 -> 성공 취급
        return httpx.Response(200, json={"success": True})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://spring.test", transport=transport)
    client = SpringPdmClient(
        base_url="http://spring.test",
        http_client=http_client,
        max_retries=1,
        retry_backoff_seconds=0,  # 테스트 지연 방지
    )

    payloads = [
        {"cameraId": 1, "laneId": 1, "modelType": "RULE_BASED"},
        {"cameraId": 1, "laneId": 1, "modelType": "ISOLATION_FOREST"},
        {"cameraId": 1, "laneId": 1, "modelType": "LSTM_AE"},
    ]
    saved, failed = client.save_analysis_results_resilient(payloads)

    saved_models = {p["modelType"] for p in saved}
    failed_models = {p["modelType"] for p in failed}
    assert saved_models == {"RULE_BASED", "LSTM_AE"}     # 409 포함 성공 취급
    assert failed_models == {"ISOLATION_FOREST"}          # 500은 실패


def test_fetch_retries_then_succeeds():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, json={"error": "unavailable"})  # 첫 시도 5xx
        return httpx.Response(
            200,
            json={"success": True, "message": "ok", "data": [
                {
                    "cameraId": 2, "laneId": 1,
                    "bucketStart": "2026-06-16T10:00:00", "bucketEnd": "2026-06-16T10:05:00",
                    "avgOcrConfidence": 91.0, "successRate": 94.0, "missingRate": 2.0,
                    "matchRate": 96.0, "mismatchRate": 4.0, "eventCount": 20,
                }
            ]},
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://spring.test", transport=transport)
    client = SpringPdmClient(
        base_url="http://spring.test", http_client=http_client,
        max_retries=2, retry_backoff_seconds=0,
    )

    metrics = client.fetch_quality_metrics(camera_id=2)
    assert attempts["n"] == 2          # 1회 재시도 후 성공
    assert len(metrics) == 1
    assert metrics[0].camera_id == 2


# --------------------------------------------------------------------------- #
# 7) run-once 엔드포인트: 짧은 ack + 백그라운드 실행
# --------------------------------------------------------------------------- #
def test_run_once_endpoint_returns_started_ack(monkeypatch):
    from app.pdm import runtime

    job = runtime.get_analysis_job()
    calls = []
    monkeypatch.setattr(job, "run_once", lambda: calls.append(1) or {"status": "DONE"})

    # with 미사용 -> lifespan(스케줄러)은 동작하지 않음. BackgroundTask는 응답 후 실행됨.
    client = TestClient(app)
    response = client.post("/internal/pdm/run-once")

    assert response.status_code == 200
    assert response.json() == {"status": "STARTED", "message": "PDM analysis job started"}
    assert calls == [1]
