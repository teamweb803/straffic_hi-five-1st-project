from app.schemas.pdm import IntegratedAnalysis, ModelAnalysisResult, ProcessedMetric

MODEL_WEIGHTS = {
    "RULE_BASED": 0.4,
    "ISOLATION_FOREST": 0.3,
    "LSTM_AE": 0.3,
}


def integrate_results(
    target: ProcessedMetric,
    model_results: list[ModelAnalysisResult],
) -> IntegratedAnalysis:
    anomaly_count = sum(1 for result in model_results if result.is_anomaly)
    representative_score = _weighted_score(model_results)
    representative_risk = _representative_risk(representative_score, model_results)
    return IntegratedAnalysis(
        cameraId=target.camera_id,
        laneId=target.lane_id,
        representativeRiskLevel=representative_risk,
        representativeHealthScore=representative_score,
        anomalyModelCount=anomaly_count,
        modelResults=model_results,
        springSavePayloads=[result.to_spring_payload() for result in model_results],
    )


def _weighted_score(model_results: list[ModelAnalysisResult]) -> float:
    weighted_sum = 0.0
    weight_sum = 0.0
    for result in model_results:
        weight = MODEL_WEIGHTS.get(result.model_type, 1.0)
        weighted_sum += _clamp_score(result.health_score) * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return round(weighted_sum / weight_sum, 1)


def _integrated_risk_from_score(score: float):
    if score >= 80:
        return "NORMAL"
    if score >= 60:
        return "WARNING"
    return "CRITICAL"


def _representative_risk(score: float, model_results: list[ModelAnalysisResult]) -> str:
    score_risk = _integrated_risk_from_score(score)
    risks = [score_risk, *(result.risk_level for result in model_results)]
    return max(risks, key=_risk_rank)


def _risk_rank(risk_level: str) -> int:
    return {
        "NORMAL": 0,
        "WARNING": 1,
        "HIGH": 2,
        "CRITICAL": 3,
    }.get(risk_level, 0)


def _clamp_score(score: float) -> float:
    return max(0.0, min(100.0, score))
