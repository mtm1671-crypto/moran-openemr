"""Run Week 3 adversarial eval suites."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from time import monotonic
from typing import Any

from .case_loader import load_cases_for_suite
from .config import Settings
from .costing import build_suite_summary
from .graph import run_case_with_graph
from .models import (
    AgentTraceEvent,
    AttackCase,
    AttackRun,
    RunBudget,
    RunMode,
    Severity,
    StopReason,
    TargetMode,
    Verdict,
    utc_now,
)
from .orchestrator import prioritize_cases
from .red_team_agent import RedTeamAgent
from .reporting import latest_verdict_by_case
from .resilience import build_resilience_snapshot
from .run_store import RunStore
from .synthetic_auth import resolve_synthetic_clinician_token
from .target_client import TargetClient


def build_budget(settings: Settings) -> RunBudget:
    return RunBudget(
        max_requests_per_case=settings.max_requests_per_case,
        max_latency_ms_per_case=settings.max_latency_ms_per_case,
        max_token_estimate_per_case=settings.max_token_estimate_per_case,
        max_provider_cost_usd_per_case=settings.max_provider_cost_usd_per_case,
        max_retries_per_case=settings.max_retries_per_case,
        max_loop_depth=settings.max_loop_depth,
        max_variants_per_case=settings.max_variants_per_case,
        max_wall_clock_seconds=settings.max_wall_clock_seconds,
    )


def run_suite(
    *,
    settings: Settings,
    suite: str,
    run_mode: RunMode,
    case_root: Path | None = None,
    include_variants: bool = False,
) -> list[str]:
    settings.validate_ready_for_run()
    store = RunStore(settings.sqlite_path, private_path=settings.private_sqlite_path)
    store.initialize()
    seed_cases = load_cases_for_suite(suite, case_root)
    if suite == "regression":
        seed_cases.extend(
            AttackCase.model_validate(regression["replay_case"])
            for regression in store.regression_cases()
            if regression.get("status") == "promoted"
        )
    bearer_token = asyncio.run(resolve_synthetic_clinician_token(settings))
    client = TargetClient(settings.target_url, bearer_token=bearer_token)
    budget = build_budget(settings)
    cases = list(seed_cases)
    if include_variants:
        red_team = RedTeamAgent()
        for seed_case in seed_cases:
            cases.extend(red_team.generate_variants(seed_case, budget))
    cases = prioritize_cases(
        cases,
        persisted_cases=store.cases(),
        latest_runs=store.latest_runs(limit=500),
        verdicts=store.verdicts(),
        reports=store.reports(),
    )
    store.save_cases(cases)
    suite_started = monotonic()
    target_metadata = asyncio.run(client.metadata())
    synthetic_principal = _synthetic_principal_label(settings)
    run_ids: list[str] = []
    for case in cases:
        if monotonic() - suite_started >= budget.max_wall_clock_seconds:
            run = _timeout_run(
                case=case,
                settings=settings,
                run_mode=run_mode,
                synthetic_principal=synthetic_principal,
                target_metadata=target_metadata,
            )
            store.save_run(run)
            store.save_trace(
                AgentTraceEvent(
                    run_id=run.run_id,
                    agent_name="stop_policy",
                    event_type="suite_timeout",
                    message="Suite wall-clock budget exceeded before case execution",
                )
            )
            run_ids.append(run.run_id)
            break
        run = run_case_with_graph(
            case=case,
            target_mode=settings.target_mode,
            target_url=settings.target_url,
            run_mode=run_mode,
            budget=budget,
            target_client=client,
            store=store,
            synthetic_principal=synthetic_principal,
            target_metadata=target_metadata,
        )
        run_ids.append(run.run_id)
    suite_observations = [
        observation
        for run_id in run_ids
        for observation in store.observations(run_id)
    ]
    suite_verdicts = [
        verdict for verdict in store.verdicts() if str(verdict.get("run_id", "")) in set(run_ids)
    ]
    store.save_suite_summary(
        build_suite_summary(
            suite=suite,
            target_mode=settings.target_mode,
            run_mode=run_mode,
            run_ids=run_ids,
            observations=suite_observations,
            verdicts=suite_verdicts,
        )
    )
    if run_ids:
        latest_verdicts = list(
            latest_verdict_by_case(store.verdicts(), store.latest_runs(limit=500)).values()
        )
        store.save_snapshot(
            build_resilience_snapshot(
                run_id=run_ids[-1],
                cases=store.cases(),
                latest_verdicts=latest_verdicts,
                reports=store.reports(),
                regression_cases=store.regression_cases(),
            )
        )
    return run_ids


def _timeout_run(
    *,
    case: AttackCase,
    settings: Settings,
    run_mode: RunMode,
    synthetic_principal: str | None,
    target_metadata: dict[str, Any],
) -> AttackRun:
    return AttackRun(
        case_id=case.case_id,
        target_mode=settings.target_mode,
        target_url=settings.target_url,
        target_version=_target_version(target_metadata),
        run_mode=run_mode,
        completed_at=utc_now(),
        stop_reason=StopReason.TIMEOUT,
        synthetic_principal=synthetic_principal,
        target_metadata=target_metadata,
    )


def _target_version(target_metadata: dict[str, Any]) -> str | None:
    api_status = target_metadata.get("api_status")
    if not isinstance(api_status, dict):
        return None
    version = api_status.get("version") or api_status.get("commit")
    return str(version) if version else None


def _synthetic_principal_label(settings: Settings) -> str | None:
    if settings.synthetic_clinician_username:
        return f"synthetic-clinician:{settings.synthetic_clinician_username}"
    if settings.synthetic_clinician_token:
        return "synthetic-clinician:bearer-token"
    if settings.has_synthetic_clinician_auth:
        return "synthetic-clinician:password-grant"
    return None


def blocking_verdicts(store: RunStore, run_ids: list[str]) -> list[dict[str, Any]]:
    run_id_set = set(run_ids)
    blocking_severities = {Severity.CRITICAL.value, Severity.HIGH.value}
    return [
        verdict
        for verdict in store.verdicts()
        if verdict.get("run_id") in run_id_set
        and verdict.get("verdict") == Verdict.FAIL.value
        and verdict.get("severity") in blocking_severities
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=[mode.value for mode in TargetMode], default=None)
    parser.add_argument("--suite", choices=["smoke", "seed", "regression"], default="seed")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--report-only", action="store_true")
    mode.add_argument("--enforce", action="store_true")
    parser.add_argument("--include-variants", action="store_true")
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    settings = Settings()
    if args.target:
        settings.target_mode = TargetMode(args.target)
    if args.db:
        settings.sqlite_path = args.db
    settings.validate_ready_for_run()
    run_mode = RunMode.ENFORCE if args.enforce else RunMode.REPORT_ONLY
    run_ids = run_suite(
        settings=settings,
        suite=args.suite,
        run_mode=run_mode,
        include_variants=args.include_variants,
    )
    print(f"Week 3 adversarial suite complete: {len(run_ids)} run(s)")
    for run_id in run_ids:
        print(run_id)
    if run_mode == RunMode.ENFORCE:
        store = RunStore(settings.sqlite_path, private_path=settings.private_sqlite_path)
        blockers = blocking_verdicts(store, run_ids)
        if blockers:
            print(f"enforce gate blocked: {len(blockers)} critical/high failure(s)")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
