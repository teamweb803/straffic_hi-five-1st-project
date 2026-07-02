from app.analyzers.integration import integrate_results
from app.analyzers.isolation_forest import IsolationForestAnalyzer
from app.analyzers.lstm_ae import LstmAeAnalyzer
from app.analyzers.preprocessing import preprocess_metrics
from app.analyzers.rule_based import RuleBasedAnalyzer
from app.pdm.wire import to_wire_payload
from app.schemas.pdm import (
    AnalyzeRequest,
    IntegratedAnalysis,
    ProcessedMetric,
    QualityMetric,
    SpringAnalyzeRequest,
)
from app.services.spring_pdm_client import SpringPdmClient


class PdmAnalysisService:
    def __init__(self) -> None:
        self.rule_based = RuleBasedAnalyzer()
        self.isolation_forest = IsolationForestAnalyzer()
        self.lstm_ae = LstmAeAnalyzer()

    def analyze(self, request: AnalyzeRequest) -> list[IntegratedAnalysis]:
        processed = preprocess_metrics(request.metrics, request.event_count_min)
        targets = _representative_metric_by_group(processed)
        return [
            self._analyze_target(processed, target, request.window_size)
            for target in targets
        ]

    def calculate_single_health_score(self, metric: QualityMetric, event_count_min: int) -> dict:
        processed = preprocess_metrics([metric], event_count_min=event_count_min)[0]
        result = self.rule_based.analyze(processed)
        return result.as_dict(by_alias=True)

    def analyze_from_spring(self, request: SpringAnalyzeRequest) -> dict:
        client = SpringPdmClient(base_url=request.spring_base_url)
        try:
            metrics = client.fetch_quality_metrics(
                camera_id=request.camera_id,
                lane_id=request.lane_id,
                query_from=request.query_from,
                query_to=request.query_to,
            )
            analysis = self.analyze(
                AnalyzeRequest(
                    metrics=metrics,
                    eventCountMin=request.event_count_min,
                    windowSize=request.window_size,
                )
            )
            # 스케줄러 경로와 동일하게 wire 경계를 통과시킨다:
            # datetime -> ISO, HIGH -> CRITICAL, LSTM_AE 유지, 분석 구간을 요청 window로 통일.
            raw_payloads = [
                payload
                for integrated in analysis
                for payload in integrated.spring_save_payloads
            ]
            payloads = [
                to_wire_payload(
                    payload,
                    analysis_start=request.query_from,
                    analysis_end=request.query_to,
                )
                for payload in raw_payloads
            ]
            saved: list = []
            failed: list = []
            if request.save_results:
                saved, failed = client.save_analysis_results_batch_resilient(payloads)
            return {
                "fetchedMetricCount": len(metrics),
                "analysisGroupCount": len(analysis),
                "springSavePayloadCount": len(payloads),
                "savedCount": len(saved),
                "failedCount": len(failed),
                "analysis": analysis,
                "springSavePayloads": payloads,
            }
        finally:
            client.close()

    def _analyze_target(
        self,
        processed: list[ProcessedMetric],
        target: ProcessedMetric,
        window_size: int,
    ) -> IntegratedAnalysis:
        model_results = [
            self.rule_based.analyze(target),
            self.isolation_forest.analyze(processed, target),
            self.lstm_ae.analyze(processed, target, window_size),
        ]
        return integrate_results(target, model_results)


def _representative_metric_by_group(metrics: list[ProcessedMetric]) -> list[ProcessedMetric]:
    representatives: dict[tuple[int, int], ProcessedMetric] = {}
    for metric in metrics:
        key = (metric.camera_id, metric.lane_id)
        current = representatives.get(key)
        if current is None or _metric_rank(metric) < _metric_rank(current):
            representatives[key] = metric
    return list(representatives.values())


def _metric_rank(metric: ProcessedMetric) -> tuple[float, float]:
    score = 100.0
    score -= max(0.0, 75 - metric.avg_ocr_confidence) * 0.8
    score -= max(0.0, 80 - metric.success_rate) * 0.6
    score -= max(0.0, metric.missing_rate - 10) * 1.2
    score -= max(0.0, metric.mismatch_rate - 15) * 1.0
    if not metric.event_count_valid:
        score -= 8.0
    return score, -metric.bucket_start.timestamp()
