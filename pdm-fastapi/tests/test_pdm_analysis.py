from datetime import datetime, timedelta

from app.analyzers.integration import integrate_results
from app.pdm.demo_refresh import _metric_values
from app.scenarios.demo_scenarios import build_demo_metrics
from app.schemas.pdm import AnalyzeRequest, DemoScenarioRequest, ModelAnalysisResult, ProcessedMetric, QualityMetric
from app.services.pdm_analysis_service import PdmAnalysisService


def test_all_three_model_results_are_generated():
    metrics = build_demo_metrics(
        DemoScenarioRequest(
            scenarioType="REAR_DEGRADED",
            startTime=datetime(2026, 6, 16, 10, 0, 0),
            durationMinutes=60,
        )
    )
    result = PdmAnalysisService().analyze(AnalyzeRequest(metrics=metrics))

    assert len(result) == 1
    model_types = {item.model_type for item in result[0].model_results}
    assert model_types == {"RULE_BASED", "ISOLATION_FOREST", "LSTM_AE"}
    assert len(result[0].spring_save_payloads) == 3


def test_match_rate_is_not_used_as_model_feature():
    metrics = build_demo_metrics(
        DemoScenarioRequest(
            scenarioType="NORMAL",
            startTime=datetime(2026, 6, 16, 10, 0, 0),
            durationMinutes=60,
        )
    )
    result = PdmAnalysisService().analyze(AnalyzeRequest(metrics=metrics))[0]
    iforest = [item for item in result.model_results if item.model_type == "ISOLATION_FOREST"][0]
    assert "matchRate" not in iforest.debug["features"]


def test_spring_save_payloads_do_not_include_internal_fields():
    metrics = build_demo_metrics(
        DemoScenarioRequest(
            scenarioType="REAR_DEGRADED",
            startTime=datetime(2026, 6, 16, 10, 0, 0),
            durationMinutes=60,
        )
    )
    result = PdmAnalysisService().analyze(AnalyzeRequest(metrics=metrics))[0]

    for payload in result.spring_save_payloads:
        assert "isAnomaly" not in payload
        assert "debug" not in payload


def test_period_analysis_uses_worst_bucket_not_last_bucket():
    metrics = [
        QualityMetric(
            cameraId=1,
            laneId=1,
            bucketStart=datetime(2026, 6, 16, 10, 0, 0),
            bucketEnd=datetime(2026, 6, 16, 10, 10, 0),
            avgOcrConfidence=70.0,
            successRate=76.0,
            missingRate=18.0,
            matchRate=78.0,
            mismatchRate=22.0,
            eventCount=4,
        ),
        QualityMetric(
            cameraId=1,
            laneId=1,
            bucketStart=datetime(2026, 6, 16, 10, 10, 0),
            bucketEnd=datetime(2026, 6, 16, 10, 20, 0),
            avgOcrConfidence=92.0,
            successRate=96.0,
            missingRate=2.0,
            matchRate=96.0,
            mismatchRate=4.0,
            eventCount=30,
        ),
    ]

    result = PdmAnalysisService().analyze(AnalyzeRequest(metrics=metrics))[0]
    rule_based = [item for item in result.model_results if item.model_type == "RULE_BASED"][0]

    assert rule_based.analysis_start == datetime(2026, 6, 16, 10, 0, 0)
    assert rule_based.reason_code != "NORMAL_QUALITY"


def test_integrated_result_keeps_weighted_score_but_surfaces_model_warning():
    target = ProcessedMetric(
        cameraId=5,
        laneId=5,
        bucketStart=datetime(2026, 6, 18, 22, 30, 0),
        bucketEnd=datetime(2026, 6, 18, 23, 30, 0),
        avgOcrConfidence=84.2,
        successRate=87.9,
        missingRate=7.8,
        matchRate=89.5,
        mismatchRate=10.5,
        eventCount=5,
        eventCountValid=False,
    )
    model_results = [
        _model_result("RULE_BASED", 70.0, "WARNING"),
        _model_result("ISOLATION_FOREST", 79.9, "WARNING"),
        _model_result("LSTM_AE", 100.0, "NORMAL"),
    ]

    result = integrate_results(target, model_results)

    assert result.representative_health_score == 82.0
    assert result.representative_risk_level == "WARNING"
    assert result.anomaly_model_count == 2


