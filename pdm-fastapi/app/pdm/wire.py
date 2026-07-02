from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings


def to_wire_payload(
    payload: dict[str, Any],
    settings: Settings | None = None,
    analysis_start: Any = None,
    analysis_end: Any = None,
) -> dict[str, Any]:
    """모델 결과 payload를 Spring DB 계약에 맞춰 변환한다(저장 직전 경계).

    1) riskLevel: HIGH -> CRITICAL
       ERD risk_level은 NORMAL/WARNING/CRITICAL 3개만 허용. 코드 내부의 HIGH(40~59점)는
       스펙상 어차피 CRITICAL(<60) 구간이므로 상향 흡수한다.
    2) modelType: LSTM_AE 유지
       현재 Spring Boot PDM 저장 API 허용값은 RULE_BASED / ISOLATION_FOREST / LSTM_AE이다.
    3) analysisStart/analysisEnd 통일: analysis_start/analysis_end가 주어지면 모든 모델의
       구간을 공식 분석 window로 덮어쓴다(가이드 §9: 동일 cameraId/laneId/window의 모델별 저장).
       모델마다 제각각인 내부 데이터 구간(rule=최신버킷, iforest=fetch시작, lstm=window시작)을
       한 번의 분석으로 묶기 위함. 각 모델의 실제 관찰 범위는 trendSummary에 남는다.
    4) analysisStart/analysisEnd: datetime -> ISO 문자열
       to_spring_payload는 datetime 객체를 담고 있어 httpx json= 직렬화가 깨진다.
       경계에서 문자열로 고정(중복키 안정화에도 필요).
    """
    settings = settings or get_settings()
    wired = dict(payload)

    if settings.collapse_high_to_critical and wired.get("riskLevel") == "HIGH":
        wired["riskLevel"] = "CRITICAL"

    if wired.get("modelType") == "LSTM_AE":
        wired["modelType"] = settings.lstm_wire_model_type

    if analysis_start is not None:
        wired["analysisStart"] = analysis_start
    if analysis_end is not None:
        wired["analysisEnd"] = analysis_end

    for field in ("analysisStart", "analysisEnd"):
        value = wired.get(field)
        if hasattr(value, "isoformat"):
            wired[field] = value.isoformat()

    return wired
