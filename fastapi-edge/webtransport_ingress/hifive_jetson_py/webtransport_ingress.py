from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .ack import ACK, REJECT, RETRY, encode_ack
from .framing import FrameError, unpack_ready_event_frame
from .ingress_state import IngressStats
from .spring_forwarder import SpringForwarder


logger = logging.getLogger("hifive.ingress")

NETWORK_TRANSITION_EVENT_PREFIX = "network-transition-"


def _decode_network_transition_payload(payload: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        return {
            "type": "network_transition",
            "parse_error": str(exc),
            "raw": payload[:200].decode("utf-8", errors="replace"),
        }
    if isinstance(decoded, dict):
        return decoded
    return {"type": "network_transition", "value": decoded}


@dataclass
class IngressSession:
    session_id: int
    forwarder: SpringForwarder
    stats: IngressStats
    buffers: dict[int, bytearray]

    async def receive_stream(self, stream_id: int, data: bytes, stream_ended: bool) -> bytes | None:
        self.buffers[stream_id].extend(data)
        if not stream_ended:
            return None

        buffer = self.buffers.pop(stream_id, bytearray())
        try:
            frame = unpack_ready_event_frame(buffer)
        except FrameError as exc:
            detail = str(exc)
            self.stats.mark_malformed(detail)
            return encode_ack(REJECT, "unknown", detail)
        if frame is None:
            detail = "incomplete frame"
            self.stats.mark_malformed(detail)
            return encode_ack(REJECT, "unknown", detail)

        self.stats.mark_received(frame.event_id, payload_bytes=len(frame.payload))
        logger.info(
            "WebTransport event received event_id=%s bytes=%d session=%s stream=%s",
            frame.event_id,
            len(frame.payload),
            self.session_id,
            stream_id,
        )
        if frame.event_id.startswith(NETWORK_TRANSITION_EVENT_PREFIX):
            detail = _decode_network_transition_payload(frame.payload)
            self.stats.mark_network_transition(
                frame.event_id,
                detail,
                payload_bytes=len(frame.payload),
            )
            logger.info(
                "Network transition event_id=%s outage_ms=%s route_before=%s route_after=%s recovered_event_id=%s",
                frame.event_id,
                detail.get("outage_ms", ""),
                detail.get("route_before_failure", ""),
                detail.get("route_after_recovery", ""),
                detail.get("recovered_event_id", ""),
            )
            return encode_ack(ACK, frame.event_id, "network transition logged")

        result = await self.forwarder.forward(frame.payload, frame.event_id)
        if result.accepted:
            self.stats.mark_ack(frame.event_id)
            logger.info("WebTransport event ACK event_id=%s detail=%s", frame.event_id, result.detail)
            return encode_ack(ACK, frame.event_id, result.detail)
        if result.retryable:
            self.stats.mark_retry(frame.event_id, result.detail)
            logger.info("WebTransport event RETRY event_id=%s detail=%s", frame.event_id, result.detail)
            return encode_ack(RETRY, frame.event_id, result.detail)
        self.stats.mark_reject(frame.event_id, result.detail)
        logger.info("WebTransport event REJECT event_id=%s detail=%s", frame.event_id, result.detail)
        return encode_ack(REJECT, frame.event_id, result.detail)


class WebTransportIngressFactory:
    def __init__(
        self,
        *,
        path: str,
        forwarder: SpringForwarder,
        stats: IngressStats,
    ) -> None:
        self.path = path if path.startswith("/") else f"/{path}"
        self.forwarder = forwarder
        self.stats = stats

    def create(self):  # type: ignore[no-untyped-def]
        from aioquic.asyncio.protocol import QuicConnectionProtocol
        from aioquic.h3.connection import H3Connection
        from aioquic.h3.events import HeadersReceived, WebTransportStreamDataReceived
        from aioquic.quic.events import ProtocolNegotiated, QuicEvent

        expected_path = self.path
        forwarder = self.forwarder
        stats = self.stats

        class IngressProtocol(QuicConnectionProtocol):
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                super().__init__(*args, **kwargs)
                self.http: H3Connection | None = None
                self.sessions: dict[int, IngressSession] = {}

            def quic_event_received(self, event: QuicEvent) -> None:
                if isinstance(event, ProtocolNegotiated):
                    self.http = H3Connection(self._quic, enable_webtransport=True)
                if self.http is None:
                    return
                for http_event in self.http.handle_event(event):
                    if isinstance(http_event, HeadersReceived):
                        self._handle_headers(http_event)
                    elif isinstance(http_event, WebTransportStreamDataReceived):
                        asyncio.create_task(self._handle_webtransport_stream(http_event))

            def _handle_headers(self, event: HeadersReceived) -> None:
                assert self.http is not None
                headers = dict(event.headers)
                method = headers.get(b":method", b"").decode("ascii", errors="ignore")
                protocol = headers.get(b":protocol", b"").decode("ascii", errors="ignore")
                path = headers.get(b":path", b"").decode("utf-8", errors="ignore")
                if method == "CONNECT" and protocol == "webtransport" and path == expected_path:
                    self.http.send_headers(
                        stream_id=event.stream_id,
                        headers=[
                            (b":status", b"200"),
                            (b"sec-webtransport-http3-draft", b"draft02"),
                        ],
                    )
                    self.sessions[event.stream_id] = IngressSession(
                        session_id=event.stream_id,
                        forwarder=forwarder,
                        stats=stats,
                        buffers=defaultdict(bytearray),
                    )
                else:
                    self.http.send_headers(stream_id=event.stream_id, headers=[(b":status", b"404")])
                    self.http.send_data(stream_id=event.stream_id, data=b"", end_stream=True)
                self.transmit()

            async def _handle_webtransport_stream(self, event: WebTransportStreamDataReceived) -> None:
                session = self.sessions.get(event.session_id)
                if session is None:
                    return
                response = await session.receive_stream(event.stream_id, event.data, event.stream_ended)
                if response is None:
                    return
                assert self.http is not None
                ack_stream_id = self.http.create_webtransport_stream(event.session_id)
                self._quic.send_stream_data(stream_id=ack_stream_id, data=response, end_stream=True)
                self.transmit()

        return IngressProtocol
