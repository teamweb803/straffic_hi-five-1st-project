"""Operational API for the Python Ingress process."""
from __future__ import annotations

from time import monotonic

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.services.spring_client import SpringForwardError, SpringRestClient

router = APIRouter()


def get_spring_client(req: Request) -> SpringRestClient:
    return req.app.state.spring_client


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
        "springRestBaseUrl": settings.spring_rest_base_url,
        "webtransportHost": settings.webtransport_host,
        "webtransportPort": settings.webtransport_port,
        "forwardedEvents": req.app.state.forwarded_events,
        "uptimeSec": uptime_sec,
    }


@router.get("/metrics")
async def metrics(req: Request, response: Response):
    response.media_type = "text/plain"
    uptime_sec = monotonic() - req.app.state.started_at
    return (
        f"hifive_ingress_forwarded_events {req.app.state.forwarded_events}\n"
        f"hifive_ingress_uptime_seconds {uptime_sec:.3f}\n"
    )


@router.post("/internal/passage-events", status_code=status.HTTP_202_ACCEPTED)
async def forward_passage_event(
    req: Request,
    x_event_id: str = Header(alias="X-Event-Id"),
):
    """Development bridge for protobuf bytes before WebTransport is wired.

    Production edge clients should use WebTransport over QUIC/TLS. This endpoint
    keeps the ingress-to-Spring contract testable without giving the ingress any
    business persistence responsibility.
    """
    payload = await req.body()
    if not payload:
        raise HTTPException(status_code=400, detail="protobuf payload is required")

    try:
        result = await get_spring_client(req).forward_passage_event(x_event_id, payload)
    except SpringForwardError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    req.app.state.forwarded_events += 1
    return result
