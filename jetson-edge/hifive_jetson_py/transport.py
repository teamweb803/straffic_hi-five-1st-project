from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import TransportConfig
from .spool import FileSpool
from .webtransport_transport import WebTransportIngressSender


class Sender(Protocol):
    def submit(self, payload: bytes, event_id: str) -> bool:
        ...


@dataclass
class DryRunSender:
    spool: FileSpool

    def submit(self, payload: bytes, event_id: str) -> bool:
        self.spool.enqueue(payload, event_id=event_id)
        print(f"dry-run spooled event_id={event_id} bytes={len(payload)}")
        return True


def build_sender(config: TransportConfig, spool: FileSpool) -> Sender:
    if config.dry_run:
        return DryRunSender(spool)
    if config.kind == "webtransport_ingress":
        return WebTransportIngressSender(
            host=config.ingress_host,
            port=config.ingress_port,
            path=config.webtransport_path,
            server_name=config.server_name or config.ingress_host,
            verify_tls=config.verify_tls,
            timeout_sec=config.timeout_sec,
            spool=spool,
            retry_enabled=config.retry_enabled,
            retry_initial_sec=config.retry_initial_sec,
            retry_max_sec=config.retry_max_sec,
            retry_max_items_per_cycle=config.retry_max_items_per_cycle,
        )
    raise ValueError(f"unsupported transport kind: {config.kind}")
