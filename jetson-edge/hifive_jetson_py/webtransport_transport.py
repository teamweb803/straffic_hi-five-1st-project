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
MAX_UNRELIABLE_DATAGRAM_BYTES = 60_000


@dataclass(frozen=True)
class WebTransportEndpoint:
    label: str
    host: str
    port: int
    server_name: str
    verify_tls: bool


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
    failover_enabled: bool = False
    standby_host: str = ""
    standby_port: int = 0
    standby_server_name: str = ""
    standby_verify_tls: bool | None = None
    failover_recheck_sec: float = 1.0

    def __post_init__(self) -> None:
        if self.failover_enabled and not self.standby_host:
            raise ValueError("failover_enabled requires standby_host")
        self._inflight: set[Path] = set()
        self._lock = threading.Lock()
        self._primary = WebTransportEndpoint(
            label="lan",
            host=self.host,
            port=self.port,
            server_name=self.server_name or self.host,
            verify_tls=self.verify_tls,
        )
        self._standby = self._build_standby_endpoint()
        self._active_label = self._primary.label
        self._next_primary_probe_at = 0.0
        self._outage_started_monotonic: float | None = None
        self._outage_started_ms = 0
        self._outage_failed_event_id = ""
        self._outage_failure_route = ""
        self._pending_network_logs: list[tuple[str, bytes]] = []
        self._primary_reachable = True
        self._last_primary_probe_ms = 0
        self._last_primary_probe_detail = ""
        self._watchdog_failures = 0
        self._watchdog_successes = 0
        if self._standby is not None:
            watchdog = threading.Thread(
                target=self._failover_watchdog_loop,
                name="hifive-failover-watchdog",
                daemon=True,
            )
            watchdog.start()
        if self.retry_enabled:
            thread = threading.Thread(target=self._retry_loop, name="hifive-spool-retry", daemon=True)
            thread.start()

    def submit(self, payload: bytes, event_id: str) -> bool:
        item = self.spool.enqueue(payload, event_id=event_id)
        return self._send_spooled_item(item, source="live")

    def submit_latest(self, payload: bytes, event_id: str) -> bool:
        previous_active = self._active_label
        for endpoint in self._endpoint_order():
            try:
                accepted = asyncio.run(self._send_once(payload, event_id, endpoint))
            except Exception as exc:
                if endpoint.label == self._primary.label and previous_active == self._primary.label:
                    self._mark_send_failure(event_id, str(exc), "latest", endpoint)
                elif endpoint.label == self._primary.label:
                    self._defer_primary_probe()
                print(f"WebTransport latest failed path={endpoint.label} event_id={event_id}: {exc}")
                continue

            if not accepted:
                print(f"WebTransport latest rejected path={endpoint.label} event_id={event_id}")
                continue

            self._mark_endpoint_success(event_id, "latest", endpoint, previous_active)
            self._flush_network_logs()
            return True
        return False

    def submit_unreliable(self, payload: bytes, event_id: str) -> bool:
        frame = pack_event_frame(event_id, payload)
        if len(frame) > MAX_UNRELIABLE_DATAGRAM_BYTES:
            print(
                "WebTransport unreliable dropped "
                f"event_id={event_id} bytes={len(frame)} max={MAX_UNRELIABLE_DATAGRAM_BYTES}"
            )
            return False

        for endpoint in self._endpoint_order():
            try:
                asyncio.run(self._send_datagram_once(frame, event_id, endpoint))
            except Exception as exc:
                print(f"WebTransport unreliable failed path={endpoint.label} event_id={event_id}: {exc}")
                continue
            return True
        return False

    def snapshot(self) -> dict:
        standby = self._standby
        with self._lock:
            active_label = self._active_label
            outage_started = self._outage_started_monotonic is not None
            next_primary_probe_ms = max(
                0,
                int((self._next_primary_probe_at - time.monotonic()) * 1000),
            )
            pending_network_logs = len(self._pending_network_logs)
            last_primary_probe_ms = self._last_primary_probe_ms
            primary_probe_age_ms = (
                max(0, int(time.time() * 1000) - last_primary_probe_ms)
                if last_primary_probe_ms
                else 0
            )
            primary_reachable = self._primary_reachable
            primary_probe_detail = self._last_primary_probe_detail
            watchdog_failures = self._watchdog_failures
            watchdog_successes = self._watchdog_successes
        return {
            "kind": "webtransport_ingress",
            "active_path": active_label,
            "failover_enabled": self.failover_enabled and standby is not None,
            "primary_host": self._primary.host,
            "primary_port": self._primary.port,
            "standby_host": standby.host if standby is not None else "",
            "standby_port": standby.port if standby is not None else 0,
            "outage_active": outage_started,
            "next_primary_probe_ms": next_primary_probe_ms,
            "pending_network_logs": pending_network_logs,
            "watchdog": {
                "enabled": standby is not None,
                "primary_reachable": primary_reachable,
                "last_primary_probe_ms": last_primary_probe_ms,
                "primary_probe_age_ms": primary_probe_age_ms,
                "last_primary_probe_detail": primary_probe_detail,
                "failures": watchdog_failures,
                "successes": watchdog_successes,
            },
        }

    def _failover_watchdog_loop(self) -> None:
        interval = max(0.1, float(self.failover_recheck_sec))
        timeout = max(0.1, min(float(self.timeout_sec), interval))
        while True:
            reachable, detail = self._probe_primary(timeout)
            now_ms = int(time.time() * 1000)
            now_mono = time.monotonic()
            should_flush = False
            with self._lock:
                self._primary_reachable = reachable
                self._last_primary_probe_ms = now_ms
                self._last_primary_probe_detail = detail[:300]
                if reachable:
                    self._watchdog_successes += 1
                    self._watchdog_failures = 0
                    if self._active_label == self._standby_label:
                        previous_active = self._active_label
                        outage_started = self._outage_started_monotonic
                        outage_started_ms = self._outage_started_ms
                        failed_event_id = self._outage_failed_event_id or "watchdog-primary-failed"
                        failure_route = self._outage_failure_route
                        outage_ms = (
                            int((now_mono - outage_started) * 1000)
                            if outage_started is not None
                            else 0
                        )
                        self._active_label = self._primary.label
                        self._next_primary_probe_at = 0.0
                        self._outage_started_monotonic = None
                        self._outage_started_ms = 0
                        self._outage_failed_event_id = ""
                        self._outage_failure_route = ""
                        self._append_network_transition_locked(
                            ts_ms=now_ms,
                            transition="lte_to_lan",
                            from_path=previous_active,
                            to_endpoint=self._primary,
                            source="watchdog",
                            failed_event_id=failed_event_id,
                            recovered_event_id="watchdog-primary-recovered",
                            outage_started_ms=outage_started_ms,
                            outage_ms=outage_ms,
                            route_before_failure=failure_route,
                            route_after_recovery=detail,
                        )
                        should_flush = True
                else:
                    self._watchdog_failures += 1
                    self._watchdog_successes = 0
                    if self._active_label == self._primary.label:
                        previous_active = self._active_label
                        if self._outage_started_monotonic is None:
                            self._outage_started_monotonic = now_mono
                            self._outage_started_ms = now_ms
                            self._outage_failed_event_id = "watchdog-primary-failed"
                            self._outage_failure_route = detail
                        self._active_label = self._standby_label
                        self._next_primary_probe_at = now_mono + interval
                        standby = self._active_endpoint_locked()
                        self._append_network_transition_locked(
                            ts_ms=now_ms,
                            transition="lan_to_lte",
                            from_path=previous_active,
                            to_endpoint=standby,
                            source="watchdog",
                            failed_event_id="watchdog-primary-failed",
                            recovered_event_id="watchdog-standby-active",
                            outage_started_ms=self._outage_started_ms,
                            outage_ms=0,
                            route_before_failure=detail,
                            route_after_recovery=f"active_path={standby.label} host={standby.host}",
                        )
                        should_flush = True
            if should_flush:
                self._flush_network_logs()
            time.sleep(interval)

    def _probe_primary(self, timeout: float) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-n", self._primary.host],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, f"ping timeout host={self._primary.host} timeout_sec={timeout:.3f}"
        except Exception as exc:
            return False, f"ping error host={self._primary.host}: {exc}"
        detail = " ".join((result.stdout or result.stderr).strip().split())
        if result.returncode == 0:
            return True, f"ping ok host={self._primary.host} {detail}"[:300]
        return False, f"ping failed host={self._primary.host} code={result.returncode} {detail}"[:300]

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
        previous_active = self._active_label
        for endpoint in self._endpoint_order():
            try:
                accepted = asyncio.run(self._send_once(item.payload, item.event_id, endpoint))
            except Exception as exc:
                if endpoint.label == self._primary.label and previous_active == self._primary.label:
                    self._mark_send_failure(item.event_id, str(exc), source, endpoint)
                elif endpoint.label == self._primary.label:
                    self._defer_primary_probe()
                print(
                    f"WebTransport {source} failed path={endpoint.label} "
                    f"event_id={item.event_id}: {exc}"
                )
                continue

            if not accepted:
                print(f"WebTransport {source} rejected path={endpoint.label} event_id={item.event_id}")
                continue

            self.spool.ack(item)
            self._release(item.path)
            self._mark_endpoint_success(item.event_id, source, endpoint, previous_active)
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

    def _mark_send_failure(
        self,
        event_id: str,
        detail: str,
        source: str,
        endpoint: WebTransportEndpoint,
    ) -> None:
        with self._lock:
            if self._outage_started_monotonic is not None:
                return
        route = self._route_snapshot(endpoint.host)
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
            f"source={source} path={endpoint.label} event_id={event_id} route={route} detail={detail}"
        )

    def _mark_endpoint_success(
        self,
        event_id: str,
        source: str,
        endpoint: WebTransportEndpoint,
        previous_active: str,
    ) -> None:
        success_ms = int(time.time() * 1000)
        success_mono = time.monotonic()
        success_route = self._route_snapshot(endpoint.host)
        with self._lock:
            outage_started = self._outage_started_monotonic
            failed_event_id = self._outage_failed_event_id
            failure_route = self._outage_failure_route
            outage_started_ms = self._outage_started_ms
            outage_ms = int((success_mono - outage_started) * 1000) if outage_started is not None else 0
            self._active_label = endpoint.label
            if endpoint.label == self._standby_label:
                self._next_primary_probe_at = time.monotonic() + max(0.1, self.failover_recheck_sec)
                if previous_active != endpoint.label:
                    self._append_network_transition_locked(
                        ts_ms=success_ms,
                        transition="lan_to_lte",
                        from_path=previous_active,
                        to_endpoint=endpoint,
                        source=source,
                        failed_event_id=failed_event_id or event_id,
                        recovered_event_id=event_id,
                        outage_started_ms=outage_started_ms or success_ms,
                        outage_ms=outage_ms,
                        route_before_failure=failure_route,
                        route_after_recovery=success_route,
                    )
                    print(
                        "network_failover "
                        f"event_id={event_id} from={previous_active} to={endpoint.label} "
                        f"outage_ms={outage_ms} route={success_route}"
                    )
                # Keep outage state while the primary LAN path is still failing.
                return
            else:
                self._next_primary_probe_at = 0.0

            if previous_active == endpoint.label:
                self._outage_started_monotonic = None
                self._outage_started_ms = 0
                self._outage_failed_event_id = ""
                self._outage_failure_route = ""
                return
            self._append_network_transition_locked(
                ts_ms=success_ms,
                transition="lte_to_lan",
                from_path=previous_active,
                to_endpoint=endpoint,
                source=source,
                failed_event_id=failed_event_id,
                recovered_event_id=event_id,
                outage_started_ms=outage_started_ms,
                outage_ms=outage_ms,
                route_before_failure=failure_route,
                route_after_recovery=success_route,
            )
            self._outage_started_monotonic = None
            self._outage_started_ms = 0
            self._outage_failed_event_id = ""
            self._outage_failure_route = ""
        print(
            "network_lan_recovered "
            f"event_id={event_id} from={previous_active} to={endpoint.label} "
            f"outage_ms={outage_ms} route={success_route}"
        )

    def _flush_network_logs(self) -> None:
        while True:
            with self._lock:
                if not self._pending_network_logs:
                    return
                event_id, payload = self._pending_network_logs[0]
                endpoint = self._active_endpoint_locked()
            try:
                accepted = asyncio.run(self._send_once(payload, event_id, endpoint))
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

    def _route_snapshot(self, host: str) -> str:
        try:
            result = subprocess.run(
                ["ip", "route", "get", host],
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

    def _append_network_transition_locked(
        self,
        *,
        ts_ms: int,
        transition: str,
        from_path: str,
        to_endpoint: WebTransportEndpoint,
        source: str,
        failed_event_id: str,
        recovered_event_id: str,
        outage_started_ms: int,
        outage_ms: int,
        route_before_failure: str,
        route_after_recovery: str,
    ) -> None:
        log_event_id = self._network_log_event_id(ts_ms, recovered_event_id)
        payload = {
            "transition_id": log_event_id,
            "type": "network_transition",
            "transition": transition,
            "reason": transition,
            "transport": "webtransport",
            "from_path": from_path,
            "to_path": to_endpoint.label,
            "active_path": to_endpoint.label,
            "host": to_endpoint.host,
            "port": to_endpoint.port,
            "source": source,
            "failed_event_id": failed_event_id,
            "recovered_event_id": recovered_event_id,
            "outage_started_ms": outage_started_ms,
            "recovered_ms": ts_ms,
            "outage_ms": outage_ms,
            "route_before_failure": route_before_failure,
            "route_after_recovery": route_after_recovery,
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._pending_network_logs.append((log_event_id, body))
        print(
            "network_watchdog_transition "
            f"transition={transition} from={from_path} to={to_endpoint.label} "
            f"outage_ms={outage_ms} detail={route_after_recovery}"
        )

    def _network_log_event_id(self, recovered_ms: int, recovered_event_id: str) -> str:
        suffix = "".join(
            char if char.isalnum() or char in "-_" else "-"
            for char in recovered_event_id
        )[:60]
        return f"{NETWORK_TRANSITION_EVENT_PREFIX}{recovered_ms}-{suffix or 'unknown'}"

    @property
    def _standby_label(self) -> str:
        return self._standby.label if self._standby is not None else self._primary.label

    def _build_standby_endpoint(self) -> WebTransportEndpoint | None:
        if not self.failover_enabled or not self.standby_host:
            return None
        return WebTransportEndpoint(
            label="lte",
            host=self.standby_host,
            port=self.standby_port or self.port,
            server_name=self.standby_server_name or self.standby_host,
            verify_tls=self.verify_tls if self.standby_verify_tls is None else bool(self.standby_verify_tls),
        )

    def _endpoint_order(self) -> list[WebTransportEndpoint]:
        standby = self._standby
        if standby is None:
            return [self._primary]
        with self._lock:
            active_label = self._active_label
            probe_primary = active_label == standby.label and time.monotonic() >= self._next_primary_probe_at
        if active_label == standby.label and not probe_primary:
            return [standby]
        if active_label == standby.label and probe_primary:
            return [self._primary, standby]
        return [self._primary, standby]

    def _active_endpoint_locked(self) -> WebTransportEndpoint:
        if self._standby is not None and self._active_label == self._standby.label:
            return self._standby
        return self._primary

    def _defer_primary_probe(self) -> None:
        with self._lock:
            self._next_primary_probe_at = time.monotonic() + max(0.1, self.failover_recheck_sec)

    async def _send_once(
        self,
        payload: bytes,
        event_id: str,
        endpoint: WebTransportEndpoint,
    ) -> bool:
        try:
            from aioquic.asyncio import connect
            from aioquic.asyncio.protocol import QuicConnectionProtocol
            from aioquic.h3.connection import H3_ALPN, H3Connection
            from aioquic.h3.events import DataReceived, HeadersReceived, WebTransportStreamDataReceived
            from aioquic.quic.configuration import QuicConfiguration
            from aioquic.quic.events import ProtocolNegotiated, QuicEvent
        except ImportError as exc:
            raise RuntimeError("aioquic is required for WebTransport transport") from exc

        host = endpoint.host
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        authority = f"{endpoint.server_name}:{endpoint.port}".encode("utf-8")
        server_name = endpoint.server_name or endpoint.host
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
                if ack.event_id != event_id_value:
                    return False
                return ack.accepted or ack.status == "reject"

        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=H3_ALPN,
            verify_mode=ssl.CERT_REQUIRED if endpoint.verify_tls else ssl.CERT_NONE,
            server_name=server_name,
        )
        configuration.max_datagram_frame_size = 65536

        async with connect(
            host,
            endpoint.port,
            configuration=configuration,
            create_protocol=ClientProtocol,
        ) as protocol:
            client = protocol  # type: ignore[assignment]
            return await client.send_payload(payload, event_id)

    async def _send_datagram_once(
        self,
        frame: bytes,
        event_id: str,
        endpoint: WebTransportEndpoint,
    ) -> None:
        try:
            from aioquic.asyncio import connect
            from aioquic.asyncio.protocol import QuicConnectionProtocol
            from aioquic.h3.connection import H3_ALPN, H3Connection
            from aioquic.h3.events import HeadersReceived
            from aioquic.quic.configuration import QuicConfiguration
            from aioquic.quic.events import ProtocolNegotiated, QuicEvent
        except ImportError as exc:
            raise RuntimeError("aioquic is required for WebTransport transport") from exc

        host = endpoint.host
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        authority = f"{endpoint.server_name}:{endpoint.port}".encode("utf-8")
        server_name = endpoint.server_name or endpoint.host
        timeout_sec = self.timeout_sec

        class DatagramClientProtocol(QuicConnectionProtocol):
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                super().__init__(*args, **kwargs)
                loop = asyncio.get_running_loop()
                self.http: H3Connection | None = None
                self.ready: asyncio.Future[None] = loop.create_future()
                self.connected: asyncio.Future[None] | None = None
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

            async def send_datagram_payload(self, datagram_frame: bytes) -> None:
                await asyncio.wait_for(self.ready, timeout=timeout_sec)
                assert self.http is not None
                loop = asyncio.get_running_loop()
                self.connected = loop.create_future()
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
                self.http.send_datagram(self.session_id, datagram_frame)
                self.transmit()
                await asyncio.sleep(0.2)

        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=H3_ALPN,
            verify_mode=ssl.CERT_REQUIRED if endpoint.verify_tls else ssl.CERT_NONE,
            server_name=server_name,
        )
        configuration.max_datagram_frame_size = 65536

        async with connect(
            host,
            endpoint.port,
            configuration=configuration,
            create_protocol=DatagramClientProtocol,
        ) as protocol:
            client = protocol  # type: ignore[assignment]
            await client.send_datagram_payload(frame)
