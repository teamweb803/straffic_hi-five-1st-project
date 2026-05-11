from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpoolItem:
    path: Path
    payload: bytes
    event_id: str
    attempts: int = 0
    created_ns: int = 0
    last_attempt_ns: int = 0


class FileSpool:
    def __init__(self, root: str | Path, max_items: int = 100_000) -> None:
        self.root = Path(root)
        self.max_items = max_items
        self.root.mkdir(parents=True, exist_ok=True)

    def enqueue(self, payload: bytes, event_id: str = "") -> SpoolItem:
        if not payload:
            raise ValueError("empty payload cannot be spooled")
        if self.count() >= self.max_items:
            raise RuntimeError("spool backpressure: max item count reached")
        now_ns = time.time_ns()
        safe_event_id = self._safe_event_id(event_id) or uuid.uuid4().hex
        name = f"{now_ns}_{safe_event_id}_{uuid.uuid4().hex}.pb"
        tmp_path = self.root / f"{name}.tmp"
        final_path = self.root / name
        with tmp_path.open("wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)

        item = SpoolItem(path=final_path, payload=payload, event_id=event_id, created_ns=now_ns)
        self._write_meta(item)
        return item

    def iter_items(self) -> list[SpoolItem]:
        items: list[SpoolItem] = []
        for path in sorted(self.root.glob("*.pb")):
            try:
                payload = path.read_bytes()
            except FileNotFoundError:
                continue
            meta = self._read_meta(path)
            event_id = str(meta.get("event_id") or self._event_id_from_name(path))
            items.append(
                SpoolItem(
                    path=path,
                    payload=payload,
                    event_id=event_id,
                    attempts=int(meta.get("attempts") or 0),
                    created_ns=int(meta.get("created_ns") or 0),
                    last_attempt_ns=int(meta.get("last_attempt_ns") or 0),
                )
            )
        return items

    def ack(self, item: SpoolItem) -> None:
        try:
            item.path.unlink()
        except FileNotFoundError:
            pass
        try:
            self._meta_path(item.path).unlink()
        except FileNotFoundError:
            pass

    def record_attempt(self, item: SpoolItem) -> SpoolItem:
        updated = SpoolItem(
            path=item.path,
            payload=item.payload,
            event_id=item.event_id,
            attempts=item.attempts + 1,
            created_ns=item.created_ns,
            last_attempt_ns=time.time_ns(),
        )
        self._write_meta(updated)
        return updated

    def count(self) -> int:
        return sum(1 for _ in self.root.glob("*.pb"))

    def _write_meta(self, item: SpoolItem) -> None:
        body = asdict(item)
        body.pop("payload", None)
        body["path"] = item.path.name
        tmp_path = self._meta_path(item.path).with_suffix(".json.tmp")
        final_path = self._meta_path(item.path)
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)

    def _read_meta(self, path: Path) -> dict:
        try:
            return json.loads(self._meta_path(path).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _meta_path(self, path: Path) -> Path:
        return path.with_suffix(path.suffix + ".json")

    def _safe_event_id(self, event_id: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", event_id)[:160]

    def _event_id_from_name(self, path: Path) -> str:
        parts = path.stem.split("_")
        if len(parts) >= 3:
            return "_".join(parts[1:-1])
        return path.stem
