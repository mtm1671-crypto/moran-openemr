"""Cost and budget rollups for adversarial runs."""

from __future__ import annotations

from typing import Any

from .models import RunMode, SuiteSummary, TargetMode, Verdict


def build_suite_summary(
    *,
    suite: str,
    target_mode: TargetMode,
    run_mode: RunMode,
    run_ids: list[str],
    observations: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
) -> SuiteSummary:
    observation_run_ids = set(run_ids)
    relevant_observations = [
        observation
        for observation in observations
        if str(observation.get("black_box_metadata", {}).get("run_id", ""))
        in observation_run_ids
        or str(observation.get("run_id", "")) in observation_run_ids
    ]
    if not relevant_observations:
        relevant_observations = observations

    relevant_verdicts = [verdict for verdict in verdicts if str(verdict.get("run_id", "")) in set(run_ids)]
    verdict_counts = {verdict.value: 0 for verdict in Verdict}
    for verdict in relevant_verdicts:
        verdict_name = str(verdict.get("verdict", ""))
        if verdict_name in verdict_counts:
            verdict_counts[verdict_name] += 1

    return SuiteSummary(
        suite=suite,
        target_mode=target_mode,
        run_mode=run_mode,
        run_ids=run_ids,
        total_requests=sum(int(observation.get("request_count", 0)) for observation in relevant_observations),
        total_latency_ms=sum(int(observation.get("latency_ms", 0)) for observation in relevant_observations),
        total_token_estimate=sum(
            int(observation.get("token_estimate", 0)) for observation in relevant_observations
        ),
        total_provider_cost_usd=sum(
            float(observation.get("provider_cost_usd", 0.0)) for observation in relevant_observations
        ),
        pass_count=verdict_counts[Verdict.PASS.value],
        fail_count=verdict_counts[Verdict.FAIL.value],
        partial_count=verdict_counts[Verdict.PARTIAL.value],
        inconclusive_count=verdict_counts[Verdict.INCONCLUSIVE.value],
    )


def observation_cost_summary(observations: list[dict[str, Any]]) -> dict[str, float | int]:
    return {
        "request_count": sum(int(observation.get("request_count", 0)) for observation in observations),
        "latency_ms": sum(int(observation.get("latency_ms", 0)) for observation in observations),
        "token_estimate": sum(int(observation.get("token_estimate", 0)) for observation in observations),
        "provider_cost_usd": round(
            sum(float(observation.get("provider_cost_usd", 0.0)) for observation in observations),
            6,
        ),
    }
