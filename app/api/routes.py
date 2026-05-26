"""HTTP routes for the standalone HiFive chatbot API."""
from __future__ import annotations

from time import monotonic

from fastapi import APIRouter, Request, Response

from app.services.chatbot_service import ChatbotService

router = APIRouter()


def get_chatbot_service(req: Request) -> ChatbotService:
    return req.app.state.chatbot_service


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/status")
async def status_view(req: Request):
    settings = req.app.state.settings
    uptime_sec = round(monotonic() - req.app.state.started_at, 3)
    return {
        "status": "ok",
        "edgeNodeId": settings.edge_node_id,
        "dbHost": settings.db_host,
        "dbPort": settings.db_port,
        "dbName": settings.db_name,
        "uptimeSec": uptime_sec,
    }


@router.get("/metrics")
async def metrics(req: Request, response: Response):
    response.media_type = "text/plain"
    uptime_sec = monotonic() - req.app.state.started_at
    return f"hifive_chatbot_uptime_seconds {uptime_sec:.3f}\n"


@router.get("/video/status")
def video_status(req: Request):
    return get_chatbot_service(req).video_status_snapshot()


@router.post("/api/chatbot/ask")
@router.post("/api/chatbot")
@router.post("/api/chat")
def ask_chatbot(req: Request, payload: dict[str, object]):
    question = str(
        payload.get("question")
        or payload.get("message")
        or payload.get("text")
        or ""
    ).strip()
    return get_chatbot_service(req).answer(question)

