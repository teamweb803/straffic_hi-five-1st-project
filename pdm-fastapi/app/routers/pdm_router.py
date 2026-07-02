from fastapi import APIRouter

from app.scenarios.demo_scenarios import build_demo_metrics
from app.schemas.pdm import (
    AnalyzeRequest,
    CommonResponse,
    DemoScenarioRequest,
    HealthScoreRequest,
    SpringAnalyzeRequest,
)
from app.services.pdm_analysis_service import PdmAnalysisService

router = APIRouter(prefix="/analysis/v1/pdm", tags=["PDM Analysis"])
service = PdmAnalysisService()


@router.post("/quality-metrics/analyze", response_model=CommonResponse)
def analyze_quality_metrics(request: AnalyzeRequest) -> CommonResponse:
    result = service.analyze(request)
    return CommonResponse(data=result)


@router.post("/health-score", response_model=CommonResponse)
def calculate_health_score(request: HealthScoreRequest) -> CommonResponse:
    result = service.calculate_single_health_score(request.metric, request.event_count_min)
    return CommonResponse(data=result)


@router.post("/demo-scenarios", response_model=CommonResponse)
def create_demo_scenario(request: DemoScenarioRequest) -> CommonResponse:
    metrics = build_demo_metrics(request)
    analysis = service.analyze(AnalyzeRequest(metrics=metrics))
    return CommonResponse(
        message="시연용 품질 지표와 분석 결과가 생성되었습니다.",
        data={"metrics": metrics, "analysis": analysis},
    )


@router.post("/spring/analyze-and-save", response_model=CommonResponse)
def analyze_from_spring_and_save(request: SpringAnalyzeRequest) -> CommonResponse:
    result = service.analyze_from_spring(request)
    return CommonResponse(
        message="Spring Boot 품질 지표 조회 후 분석 결과 저장 흐름이 처리되었습니다.",
        data=result,
    )
