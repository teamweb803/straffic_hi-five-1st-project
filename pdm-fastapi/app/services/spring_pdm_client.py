from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

import httpx

from app.schemas.pdm import QualityMetric

logger = logging.getLogger("pdm.spring_client")


class SpringFetchError(Exception):
    """Spring 품질 지표 조회 실패."""


class SpringPdmClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.base_url = (base_url or os.getenv("SPRING_BASE_URL") or "http://localhost:8585").rstrip("/")
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(base_url=self.base_url, timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    # --- 내부: 재시도 래퍼 (네트워크 오류 / 5xx 만 재시도) ---
    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"{response.status_code} server error",
                        request=response.request,
                        response=response,
                    )
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    logger.warning(
                        "Spring %s %s 실패(시도 %d/%d): %s -> 재시도",
                        method, url, attempt + 1, self.max_retries + 1, exc,
                    )
                    if self.retry_backoff_seconds > 0:
                        time.sleep(self.retry_backoff_seconds * (attempt + 1))
                else:
                    logger.error(
                        "Spring %s %s 최종 실패(시도 %d): %s",
                        method, url, attempt + 1, exc,
                    )
        assert last_exc is not None
        raise last_exc

    def fetch_quality_metrics(
        self,
        camera_id: int,
        lane_id: int | None = None,
        query_from: datetime | None = None,
        query_to: datetime | None = None,
    ) -> list[QualityMetric]:
        params: dict[str, Any] = {}
        if lane_id is not None:
            params["laneId"] = lane_id
        if query_from is not None:
            params["from"] = query_from.isoformat()
        if query_to is not None:
            params["to"] = query_to.isoformat()

        url = f"/api/v1/pdm/cameras/{camera_id}/quality-metrics"
        try:
            response = self._request_with_retry("GET", url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.error(
                "품질 지표 조회 실패 url=%s status=%s from=%s to=%s",
                url, status, query_from, query_to,
            )
            raise SpringFetchError(str(exc)) from exc

        data = _unwrap_common_response(response.json())
        return [QualityMetric(**item) for item in data]

    def save_analysis_results(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """기존 동작 유지: 하나라도 실패하면 예외 전파(기존 호출부 호환)."""
        saved_responses: list[dict[str, Any]] = []
        for payload in payloads:
            response = self._request_with_retry("POST", "/api/v1/pdm/analysis-results", json=payload)
            response.raise_for_status()
            saved_responses.append(response.json())
        return saved_responses

    def save_analysis_results_resilient(
        self,
        payloads: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """payload별로 저장. 하나가 실패해도 나머지는 계속 저장한다(가이드 §11).

        반환: (저장 성공 payload, 저장 실패 payload)
        - 409 Conflict는 '이미 저장됨'으로 보고 성공 취급(중복 방지 계약).
        """
        saved: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for payload in payloads:
            try:
                response = self._request_with_retry(
                    "POST", "/api/v1/pdm/analysis-results", json=payload
                )
                if response.status_code == 409:
                    logger.info(
                        "이미 저장됨(409) camera=%s lane=%s model=%s -> 성공 취급",
                        payload.get("cameraId"), payload.get("laneId"), payload.get("modelType"),
                    )
                    saved.append(payload)
                    continue
                response.raise_for_status()
                saved.append(payload)
            except httpx.HTTPError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                logger.error(
                    "분석 결과 저장 실패 camera=%s lane=%s model=%s status=%s",
                    payload.get("cameraId"), payload.get("laneId"),
                    payload.get("modelType"), status,
                )
                failed.append(payload)
        return saved, failed

    def save_analysis_results_batch_resilient(
        self,
        payloads: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Spring batch API로 한 분석 window의 모델 결과를 함께 저장한다.

        Spring이 batch 내부에서 종합 점수와 알림 1개를 만든다.
        batch 전체 실패 시 이번 payload 묶음은 다음 tick에서 다시 시도한다.
        """
        if not payloads:
            return [], []

        try:
            response = self._request_with_retry(
                "POST",
                "/api/v1/pdm/analysis-results/batch",
                json={"results": payloads},
            )
            if response.status_code == 409:
                logger.info("batch 이미 저장됨(409) -> 성공 취급 count=%d", len(payloads))
                return payloads, []
            response.raise_for_status()
            return payloads, []
        except httpx.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.error("batch 분석 결과 저장 실패 count=%d status=%s", len(payloads), status)
            return [], payloads


def _unwrap_common_response(body: Any) -> Any:
    if isinstance(body, dict) and "data" in body and "success" in body:
        return body["data"]
    return body
