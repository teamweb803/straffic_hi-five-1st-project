from __future__ import annotations

import asyncio
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ForwardResult:
    accepted: bool
    retryable: bool
    status_code: int | None
    detail: str = ""


@dataclass
class SpringForwarder:
    endpoint: str
    timeout_sec: float = 3.0
    ingest_key: str = ""
    dry_run: bool = False

    async def forward(self, payload: bytes, event_id: str) -> ForwardResult:
        if self.dry_run:
            return ForwardResult(True, False, 200, "dry-run")
        if not self.endpoint:
            return ForwardResult(False, True, None, "missing spring endpoint")

        try:
            return await self._forward_with_httpx(payload, event_id)
        except ImportError:
            return await asyncio.to_thread(self._forward_with_urllib, payload, event_id)

    async def _forward_with_httpx(self, payload: bytes, event_id: str) -> ForwardResult:
        import httpx

        headers = self._headers(event_id)
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            try:
                response = await client.post(self.endpoint, content=payload, headers=headers)
            except httpx.RequestError as exc:
                return ForwardResult(False, True, None, str(exc))
        return self._result_from_status(response.status_code, response.text[:200])

    def _forward_with_urllib(self, payload: bytes, event_id: str) -> ForwardResult:
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers=self._headers(event_id),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                body = response.read(200).decode("utf-8", errors="replace")
                return self._result_from_status(int(response.status), body)
        except urllib.error.HTTPError as exc:
            body = exc.read(200).decode("utf-8", errors="replace")
            return self._result_from_status(int(exc.code), body)
        except Exception as exc:
            return ForwardResult(False, True, None, str(exc))

    def _headers(self, event_id: str) -> dict[str, str]:
        headers = {
            "content-type": "application/x-protobuf",
            "x-event-id": event_id,
            "x-ingest-source": "python-webtransport-ingress",
        }
        if self.ingest_key:
            headers["x-internal-ingest-key"] = self.ingest_key
        return headers

    def _result_from_status(self, status_code: int, detail: str) -> ForwardResult:
        if 200 <= status_code < 300:
            return ForwardResult(True, False, status_code, detail)
        if status_code == 409:
            return ForwardResult(True, False, status_code, "duplicate")
        if 400 <= status_code < 500:
            return ForwardResult(False, False, status_code, detail)
        return ForwardResult(False, True, status_code, detail)
