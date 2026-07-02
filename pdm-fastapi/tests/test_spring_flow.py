import httpx

from app.services.spring_pdm_client import SpringPdmClient


def test_spring_client_fetches_metrics_and_saves_payloads():
    saved_payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/api/v1/pdm/cameras/2/quality-metrics"
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "ok",
                    "data": [
                        {
                            "cameraId": 2,
                            "laneId": 1,
                            "bucketStart": "2026-06-16T10:00:00",
                            "bucketEnd": "2026-06-16T10:05:00",
                            "avgOcrConfidence": 91.0,
                            "successRate": 94.0,
                            "missingRate": 2.0,
                            "matchRate": 96.0,
                            "mismatchRate": 4.0,
                            "eventCount": 20,
                        }
                    ],
                },
            )
        if request.method == "POST":
            assert request.url.path == "/api/v1/pdm/analysis-results"
            saved_payloads.append(request.read())
            return httpx.Response(200, json={"success": True, "data": {"saved": True}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://spring.test", transport=transport)
    client = SpringPdmClient(base_url="http://spring.test", http_client=http_client)

    metrics = client.fetch_quality_metrics(camera_id=2)
    responses = client.save_analysis_results(
        [
            {
                "cameraId": 2,
                "laneId": 1,
                "analysisStart": "2026-06-16T10:00:00",
                "analysisEnd": "2026-06-16T10:05:00",
                "healthScore": 90.0,
                "riskLevel": "NORMAL",
                "modelType": "RULE_BASED",
                "modelVersion": "rule-v1",
                "reasonCode": "NORMAL_QUALITY",
                "reasonText": "정상",
                "recommendedAction": "정기 점검",
                "trendSummary": "정상",
            }
        ]
    )

    assert len(metrics) == 1
    assert metrics[0].camera_id == 2
    assert len(saved_payloads) == 1
    assert responses[0]["success"] is True
