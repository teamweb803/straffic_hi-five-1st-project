"""FastAPI 엣지 서버 엔트리포인트.

기동 시 :
- 가상 통과선 Detector 초기화
- gRPC 클라이언트 워커 시작
종료 시 :
- gRPC 채널/워커 정리
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.services.crossing import CrossingLineDetector
from app.services.gps_service import GpsCache
from app.services.grpc_client import TollingGrpcClient
from app.services.spring_client import SpringRestClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.detector = CrossingLineDetector(settings)
    app.state.gps_cache = GpsCache()
    app.state.spring_client = SpringRestClient(settings)
    app.state.grpc_client = TollingGrpcClient(settings)
    await app.state.grpc_client.start()
    logger.info("hifive Edge API ready (node=%s)", settings.edge_node_id)
    try:
        yield
    finally:
        await app.state.grpc_client.stop()


app = FastAPI(
    title="hifive Edge API",
    description="YOLO 결과 수신 → 가상 통과선 판정 → gRPC 송신",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)
