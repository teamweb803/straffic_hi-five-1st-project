"""실제 분석 엔진으로 스케줄러 Job 전 흐름을 검증하는 스모크 테스트.

가짜 Spring 서버(httpx MockTransport)에 24개 bucket(4시간)을 넣고,
실제 PdmAnalysisService(rule_based/isolation_forest/lstm_ae)를 돌려
저장 직전 payload를 확인한다.

확인 포인트:
  1) LSTM-AE가 INSUFFICIENT_SEQUENCE(가짜 WARNING)를 내지 않는다 (history 충분).
  2) 저장 payload의 modelType에 LSTM_AE가 없고 LSTM만 있다.
  3) 저장 payload의 riskLevel에 HIGH가 없다(HIGH -> CRITICAL).
  4) analysisStart/analysisEnd가 ISO 문자열로 직렬화된다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx

from app.config import Settings
from app.pdm.analysis_job import AnalysisJob
from app.pdm.dedup import DedupStore
from app.services.spring_pdm_client import SpringPdmClient


def build_metrics() -> list[dict]:
    base = datetime(2026, 6, 16, 6, 30, 0)
    rows = []
    for i in range(24):  # 4시간치(10분 bucket)
        start = base + timedelta(minutes=10 * i)
        if i == 23:
            # 마지막 구간만 뚜렷하게 저하 -> rule-based 점수 ~55(HIGH) 유도
            conf, success, missing, mismatch = 60.0, 70.0, 20.0, 30.0
        else:
            conf, success, missing, mismatch = 94.0, 96.0, 2.0, 3.5
        rows.append({
            "cameraId": 1, "laneId": 1,
            "bucketStart": start.isoformat(),
            "bucketEnd": (start + timedelta(minutes=10)).isoformat(),
            "avgOcrConfidence": conf, "successRate": success,
            "missingRate": missing, "matchRate": 100 - mismatch,
            "mismatchRate": mismatch, "eventCount": 30,
        })
    return rows


def main() -> int:
    metrics = build_metrics()
    saved_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"success": True, "message": "ok", "data": metrics})
        if request.method == "POST":
            saved_payloads.append(json.loads(request.read().decode()))
            return httpx.Response(200, json={"success": True, "data": {"saved": True}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    settings = Settings(
        scheduler_autostart=False,
        targets="1:1",
        analysis_window_minutes=60,
        fetch_history_minutes=240,
        bucket_minutes=10,
        window_size=6,
        event_count_min=10,
    )

    def client_factory() -> SpringPdmClient:
        http_client = httpx.Client(base_url="http://spring.test", transport=transport)
        return SpringPdmClient(base_url="http://spring.test", http_client=http_client)

    job = AnalysisJob(
        settings=settings,
        client_factory=client_factory,
        dedup=DedupStore(":memory:"),
        now_fn=lambda: datetime(2026, 6, 16, 10, 37),
    )

    summary = job.run_once()

    print("=== JOB SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== SAVED PAYLOADS (실제 엔진 출력 -> 경계 매핑 후) ===")
    for p in saved_payloads:
        print(f"- {p['modelType']:<16} risk={p['riskLevel']:<9} "
              f"score={p['healthScore']:<6} reason={p['reasonCode']:<22} "
              f"start={p['analysisStart']}")

    # --- 검증 ---
    model_types = {p["modelType"] for p in saved_payloads}
    risk_levels = {p["riskLevel"] for p in saved_payloads}
    reason_codes = {p["reasonCode"] for p in saved_payloads}
    starts = {p["analysisStart"] for p in saved_payloads}
    ends = {p["analysisEnd"] for p in saved_payloads}

    checks = {
        "1) LSTM_AE 미사용(LSTM만)": "LSTM_AE" not in model_types and "LSTM" in model_types,
        "2) HIGH 미사용": "HIGH" not in risk_levels,
        "3) LSTM INSUFFICIENT_SEQUENCE 아님": "INSUFFICIENT_SEQUENCE" not in reason_codes,
        "4) analysisStart ISO 문자열": all(isinstance(p["analysisStart"], str) for p in saved_payloads),
        "5) 3개 모델 모두 저장": len(saved_payloads) == 3,
        "6) 분석 구간 공식 window로 통일": starts == {"2026-06-16T09:30:00"} and ends == {"2026-06-16T10:30:00"},
    }
    print("\n=== CHECKS ===")
    ok = True
    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print(f"\nmodelTypes={model_types} riskLevels={risk_levels}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
