import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx


_DEFAULT_RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.WriteError,
)


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0
    retry_status_codes: frozenset[int] = field(default_factory=lambda: _DEFAULT_RETRYABLE_STATUS_CODES)


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    policy: RetryPolicy,
    **kwargs: Any,
) -> httpx.Response:
    attempts = max(policy.attempts, 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code in policy.retry_status_codes:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                if attempt < attempts - 1:
                    await _sleep_before_retry(policy, attempt)
                    continue
            response.raise_for_status()
            return response
        except _RETRYABLE_EXCEPTIONS as exc:
            last_error = exc
            if attempt < attempts - 1:
                await _sleep_before_retry(policy, attempt)
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("HTTP retry loop exited without a response")


async def _sleep_before_retry(policy: RetryPolicy, attempt: int) -> None:
    delay = min(policy.backoff_seconds * (2**attempt), policy.max_backoff_seconds)
    if delay > 0:
        await asyncio.sleep(delay)
