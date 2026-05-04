from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import TypeVar

from app.config import Settings
from app.telemetry import emit_telemetry_event

T = TypeVar("T")

PHI_SAFE_METADATA_KEYS = {
    "document_job_id",
    "route_id",
    "step",
    "worker",
    "status",
    "outcome",
    "latency_ms",
    "provider",
    "model",
    "input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "confidence_bucket",
    "review_decision_count",
    "written_count",
    "skipped_count",
    "failed_count",
    "verifier_code",
}


def phi_safe_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in metadata.items() if key in PHI_SAFE_METADATA_KEYS}


def observe_step(
    *,
    settings: Settings,
    step: str,
    metadata: dict[str, object] | None,
    fn: Callable[[], T],
) -> T:
    started = perf_counter()
    try:
        result = fn()
    except Exception as exc:
        emit_telemetry_event(
            settings,
            event="w2_step_failed",
            metadata=phi_safe_metadata(
                {
                    **(metadata or {}),
                    "step": step,
                    "outcome": "failure",
                    "latency_ms": int((perf_counter() - started) * 1000),
                    "verifier_code": exc.__class__.__name__,
                }
            ),
        )
        raise
    emit_telemetry_event(
        settings,
        event="w2_step_completed",
        metadata=phi_safe_metadata(
            {
                **(metadata or {}),
                "step": step,
                "outcome": "success",
                "latency_ms": int((perf_counter() - started) * 1000),
            }
        ),
    )
    return result


def estimated_llm_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_million: float,
    output_cost_per_million: float,
) -> float:
    return round(
        (input_tokens / 1_000_000 * input_cost_per_million)
        + (output_tokens / 1_000_000 * output_cost_per_million),
        6,
    )

