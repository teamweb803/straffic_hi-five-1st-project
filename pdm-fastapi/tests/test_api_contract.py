import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_quality_metrics_analyze_api_returns_spring_payloads():
    request_path = Path("samples/analyze_request_rear_degraded.json")
    payload = json.loads(request_path.read_text(encoding="utf-8"))

    response = TestClient(app).post("/analysis/v1/pdm/quality-metrics/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    result = body["data"][0]
    assert result["representativeRiskLevel"] in {"NORMAL", "WARNING", "HIGH", "CRITICAL"}
    assert {item["modelType"] for item in result["modelResults"]} == {
        "RULE_BASED",
        "ISOLATION_FOREST",
        "LSTM_AE",
    }
    assert {item["modelType"] for item in result["springSavePayloads"]} == {
        "RULE_BASED",
        "ISOLATION_FOREST",
        "LSTM_AE",
    }
    for item in result["springSavePayloads"]:
        assert "isAnomaly" not in item
        assert "debug" not in item


def test_health_score_uses_requested_event_count_min():
    payload = {
        "eventCountMin": 30,
        "metric": {
            "cameraId": 2,
            "laneId": 1,
            "bucketStart": "2026-06-16T10:00:00",
            "bucketEnd": "2026-06-16T10:05:00",
            "avgOcrConfidence": 92.0,
            "successRate": 95.0,
            "missingRate": 2.0,
            "matchRate": 96.0,
            "mismatchRate": 4.0,
            "eventCount": 20,
        },
    }

    response = TestClient(app).post("/analysis/v1/pdm/health-score", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["debug"]["eventCountValid"] is False
