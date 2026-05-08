from __future__ import annotations

import asyncio
import json
import ssl
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .ack import decode_ack
from .framing import pack_event_frame
from .spool import FileSpool, SpoolItem


NETWORK_TRANSITION_EVENT_PREFIX = "network-transition-"


@dataclass
class WebTransportIngressSender:
    host: str
    port: int
    path: str
    server_name: str
    verify_tls: bool
    timeout_sec: float
    spool: FileSpool
    retry_enabled: bool = True
    retry_initial_sec: float = 1.0
    retry_max_sec: float = 30.0
    retry_max_items_per_cycle: int = 16

    def __post_init__(self) -> None:
        self._inflight: set[Path] = set()
        self._lock = threading.Lock()
        self._outage_started_monotonic: float | None = None
        self._outage_started_ms = 0
        self._outage_failed_event_id = ""
        self._outage_failure_route = ""
        self._pending_network_logs: list[tuple[str, bytes]] = []
        if self.retry_enabled:
            thread = threading.Thread(target=self._retry_loop, name="hifive-spool-retry", daemon=True)
            thread.start()

    def submit(self, payload: bytes, event_id: str) -> bool:
        item = self.spool.enqueue(payload, event_id=event_id)
        return self._send_spooled_item(item, source="live")

    def _retry_loop(self) -> None:
        delay = max(0.1, self.retry_initial_sec)
        while True:
            attempted = False
            sent = 0
            for item in self.spool.iter_items()[: self.retry_max_items_per_cycle]:
                if not item.event_id:
                    continue
                attempted = True
                if not self._send_spooled_item(item, source="retry"):
                    break
                sent += 1
            if sent:
                delay = max(0.1, self.retry_initial_sec)
            elif attempted:
                delay = min(self.retry_max_sec, max(0.1, delay * 2.0))
            else:
                delay = max(0.1, self.retry_initial_sec)
            time.sleep(delay)

    def _send_spooled_item(self, item: SpoolItem, source: str) -> bool:
        if not self._claim(item.path):
            return False
        item = self.spool.record_attempt(item)
        try:
            accepted = asyncio.run(self._send_once(item.payload, item.event_id))
        except Exception as exc:
            self._mark_send_failure(item.event_id, str(exc), source)
            print(f"WebTransport {source} failed event_id={item.event_id}: {exc}")
            self._release(item.path)
            return False

        if accepted:
            self.spool.ack(item)
            self._release(item.path)
            self._mark_send_success(item.event_id, source)
            self._flush_network_logs()
            return True
        self._release(item.path)
        return False

    def _claim(self, path: Path) -> bool:
        with self._lock:
            if path in self._inflight:
                return False
            self._inflight.add(path)
            return True

    def _release(self, path: Path) -> None:
        with self._lock:
            self._inflight.discard(path)

    def _mark_send_failure(self, event_id: str, detail: str, source: str) -> None:
        with self._lock:
            if self._outage_started_monotonic is not None:
                return
        route = self._route_snapshot()
        started_ms = int(time.time() * 1000)
        with self._lock:
            if self._outage_started_monotonic is not None:
                return
            self._outage_started_monotonic = time.monotonic()
            self._outage_started_ms = started_ms
            self._outage_failed_event_id = event_id
            self._outage_failure_route = route
        print(
            "network_outage_started "
            f"source={source} event_id={event_id} route={route} detail={detail}"
        )

    def _mark_send_success(self, event_id: str, source: str) -> None:
        with self._lock:
            outage_started = self._outage_started_monotonic
            if outage_started is None:
                return
            failed_event_id = self._outage_failed_event_id
            failure_route = self._outage_failure_route
            outage_started_ms = self._outage_started_ms

        recovered_ms = int(time.time() * 1000)
        outage_ms = int((time.monotonic() - outage_started) * 1000)
        recovered_route = self._route_snapshot()
        log_event_id = self._network_log_event_id(recovered_ms, event_id)
        payload = {
            "type": "network_transition",
            "transition": "communication_recovered",
            "transport": "webtransport",
            "host": self.host,
            "port": self.port,
            "source": source,
            "failed_event_id": failed_event_id,
            "recovered_event_id": event_id,
            "outage_started_ms": outage_started_ms,
            "recovered_ms": recovered_ms,
            "outage_ms": outage_ms,
            "route_before_failure": failure_route,
            "route_after_recovery": recovered_route,
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with self._lock:
            self._outage_started_monotonic = None
            self._outage_started_ms = 0
            self._outage_failed_event_id = ""
            self._outage_failure_route = ""
            self._pending_network_logs.append((log_event_id, body))
        print(
            "network_outage_recovered "
            f"event_id={event_id} outage_ms={outage_ms} route={recovered_route}"
        )

    def _flush_network_logs(self) -> None:
        while True:
            with self._lock:
                if not self._pending_network_logs:
                    return
                event_id, payload = self._pending_network_logs[0]
            try:
                accepted = asyncio.run(self._send_once(payload, event_id))
            except Exception as exc:
                print(f"network_transition_log_send_failed event_id={event_id}: {exc}")
                return
            if not accepted:
                print(f"network_transition_log_rejected event_id={event_id}")
                return
            with self._lock:
                if self._pending_network_logs and self._pending_network_logs[0][0] == event_id:
                    self._pending_network_logs.pop(0)
                else:
                    self._pending_network_logs = [
                        item for item in self._pending_network_logs if item[0] != event_id
                    ]

    def _route_snapshot(self) -> str:
        try:
            result = subprocess.run(
                ["ip", "route", "get", self.host],
                capture_output=True,
                text=True,
                timeout=0.3,
                check=False,
            )
        except Exception as exc:
            return f"unavailable:{exc}"[:300]
        route = " ".join(result.stdout.strip().split())
        if not route:
            route = "unavailable"
        return route[:300]

    def _network_log_event_id(self, recovered_ms: int, recovered_event_id: str) -> str:
        suffix = "".join(
            char if char.isalnum() or char in "-_" else "-"
            for char in recovered_event_id
        )[:60]
        return f"{NETWORK_TRANSITION_EVENT_PREFIX}{recovered_ms}-{suffix or 'unknown'}"

    async def _send_once(self, payload: bytes, event_id: str) -> bool:
        try:
            from aioquic.asyncio import connect
            from aioquic.asyncio.protocol import QuicConnectionProtocol
            from aioquic.h3.connection import H3_ALPN, H3Connection
            from aioquic.h3.events import DataReceived, HeadersReceived, WebTransportStreamDataReceived
            from aioquic.quic.configuration import QuicConfiguration
            from aioquic.quic.events import ProtocolNegotiated, QuicEvent
        except ImportError as exc:
            raise RuntimeError("aioquic is required for WebTransport transport") from exc

        host = self.host
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        authority = f"{self.server_name}:{self.port}".encode("utf-8")
        server_name = self.server_name or self.host
        timeout_sec = self.timeout_sec

        class ClientProtocol(QuicConnectionProtocol):
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                super().__init__(*args, **kwargs)
                loop = asyncio.get_running_loop()
                self.http: H3Connection | None = None
                self.ready: asyncio.Future[None] = loop.create_future()
                self.connected: asyncio.Future[None] | None = None
                self.ack: asyncio.Future[bytes] | None = None
                self.ack_buffer = bytearray()
                self.session_id: int | None = None

            def quic_event_received(self, event: QuicEvent) -> None:
                if isinstance(event, ProtocolNegotiated):
                    self.http = H3Connection(self._quic, enable_webtransport=True)
                    if not self.ready.done():
                        self.ready.set_result(None)
                if self.http is None:
                    return
                for http_event in self.http.handle_event(event):
                    if isinstance(http_event, HeadersReceived) and http_event.stream_id == self.session_id:
                        headers = dict(http_event.headers)
                        status = headers.get(b":status", b"").decode("ascii", errors="ignore")
                        if status == "200" and self.connected and not self.connected.done():
                            self.connected.set_result(None)
                        elif self.connected and not self.connected.done():
                            self.connected.set_exception(RuntimeError(f"WebTransport rejected status={status}"))
                    elif isinstance(http_event, WebTransportStreamDataReceived):
                        self.ack_buffer.extend(http_event.data)
                        if http_event.stream_ended and self.ack and not self.ack.done():
                            self.ack.set_result(bytes(self.ack_buffer))
                    elif isinstance(http_event, DataReceived):
                        self.ack_buffer.extend(http_event.data)
                        if http_event.stream_ended and self.ack and not self.ack.done():
                            self.ack.set_result(bytes(self.ack_buffer))

            async def send_payload(self, body: bytes, event_id_value: str) -> bool:
                await asyncio.wait_for(self.ready, timeout=timeout_sec)
                assert self.http is not None
                loop = asyncio.get_running_loop()
                self.connected = loop.create_future()
                self.ack = loop.create_future()
                self.session_id = self._quic.get_next_available_stream_id()
                self.http.send_headers(
                    stream_id=self.session_id,
                    headers=[
                        (b":method", b"CONNECT"),
                        (b":scheme", b"https"),
                        (b":authority", authority),
                        (b":path", path.encode("utf-8")),
                        (b":protocol", b"webtransport"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ],
                )
                self.transmit()
                await asyncio.wait_for(self.connected, timeout=timeout_sec)

                stream_id = self.http.create_webtransport_stream(self.session_id)
                self._quic.send_stream_data(
                    stream_id=stream_id,
                    data=pack_event_frame(event_id_value, body),
                    end_stream=True,
                )
                self.transmit()
                ack_data = await asyncio.wait_for(self.ack, timeout=timeout_sec)
                ack = decode_ack(ack_data)
                return ack.accepted and ack.event_id == event_id_value

        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=H3_ALPN,
            verify_mode=ssl.CERT_REQUIRED if self.verify_tls else ssl.CERT_NONE,
            server_name=server_name,
        )
        configuration.max_datagram_frame_size = 65536

        async with connect(
            host,
            self.port,
            configuration=configuration,
            create_protocol=ClientProtocol,
        ) as protocol:
            client = protocol  # type: ignore[assignment]
            return await client.send_payload(payload, event_id)
