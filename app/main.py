"""Standalone FastAPI app for the HiFive member dashboard chatbot."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.services.chatbot_service import ChatbotService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.started_at = monotonic()
    app.state.chatbot_service = ChatbotService(settings)
    logger.info("HiFive chatbot API ready")
    yield


app = FastAPI(
    title="HiFive Member Dashboard Chatbot",
    description="FastAPI chatbot API backed by PostgreSQL dashboard data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

