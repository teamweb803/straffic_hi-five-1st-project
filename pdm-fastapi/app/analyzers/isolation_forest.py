from __future__ import annotations

from statistics import mean, pstdev

from app.analyzers.risk import clamp_score, is_anomaly_level, risk_from_score
from app.schemas.pdm import ModelAnalysisResult, ProcessedMetric

FEATURE_NAMES = [
    "avgOcrConfidence",
    "successRate",
    "missingRate",
    "mismatchRate",
    "eventCountValid",
]


class IsolationForestAnalyzer:
    model_type = "ISOLATION_FOREST"
    model_version = "iforest-v1"

    def analyze(self, metrics: list[ProcessedMetric], target: ProcessedMetric) -> ModelAnalysisResult:
        group = [
            metric
            for metric in metrics
            if metric.camera_id == target.camera_id and metric.lane_id == target.lane_id
        ]
        group = group[-48:]
        features = [_feature_vector(metric) for metric in group]
        target_vector = _feature_vector(target)

        anomaly, raw_score, threshold, backend, contamination = self._detect(features, target_vector)
        if anomaly and _is_clear_normal_quality(target):
            anomaly = False
            raw_score = threshold
        health_score = clamp_score(100 - max(0.0, threshold - raw_score) * 80)
        if anomaly and health_score >= 80:
            health_score = 79.9
        risk_level = risk_from_score(health_score)

        reason_code = "PATTERN_ANOMALY" if anomaly else "NORMAL_PATTERN"
        return ModelAnalysisResult(
            cameraId=target.camera_id,
            laneId=target.lane_id,
            analysisStart=group[0].bucket_start if group else target.bucket_start,
            analysisEnd=target.bucket_end,
            healthScore=health_score,
            riskLevel=risk_level,
            modelType=self.model_type,
            modelVersion=self.model_version,
            reasonCode=reason_code,
            reasonText=(
                "최근 짧은 구간의 품질 지표 조합이 평소 정상 패턴에서 벗어났습니다."
                if anomaly
                else "최근 짧은 구간의 품질 지표 조합이 정상 패턴 범위 안에 있습니다."
            ),
            recommendedAction=(
                "OCR 신뢰도, 누락률, 불일치율을 함께 확인하고 같은 시간대 영상 품질을 점검하세요."
                if anomaly
                else "정기 점검 주기를 유지하세요."
            ),
            trendSummary=(
                "Isolation Forest는 confidence, successRate, missingRate, mismatchRate, "
                "eventCountValid 조합이 짧은 기간 동안 평소 패턴과 다른지 판단했습니다."
            ),
            isAnomaly=is_anomaly_level(risk_level),
            debug={
                "features": FEATURE_NAMES,
                "score": raw_score,
                "threshold": threshold,
                "backend": backend,
                "contamination": contamination,
            },
        )

    def _detect(
        self,
        features: list[list[float]],
        target_vector: list[float],
    ) -> tuple[bool, float, float, str, str]:
        if len(features) >= 8:
            try:
                from sklearn.ensemble import IsolationForest

                contamination = min(0.25, max(0.10, 1 / len(features)))
                model = IsolationForest(
                    n_estimators=100,
                    contamination=contamination,
                    random_state=42,
                )
                model.fit(features)
                prediction = int(model.predict([target_vector])[0])
                score = float(model.decision_function([target_vector])[0])
                return (
                    prediction == -1,
                    score,
                    0.0,
                    "sklearn",
                    f"{contamination:.4f} = min(0.25, max(0.10, 1 / sample_count))",
                )
            except Exception:
                pass
        return _fallback_detect(features, target_vector)


def _feature_vector(metric: ProcessedMetric) -> list[float]:
    return [
        metric.avg_ocr_confidence,
        metric.success_rate,
        metric.missing_rate,
        metric.mismatch_rate,
        1.0 if metric.event_count_valid else 0.0,
    ]


def _is_clear_normal_quality(metric: ProcessedMetric) -> bool:
    return (
        metric.event_count_valid
        and metric.avg_ocr_confidence >= 85
        and metric.success_rate >= 88
        and metric.missing_rate <= 8
        and metric.mismatch_rate <= 12
    )


def _fallback_detect(
    features: list[list[float]],
    target_vector: list[float],
) -> tuple[bool, float, float, str, str]:
    if len(features) < 2:
        return False, 0.0, 3.0, "statistical-fallback", "not_applied: sample_count < 8"
    distances = [_z_distance(features, row) for row in features]
    target_distance = _z_distance(features, target_vector)
    threshold = mean(distances) + 3 * (pstdev(distances) or 1.0)
    return (
        target_distance > threshold,
        -target_distance,
        -threshold,
        "statistical-fallback",
        "not_applied: sample_count < 8 or sklearn unavailable",
    )


def _z_distance(features: list[list[float]], row: list[float]) -> float:
    columns = list(zip(*features))
    total = 0.0
    for index, values in enumerate(columns):
        avg = mean(values)
        std = pstdev(values) or 1.0
        total += abs((row[index] - avg) / std)
    return total
