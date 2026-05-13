from __future__ import annotations

import argparse
import asyncio
import logging
import ssl
import time

from hifive_jetson_py.ingress_state import IngressStats
from hifive_jetson_py.spring_forwarder import SpringForwarder, SpringJsonForwarder
from hifive_jetson_py.webtransport_ingress import WebTransportIngressFactory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HI-FIVE WebTransport ingress to Spring REST")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--wt-path", default="/hifive/edge")
    parser.add_argument("--spring-url", default="http://127.0.0.1:8080/api/ingest/passage-events")
    parser.add_argument("--spring-edge-status-url", default="")
    parser.add_argument("--spring-ingress-status-url", default="")
    parser.add_argument("--ingress-status-forward-interval-sec", type=float, default=0.0)
    parser.add_argument("--spring-timeout-sec", type=float, default=3.0)
    parser.add_argument("--ingest-key", default="")
    parser.add_argument("--dry-run-spring", action="store_true")
    parser.add_argument("--ops-host", default="0.0.0.0")
    parser.add_argument("--ops-port", type=int, default=8000)
    return parser.parse_args()


def build_ops_app(stats: IngressStats):
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI(title="HI-FIVE Python Ingress Ops")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict:
        return stats.snapshot()

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        snapshot = stats.snapshot()
        lines = []
        for key, value in snapshot.items():
            if isinstance(value, (int, float)):
                lines.append(f"hifive_ingress_{key} {value}")
        return "\n".join(lines) + "\n"

    return app


async def run_ops_api(stats: IngressStats, host: str, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(build_ops_app(stats), host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def forward_ingress_status_loop(
    stats: IngressStats,
    forwarder: SpringJsonForwarder,
    interval_sec: float,
) -> None:
    interval = max(0.2, interval_sec)
    while True:
        ts_ms = int(time.time() * 1000)
        event_id = f"ingress-status-{ts_ms}"
        payload = {
            "type": "ingress_status",
            "schema_version": "hifive.ingress_status.v1",
            "ts_ms": ts_ms,
            "status": stats.snapshot(),
        }
        result = await forwarder.forward(payload, event_id)
        if result.accepted:
            stats.mark_ingress_status_forward(event_id, "accepted", result.status_code, result.detail)
        elif result.retryable:
            stats.mark_ingress_status_forward(event_id, "retry", result.status_code, result.detail)
        else:
            stats.mark_ingress_status_forward(event_id, "rejected", result.status_code, result.detail)
        await asyncio.sleep(interval)


async def async_main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="INFO:     %(message)s")

    from aioquic.asyncio import serve
    from aioquic.h3.connection import H3_ALPN
    from aioquic.quic.configuration import QuicConfiguration

    stats = IngressStats()
    forwarder = SpringForwarder(
        endpoint=args.spring_url,
        timeout_sec=args.spring_timeout_sec,
        ingest_key=args.ingest_key,
        dry_run=args.dry_run_spring,
    )
    edge_status_forwarder = None
    if args.spring_edge_status_url or args.dry_run_spring:
        edge_status_forwarder = SpringJsonForwarder(
            endpoint=args.spring_edge_status_url,
            timeout_sec=args.spring_timeout_sec,
            ingest_key=args.ingest_key,
            dry_run=args.dry_run_spring,
        )
    ingress_status_forwarder = None
    if args.spring_ingress_status_url or args.dry_run_spring:
        ingress_status_forwarder = SpringJsonForwarder(
            endpoint=args.spring_ingress_status_url,
            timeout_sec=args.spring_timeout_sec,
            ingest_key=args.ingest_key,
            dry_run=args.dry_run_spring,
        )

    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=H3_ALPN,
        verify_mode=ssl.CERT_NONE,
    )
    configuration.max_datagram_frame_size = 65536
    configuration.load_cert_chain(args.cert, args.key)

    await serve(
        args.host,
        args.port,
        configuration=configuration,
        create_protocol=WebTransportIngressFactory(
            path=args.wt_path,
            forwarder=forwarder,
            edge_status_forwarder=edge_status_forwarder,
            stats=stats,
        ).create(),
    )
    asyncio.create_task(run_ops_api(stats, args.ops_host, args.ops_port))
    if args.ingress_status_forward_interval_sec > 0 and ingress_status_forwarder is not None:
        asyncio.create_task(
            forward_ingress_status_loop(
                stats,
                ingress_status_forwarder,
                args.ingress_status_forward_interval_sec,
            )
        )
    print(f"WebTransport ingress listening on {args.host}:{args.port}{args.wt_path}")
    print(f"Ops API listening on http://{args.ops_host}:{args.ops_port}")
    await asyncio.Future()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
