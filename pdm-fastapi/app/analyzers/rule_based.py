from app.analyzers.risk import clamp_score, is_anomaly_level, risk_from_score
from app.schemas.pdm import ModelAnalysisResult, ProcessedMetric


class RuleBasedAnalyzer:
    model_type = "RULE_BASED"
    model_version = "rule-v1"

    def analyze(self, metric: ProcessedMetric) -> ModelAnalysisResult:
        reasons: list[tuple[str, float]] = []
        if metric.avg_ocr_confidence < 75:
            reasons.append(("LOW_OCR_CONFIDENCE", 75 - metric.avg_ocr_confidence))
        if metric.success_rate < 80:
            reasons.append(("LOW_SUCCESS_RATE", 80 - metric.success_rate))
        if metric.missing_rate > 10:
            reasons.append(("HIGH_MISSING_RATE", metric.missing_rate - 10))
        if metric.mismatch_rate > 15:
            reasons.append(("HIGH_MISMATCH_RATE", metric.mismatch_rate - 15))
        if not metric.event_count_valid:
            reasons.append(("LOW_EVENT_COUNT", 10.0))

        score = 100.0
        score -= max(0.0, 75 - metric.avg_ocr_confidence) * 0.8
        score -= max(0.0, 80 - metric.success_rate) * 0.6
        score -= max(0.0, metric.missing_rate - 10) * 1.2
        score -= max(0.0, metric.mismatch_rate - 15) * 1.0
        if not metric.event_count_valid:
            score -= 8.0
        health_score = clamp_score(score)

        risk_level = risk_from_score(health_score)
        severe_quality = (
            metric.avg_ocr_confidence < 55
            or metric.success_rate < 60
            or metric.missing_rate > 30
            or metric.mismatch_rate > 35
        )
        if severe_quality:
            risk_level = "CRITICAL"

        primary_reason = max(reasons, key=lambda item: item[1])[0] if reasons else "NORMAL_QUALITY"
        return ModelAnalysisResult(
            cameraId=metric.camera_id,
            laneId=metric.lane_id,
            analysisStart=metric.bucket_start,
            analysisEnd=metric.bucket_end,
            healthScore=health_score,
            riskLevel=risk_level,
            modelType=self.model_type,
            modelVersion=self.model_version,
            reasonCode=primary_reason,
            reasonText=_reason_text(primary_reason),
            recommendedAction=_recommended_action(primary_reason),
            trendSummary=(
                "현재 구간의 OCR 품질 지표를 기준으로 즉시 이상 여부를 판단했습니다."
            ),
            isAnomaly=is_anomaly_level(risk_level),
            debug={"reasons": reasons, "eventCountValid": metric.event_count_valid},
        )


def _reason_text(reason_code: str) -> str:
    return {
        "NORMAL_QUALITY": "현재 구간의 OCR 품질 지표가 정상 범위입니다.",
        "LOW_OCR_CONFIDENCE": "현재 구간에서 OCR 신뢰도 저하가 감지되었습니다.",
        "LOW_SUCCESS_RATE": "현재 구간에서 OCR 성공률 저하가 감지되었습니다.",
        "HIGH_MISSING_RATE": "현재 구간에서 인식 누락률 증가가 감지되었습니다.",
        "HIGH_MISMATCH_RATE": "현재 구간에서 전후방 번호판 불일치 증가가 감지되었습니다.",
        "LOW_EVENT_COUNT": "이벤트 수가 적어 판단 신뢰도가 낮은 구간입니다.",
    }[reason_code]


def _recommended_action(reason_code: str) -> str:
    return {
        "NORMAL_QUALITY": "정기 점검 주기를 유지하세요.",
        "LOW_OCR_CONFIDENCE": "렌즈 오염, 초점 상태, 카메라 설치 각도를 점검하세요.",
        "LOW_SUCCESS_RATE": "OCR 처리 로그와 조명 상태를 함께 확인하세요.",
        "HIGH_MISSING_RATE": "카메라 시야 가림, 조명 변화, 렌즈 오염 여부를 점검하세요.",
        "HIGH_MISMATCH_RATE": "전방·후방 카메라 시간 동기화와 설치 각도를 확인하세요.",
        "LOW_EVENT_COUNT": "차량 통행량이 적은 시간대인지 확인하고 추가 구간을 함께 검토하세요.",
    }[reason_code]
