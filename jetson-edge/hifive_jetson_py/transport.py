from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Protocol

from .config import TransportConfig
from .spool import FileSpool
from .webtransport_transport import WebTransportIngressSender


class Sender(Protocol):
    def submit(self, payload: bytes, event_id: str) -> bool:
        ...

    def submit_latest(self, payload: bytes, event_id: str) -> bool:
        ...

    def snapshot(self) -> dict:
        ...


@dataclass
class DryRunSender:
    spool: FileSpool

    def submit(self, payload: bytes, event_id: str) -> bool:
        self.spool.enqueue(payload, event_id=event_id)
        print(f"dry-run spooled event_id={event_id} bytes={len(payload)}")
        return True

    def submit_latest(self, payload: bytes, event_id: str) -> bool:
        print(f"dry-run latest event_id={event_id} bytes={len(payload)}")
        return True

    def snapshot(self) -> dict:
        return {"kind": "dry_run", "active_path": "dry_run"}


@dataclass
class QueuedSender:
    delegate: Sender
    spool: FileSpool
    queue_size: int = 128

    def __post_init__(self) -> None:
        self._queue: queue.Queue[tuple[bytes, str]] = queue.Queue(maxsize=max(1, self.queue_size))
        self._dropped_to_spool = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run_forever, name="hifive-queued-sender", daemon=True)
        self._thread.start()

    def submit(self, payload: bytes, event_id: str) -> bool:
        try:
            self._queue.put_nowait((payload, event_id))
            return True
        except queue.Full:
            self.spool.enqueue(payload, event_id=event_id)
            with self._lock:
                self._dropped_to_spool += 1
            print(f"transport queue full; spooled event_id={event_id}")
            return False

    def submit_latest(self, payload: bytes, event_id: str) -> bool:
        return self.delegate.submit_latest(payload, event_id)

    def snapshot(self) -> dict:
        snapshot = dict(self.delegate.snapshot())
        with self._lock:
            dropped_to_spool = self._dropped_to_spool
        snapshot.update(
            {
                "queued_sender": True,
                "queued_events": self._queue.qsize(),
                "queue_size": self.queue_size,
                "queue_full_spooled_events": dropped_to_spool,
            }
        )
        return snapshot

    def drain(self) -> None:
        self._queue.join()

    def _run_forever(self) -> None:
        while True:
            payload, event_id = self._queue.get()
            try:
                self.delegate.submit(payload, event_id)
            except Exception as exc:
                try:
                    self.spool.enqueue(payload, event_id=event_id)
                except Exception as spool_exc:
                    print(
                        f"queued transport failed event_id={event_id}: {exc}; "
                        f"spool fallback failed: {spool_exc}"
                    )
                else:
                    print(f"queued transport failed; spooled event_id={event_id}: {exc}")
            finally:
                self._queue.task_done()


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
            failover_enabled=config.failover_enabled,
            standby_host=config.standby_ingress_host,
            standby_port=config.standby_ingress_port,
            standby_server_name=config.standby_server_name,
            standby_verify_tls=config.standby_verify_tls,
            failover_recheck_sec=config.failover_recheck_sec,
        )
    raise ValueError(f"unsupported transport kind: {config.kind}")