def test_integrated_result_collapses_low_weighted_score_to_critical():
    target = ProcessedMetric(
        cameraId=2,
        laneId=1,
        bucketStart=datetime(2026, 6, 18, 22, 30, 0),
        bucketEnd=datetime(2026, 6, 18, 23, 30, 0),
        avgOcrConfidence=88.2,
        successRate=92.5,
        missingRate=4.3,
        matchRate=92.5,
        mismatchRate=7.5,
        eventCount=48,
        eventCountValid=True,
    )
    model_results = [
        _model_result("RULE_BASED", 10.4, "CRITICAL"),
        _model_result("ISOLATION_FOREST", 72.0, "WARNING"),
        _model_result("LSTM_AE", 100.0, "NORMAL"),
    ]

    result = integrate_results(target, model_results)

    assert result.representative_health_score == 55.8
    assert result.representative_risk_level == "CRITICAL"


def test_demo_model_examples_separate_short_and_long_anomalies():
    cam1 = _demo_model_results(camera_id=1, lane_id=1)
    cam2 = _demo_model_results(camera_id=2, lane_id=1)
    cam3 = _demo_model_results(camera_id=3, lane_id=3)
    cam4 = _demo_model_results(camera_id=4, lane_id=3)

    assert _model(cam1, "RULE_BASED").risk_level == "NORMAL"
    assert _model(cam1, "ISOLATION_FOREST").risk_level == "NORMAL"
    assert _model(cam1, "LSTM_AE").risk_level == "NORMAL"

    assert _model(cam2, "RULE_BASED").risk_level == "CRITICAL"
    assert _model(cam2, "LSTM_AE").risk_level == "NORMAL"

    assert _model(cam3, "RULE_BASED").risk_level == "NORMAL"
    assert _model(cam3, "ISOLATION_FOREST").risk_level == "WARNING"
    assert _model(cam3, "LSTM_AE").risk_level == "NORMAL"

    assert _model(cam4, "RULE_BASED").risk_level == "NORMAL"
    assert _model(cam4, "ISOLATION_FOREST").risk_level == "NORMAL"
    assert _model(cam4, "LSTM_AE").risk_level == "WARNING"


def _demo_model_results(camera_id: int, lane_id: int) -> list[ModelAnalysisResult]:
    start = datetime(2026, 6, 16, 9, 0, 0)
    metrics = []
    for index in range(36):
        bucket_start = start + timedelta(minutes=10 * index)
        values = _metric_values(camera_id, bucket_start)
        metrics.append(
            QualityMetric(
                cameraId=camera_id,
                laneId=lane_id,
                bucketStart=bucket_start,
                bucketEnd=bucket_start + timedelta(minutes=10),
                avgOcrConfidence=values["avgOcrConfidence"],
                successRate=values["successRate"],
                missingRate=values["missingRate"],
                matchRate=values["matchRate"],
                mismatchRate=values["mismatchRate"],
                eventCount=values["eventCount"],
            )
        )
    return PdmAnalysisService().analyze(AnalyzeRequest(metrics=metrics))[0].model_results


def _model(results: list[ModelAnalysisResult], model_type: str) -> ModelAnalysisResult:
    return next(result for result in results if result.model_type == model_type)


def _model_result(model_type: str, health_score: float, risk_level: str) -> ModelAnalysisResult:
    return ModelAnalysisResult(
        cameraId=1,
        laneId=1,
        analysisStart=datetime(2026, 6, 18, 22, 30, 0),
        analysisEnd=datetime(2026, 6, 18, 23, 30, 0),
        healthScore=health_score,
        riskLevel=risk_level,
        modelType=model_type,
        modelVersion="test",
        reasonCode="TEST",
        reasonText="test",
        recommendedAction="test",
        trendSummary="test",
        isAnomaly=risk_level != "NORMAL",
    )
