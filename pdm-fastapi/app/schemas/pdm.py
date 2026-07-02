from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # Pydantic v1
    ConfigDict = None

RiskLevel = Literal["NORMAL", "WARNING", "HIGH", "CRITICAL"]
ModelType = Literal["RULE_BASED", "ISOLATION_FOREST", "LSTM_AE"]


if ConfigDict:

    class PdmBaseModel(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        def as_dict(self, **kwargs):
            return self.model_dump(**kwargs)

else:

    class PdmBaseModel(BaseModel):
        class Config:
            allow_population_by_field_name = True

        def as_dict(self, **kwargs):
            return self.dict(**kwargs)


class QualityMetric(PdmBaseModel):
    camera_id: int = Field(alias="cameraId")
    lane_id: int = Field(alias="laneId")
    bucket_start: datetime = Field(alias="bucketStart")
    bucket_end: datetime = Field(alias="bucketEnd")
    avg_ocr_confidence: float = Field(alias="avgOcrConfidence")
    success_rate: float = Field(alias="successRate")
    missing_rate: float = Field(alias="missingRate")
    match_rate: float | None = Field(default=None, alias="matchRate")
    mismatch_rate: float = Field(alias="mismatchRate")
    event_count: int = Field(alias="eventCount")


class ProcessedMetric(QualityMetric):
    event_count_valid: bool = Field(alias="eventCountValid")
    missing_bucket: bool = Field(default=False, alias="missingBucket")


class AnalyzeRequest(PdmBaseModel):
    metrics: list[QualityMetric]
    event_count_min: int = Field(default=10, alias="eventCountMin")
    window_size: int = Field(default=6, alias="windowSize")


class HealthScoreRequest(PdmBaseModel):
    metric: QualityMetric
    event_count_min: int = Field(default=10, alias="eventCountMin")


class SpringAnalyzeRequest(PdmBaseModel):
    spring_base_url: str | None = Field(default=None, alias="springBaseUrl")
    camera_id: int = Field(alias="cameraId")
    lane_id: int | None = Field(default=None, alias="laneId")
    query_from: datetime | None = Field(default=None, alias="from")
    query_to: datetime | None = Field(default=None, alias="to")
    event_count_min: int = Field(default=10, alias="eventCountMin")
    window_size: int = Field(default=6, alias="windowSize")
    save_results: bool = Field(default=True, alias="saveResults")


class ModelAnalysisResult(PdmBaseModel):
    camera_id: int = Field(alias="cameraId")
    lane_id: int = Field(alias="laneId")
    analysis_start: datetime = Field(alias="analysisStart")
    analysis_end: datetime = Field(alias="analysisEnd")
    health_score: float = Field(alias="healthScore")
    risk_level: RiskLevel = Field(alias="riskLevel")
    model_type: ModelType = Field(alias="modelType")
    model_version: str = Field(alias="modelVersion")
    reason_code: str = Field(alias="reasonCode")
    reason_text: str = Field(alias="reasonText")
    recommended_action: str = Field(alias="recommendedAction")
    trend_summary: str = Field(alias="trendSummary")
    is_anomaly: bool = Field(alias="isAnomaly")
    debug: dict[str, Any] = Field(default_factory=dict)

    def to_spring_payload(self) -> dict[str, Any]:
        return self.as_dict(by_alias=True, exclude={"is_anomaly", "debug"})


class IntegratedAnalysis(PdmBaseModel):
    camera_id: int = Field(alias="cameraId")
    lane_id: int = Field(alias="laneId")
    representative_risk_level: RiskLevel = Field(alias="representativeRiskLevel")
    representative_health_score: float = Field(alias="representativeHealthScore")
    anomaly_model_count: int = Field(alias="anomalyModelCount")
    model_results: list[ModelAnalysisResult] = Field(alias="modelResults")
    spring_save_payloads: list[dict[str, Any]] = Field(alias="springSavePayloads")


class DemoScenarioRequest(PdmBaseModel):
    scenario_type: Literal["NORMAL", "REAR_DEGRADED", "MISMATCH_SPIKE", "LOW_TRAFFIC"] = Field(
        alias="scenarioType"
    )
    start_time: datetime = Field(alias="startTime")
    duration_minutes: int = Field(default=60, alias="durationMinutes")


class CommonResponse(PdmBaseModel):
    success: bool = True
    message: str = "요청이 정상 처리되었습니다."
    data: Any
