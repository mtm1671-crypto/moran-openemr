"""Black-box HTTP target client for Co-Pilot adversarial cases."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .models import AttackCase, Citation, ObservedResponse, RunBudget


class TargetClient:
    def __init__(self, base_url: str, bearer_token: str | None = None, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds

    async def readiness(self) -> ObservedResponse:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/readyz")
            return ObservedResponse(
                status_code=response.status_code,
                text=response.text,
                latency_ms=int((time.perf_counter() - started) * 1000),
                gray_box_metadata={"endpoint": "/readyz"},
            )
        except httpx.HTTPError as exc:
            return ObservedResponse(
                status_code=0,
                text=f"target readiness failed: {exc}",
                latency_ms=int((time.perf_counter() - started) * 1000),
                gray_box_metadata={"endpoint": "/readyz", "error": type(exc).__name__},
            )

    async def metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {"base_url": self.base_url}
        readiness = await self.readiness()
        metadata["readyz_status_code"] = readiness.status_code
        metadata["readyz_preview"] = readiness.text[:300]
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/status")
            metadata["api_status_code"] = response.status_code
            if "application/json" in response.headers.get("content-type", ""):
                payload = response.json()
                if isinstance(payload, dict):
                    metadata["api_status"] = {
                        key: value
                        for key, value in payload.items()
                        if key in {"status", "version", "commit", "environment", "service"}
                    }
            else:
                metadata["api_status_preview"] = response.text[:300]
        except (httpx.HTTPError, ValueError) as exc:
            metadata["api_status_error"] = type(exc).__name__
        return metadata

    async def execute_case(self, case: AttackCase, budget: RunBudget) -> ObservedResponse:
        started = time.perf_counter()
        headers = {"content-type": "application/json"}
        if self.bearer_token:
            headers["authorization"] = f"Bearer {self.bearer_token}"
        body: dict[str, Any] = {
            "message": case.input_sequence[-1],
            "messages": [{"role": "user", "content": prompt} for prompt in case.input_sequence],
            "patient_id": case.selected_patient_id,
        }
        try:
            async with httpx.AsyncClient(timeout=budget.max_latency_ms_per_case / 1000) as client:
                response = await client.post(
                    f"{self.base_url}{case.target_route}",
                    headers=headers,
                    json=body,
                )
            text, citations, tool_outcome = self._extract_response_parts(response)
            return ObservedResponse(
                status_code=response.status_code,
                text=text,
                citations=citations,
                tool_outcome=tool_outcome,
                request_count=1,
                latency_ms=int((time.perf_counter() - started) * 1000),
                token_estimate=self._estimate_tokens(body, text),
                black_box_metadata={
                    "route": case.target_route,
                    "response_headers": {
                        key: value
                        for key, value in response.headers.items()
                        if key.lower() in {"content-type", "x-request-id", "x-trace-id"}
                    },
                },
            )
        except httpx.HTTPError as exc:
            return ObservedResponse(
                status_code=0,
                text=f"target request failed: {exc}",
                request_count=1,
                latency_ms=int((time.perf_counter() - started) * 1000),
                black_box_metadata={"route": case.target_route, "error": type(exc).__name__},
            )

    def _extract_response_parts(
        self, response: httpx.Response
    ) -> tuple[str, list[Citation], str | None]:
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            if "text/event-stream" in content_type:
                return self._extract_sse_response_parts(response.text)
            return response.text, [], None
        try:
            payload = response.json()
        except ValueError:
            return response.text, [], None
        return self._extract_json_response_parts(payload, response.text)

    def _extract_sse_response_parts(self, body: str) -> tuple[str, list[Citation], str | None]:
        final_payload: dict[str, Any] | None = None
        current_event: str | None = None
        data_lines: list[str] = []

        for line in body.splitlines():
            if not line:
                if current_event == "final" and data_lines:
                    try:
                        payload = json.loads("\n".join(data_lines))
                    except ValueError:
                        payload = None
                    if isinstance(payload, dict):
                        final_payload = payload
                current_event = None
                data_lines = []
                continue
            if line.startswith("event:"):
                current_event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())

        if current_event == "final" and data_lines and final_payload is None:
            try:
                payload = json.loads("\n".join(data_lines))
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                final_payload = payload

        if final_payload is None:
            return body, [], None
        return self._extract_json_response_parts(final_payload, body)

    def _extract_json_response_parts(
        self, payload: dict[str, Any], fallback_text: str
    ) -> tuple[str, list[Citation], str | None]:
        text = (
            payload.get("answer")
            or payload.get("message")
            or payload.get("content")
            or payload.get("text")
            or fallback_text
        )
        raw_citations = payload.get("citations") or payload.get("sources") or []
        citations: list[Citation] = []
        if isinstance(raw_citations, list):
            for raw in raw_citations:
                if isinstance(raw, dict):
                    citations.append(
                        Citation(
                            source_id=str(
                                raw.get("source_id")
                                or raw.get("evidence_id")
                                or raw.get("id")
                                or raw.get("url")
                                or "unknown"
                            ),
                            patient_id=raw.get("patient_id"),
                            quote=raw.get("quote") or raw.get("text"),
                            url=raw.get("url") or raw.get("source_url"),
                        )
                    )
        tool_outcome = payload.get("tool_outcome") if isinstance(payload.get("tool_outcome"), str) else None
        return str(text), citations, tool_outcome

    def _estimate_tokens(self, request_body: dict[str, Any], response_text: str) -> int:
        text = f"{request_body} {response_text}"
        return max(1, len(text) // 4)
