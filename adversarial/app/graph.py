"""LangGraph orchestration for a bounded autonomous adversarial run."""

from __future__ import annotations

import asyncio
import warnings
from datetime import UTC, datetime
from typing import Any, TypedDict

from .documentation_agent import DocumentationAgent
from .judge_agent import JudgeAgent
from .models import (
    AgentTraceEvent,
    AttackCase,
    AttackRun,
    JudgeVerdict,
    ObservedResponse,
    RunBudget,
    RunMode,
    Severity,
    StopReason,
    TargetMode,
    Verdict,
    VulnerabilityReport,
)
from .regression_harness import candidate_from_failure
from .run_store import RunStore
from .target_client import TargetClient

warning_category: type[Warning]
try:
    from langchain_core._api.deprecation import (
        LangChainPendingDeprecationWarning as _LangChainPendingDeprecationWarning,
    )

    warning_category = _LangChainPendingDeprecationWarning
except ImportError:  # pragma: no cover - only relevant if langgraph is absent.
    warning_category = PendingDeprecationWarning

warnings.filterwarnings("ignore", category=warning_category)


class AdversarialState(TypedDict, total=False):
    case: AttackCase
    run: AttackRun
    budget: RunBudget
    target_client: TargetClient
    store: RunStore
    observed: ObservedResponse
    verdict: JudgeVerdict
    report: VulnerabilityReport | None


def run_case_with_graph(
    *,
    case: AttackCase,
    target_mode: TargetMode,
    target_url: str,
    run_mode: RunMode,
    budget: RunBudget,
    target_client: TargetClient,
    store: RunStore,
    synthetic_principal: str | None = None,
    target_metadata: dict[str, Any] | None = None,
) -> AttackRun:
    """Run one case through the LangGraph node sequence and persist evidence."""
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only in missing envs
        raise RuntimeError("langgraph is required for adversarial graph execution") from exc

    def trace(state: AdversarialState, agent_name: str, event_type: str, message: str) -> None:
        event = AgentTraceEvent(
            run_id=state["run"].run_id,
            agent_name=agent_name,
            event_type=event_type,
            message=message,
        )
        state["store"].save_trace(event)

    def orchestrator(state: AdversarialState) -> AdversarialState:
        trace(state, "orchestrator", "campaign_selected", f"Selected case {state['case'].case_id}")
        return state

    def red_team(state: AdversarialState) -> AdversarialState:
        case = state["case"]
        if case.parent_case_id:
            message = f"Using bounded variant from {case.parent_case_id}: {case.mutation_rationale}"
            trace(state, "red_team", "generated_variant_used", message)
        else:
            trace(state, "red_team", "seed_case_used", "Using approved seed case for MVP run")
        return state

    def target_runner(state: AdversarialState) -> AdversarialState:
        observed = asyncio.run(state["target_client"].execute_case(state["case"], state["budget"]))
        state["observed"] = observed
        state["store"].save_observation(state["run"].run_id, state["case"].case_id, observed)
        trace(
            state,
            "target_runner",
            "case_executed",
            f"status={observed.status_code} latency_ms={observed.latency_ms}",
        )
        return state

    def judge(state: AdversarialState) -> AdversarialState:
        verdict = JudgeAgent().evaluate(
            run_id=state["run"].run_id,
            case=state["case"],
            observed=state["observed"],
            budget=state["budget"],
        )
        state["verdict"] = verdict
        state["store"].save_verdict(verdict)
        trace(state, "judge", "verdict_recorded", f"{verdict.verdict}: {verdict.reason_code}")
        return state

    def documentation(state: AdversarialState) -> AdversarialState:
        report = DocumentationAgent().draft_report(state["case"], state["verdict"])
        state["report"] = report
        if report:
            state["store"].save_report(report)
            trace(state, "documentation", "draft_report_created", report.vulnerability_id)
        else:
            trace(state, "documentation", "report_skipped", "Passing case did not produce a report")
        return state

    def regression_store(state: AdversarialState) -> AdversarialState:
        verdict = state["verdict"]
        report = state.get("report")
        if verdict.verdict == Verdict.FAIL and state["case"].regression_candidate and report:
            regression = candidate_from_failure(
                report=report,
                case=state["case"],
                promotion_reason="Deterministic failure recorded as regression candidate.",
            )
            state["store"].save_regression_case(regression)
            trace(state, "regression_store", "candidate_recorded", "Failure is regression-eligible")
        else:
            trace(state, "regression_store", "candidate_skipped", "No regression candidate recorded")
        return state

    def stop_policy(state: AdversarialState) -> AdversarialState:
        run = state["run"]
        verdict = state["verdict"]
        observed = state["observed"]
        if verdict.verdict == Verdict.FAIL and verdict.severity == Severity.CRITICAL:
            run.stop_reason = StopReason.CRITICAL_FAILURE
        elif verdict.requires_human_review:
            run.stop_reason = StopReason.HUMAN_REVIEW_GATE
        elif observed.status_code == 0 or observed.status_code >= 500:
            run.stop_reason = StopReason.TARGET_INSTABILITY
        else:
            run.stop_reason = StopReason.COMPLETED
        run.completed_at = datetime.now(UTC)
        run.request_count = observed.request_count
        run.estimated_cost_usd = observed.provider_cost_usd
        state["store"].save_run(run)
        trace(state, "stop_policy", "run_stopped", run.stop_reason)
        return state

    graph = StateGraph(AdversarialState)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("red_team", red_team)
    graph.add_node("target_runner", target_runner)
    graph.add_node("judge", judge)
    graph.add_node("documentation", documentation)
    graph.add_node("regression_store", regression_store)
    graph.add_node("stop_policy", stop_policy)
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "red_team")
    graph.add_edge("red_team", "target_runner")
    graph.add_edge("target_runner", "judge")
    graph.add_edge("judge", "documentation")
    graph.add_edge("documentation", "regression_store")
    graph.add_edge("regression_store", "stop_policy")
    graph.add_edge("stop_policy", END)
    compiled = graph.compile()

    target_version: str | None = None
    if target_metadata:
        api_status = target_metadata.get("api_status")
        if isinstance(api_status, dict):
            version = api_status.get("version") or api_status.get("commit")
            target_version = str(version) if version else None
    run = AttackRun(
        case_id=case.case_id,
        target_mode=target_mode,
        target_url=target_url,
        target_version=target_version,
        run_mode=run_mode,
        synthetic_principal=synthetic_principal,
        target_metadata=target_metadata or {},
    )
    store.save_run(run)
    result: dict[str, Any] = compiled.invoke(
        {
            "case": case,
            "run": run,
            "budget": budget,
            "target_client": target_client,
            "store": store,
        }
    )
    run_result = result["run"]
    if not isinstance(run_result, AttackRun):
        raise TypeError("adversarial graph did not return an AttackRun")
    return run_result
