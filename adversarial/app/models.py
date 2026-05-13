"""Typed contracts for Week 3 adversarial runs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class TargetMode(StrEnum):
    LOCAL = "local"
    DEPLOYED = "deployed"


class RunMode(StrEnum):
    REPORT_ONLY = "report-only"
    ENFORCE = "enforce"


class Severity(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class ImpactDomain(StrEnum):
    PHI = "PHI"
    PATIENT_SAFETY = "Patient Safety"
    AUTHORIZATION = "Authorization"
    CLINICAL_WORKFLOW = "Clinical Workflow"
    OPERATIONAL_COST = "Operational Cost"
    REPUTATION = "Reputation"


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


class ReportStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    RESOLVED = "resolved"


class CaseApprovalStatus(StrEnum):
    APPROVED = "approved"
    PROPOSED = "proposed"


class RegressionStatus(StrEnum):
    CANDIDATE = "candidate"
    PROMOTED = "promoted"
    RETIRED = "retired"


class InjectionLayer(StrEnum):
    NONE = "none"
    PROMPT_SIMULATION = "prompt_simulation"
    UPLOADED_DOCUMENT = "uploaded_document"
    SEEDED_NOTE = "seeded_note"


class StopReason(StrEnum):
    NOT_STOPPED = "not_stopped"
    BUDGET_CAP = "budget_cap"
    CRITICAL_FAILURE = "critical_failure"
    HUMAN_REVIEW_GATE = "human_review_gate"
    TARGET_INSTABILITY = "target_instability"
    SUFFICIENT_COVERAGE = "sufficient_coverage"
    LOW_SIGNAL = "low_signal"
    TIMEOUT = "timeout"
    OPERATOR_CANCELLED = "operator_cancelled"
    COMPLETED = "completed"


class AttackCategory(StrEnum):
    DIRECT_PROMPT_INJECTION = "direct_prompt_injection"
    CROSS_PATIENT_PHI = "cross_patient_phi"
    AUTHORIZATION_SESSION = "authorization_session"
    CLINICAL_RECOMMENDATION = "clinical_recommendation"
    INDIRECT_INJECTION = "indirect_injection"
    MULTI_TURN_MANIPULATION = "multi_turn_manipulation"
    TOOL_MISUSE = "tool_misuse"
    COST_AMPLIFICATION = "cost_amplification"
    CITATION_MANIPULATION = "citation_manipulation"
    STATE_CORRUPTION = "state_corruption"
    IDENTITY_HIJACKING = "identity_hijacking"


class Citation(BaseModel):
    source_id: str
    patient_id: str | None = None
    quote: str | None = None
    url: str | None = None


class AttackCase(BaseModel):
    case_id: str
    name: str
    category: AttackCategory
    subcategory: str
    surface: str
    target_route: str
    input_sequence: list[str]
    expected_safe_behavior: str
    severity: Severity
    impact_domain: ImpactDomain
    exploitability: str
    regression_candidate: bool = True
    selected_patient_id: str | None = None
    selected_patient_name: str | None = None
    forbidden_patient_identifiers: list[str] = Field(default_factory=list)
    forbidden_patient_facts: list[str] = Field(default_factory=list)
    requires_citations: bool = False
    injection_layer: InjectionLayer = InjectionLayer.NONE
    tags: list[str] = Field(default_factory=list)
    parent_case_id: str | None = None
    mutation_rationale: str | None = None
    approval_status: CaseApprovalStatus = CaseApprovalStatus.APPROVED

    @field_validator("input_sequence")
    @classmethod
    def input_sequence_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("input_sequence must contain at least one prompt")
        return value


class ObservedResponse(BaseModel):
    status_code: int = 200
    text: str
    citations: list[Citation] = Field(default_factory=list)
    tool_outcome: str | None = None
    request_count: int = 1
    latency_ms: int = 0
    token_estimate: int = 0
    provider_cost_usd: float = 0.0
    retry_count: int = 0
    loop_depth: int = 0
    black_box_metadata: dict[str, Any] = Field(default_factory=dict)
    gray_box_metadata: dict[str, Any] = Field(default_factory=dict)


class RunBudget(BaseModel):
    max_requests_per_case: int = 8
    max_latency_ms_per_case: int = 30_000
    max_token_estimate_per_case: int = 8_000
    max_provider_cost_usd_per_case: float = 0.25
    max_retries_per_case: int = 2
    max_loop_depth: int = 3
    max_variants_per_case: int = 3
    max_wall_clock_seconds: int = 300


class JudgeVerdict(BaseModel):
    run_id: str
    case_id: str
    verdict: Verdict
    reason_code: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    impact_domain: ImpactDomain
    requires_human_review: bool = False


class AgentTraceEvent(BaseModel):
    trace_id: str = Field(default_factory=lambda: new_id("trace"))
    run_id: str
    agent_name: str
    event_type: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttackRun(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    case_id: str
    campaign_id: str | None = None
    target_mode: TargetMode
    target_url: str
    target_version: str | None = None
    run_mode: RunMode
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    request_count: int = 0
    estimated_cost_usd: float = 0.0
    raw_observations_ref: str | None = None
    stop_reason: StopReason = StopReason.NOT_STOPPED
    synthetic_principal: str | None = None
    target_metadata: dict[str, Any] = Field(default_factory=dict)


class VulnerabilityReport(BaseModel):
    vulnerability_id: str = Field(default_factory=lambda: new_id("vuln"))
    source_run_id: str
    case_id: str
    severity: Severity
    impact_domain: ImpactDomain
    clinical_or_privacy_impact: str
    minimal_reproduction: list[str]
    observed_behavior: str
    expected_behavior: str
    recommended_remediation: str
    status: ReportStatus = ReportStatus.DRAFT
    fix_validation_runs: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    export_links: list[str] = Field(default_factory=list)


class RegressionCase(BaseModel):
    regression_id: str = Field(default_factory=lambda: new_id("reg"))
    source_report_id: str | None = None
    source_run_id: str
    case_id: str
    status: RegressionStatus = RegressionStatus.CANDIDATE
    created_at: datetime = Field(default_factory=utc_now)
    replay_case: AttackCase
    last_replay_run_id: str | None = None
    last_replay_verdict: Verdict | None = None
    promotion_reason: str = ""


class SuiteSummary(BaseModel):
    summary_id: str = Field(default_factory=lambda: new_id("suite"))
    created_at: datetime = Field(default_factory=utc_now)
    suite: str
    target_mode: TargetMode
    run_mode: RunMode
    run_ids: list[str]
    total_requests: int = 0
    total_latency_ms: int = 0
    total_token_estimate: int = 0
    total_provider_cost_usd: float = 0.0
    pass_count: int = 0
    fail_count: int = 0
    partial_count: int = 0
    inconclusive_count: int = 0


class CampaignPriority(BaseModel):
    campaign_id: str = Field(default_factory=lambda: new_id("campaign"))
    category: AttackCategory
    coverage_gap_score: float = 0.0
    severity_weight: float = 0.0
    recent_failure_score: float = 0.0
    inconclusive_score: float = 0.0
    age_since_last_run_score: float = 0.0
    regression_weight: float = 0.0
    budget_remaining_score: float = 0.0
    total_priority_score: float = 0.0
    selection_reason: str = ""


class ResilienceSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: new_id("snapshot"))
    run_id: str
    created_at: datetime = Field(default_factory=utc_now)
    risk_weighted_score: float
    severity_component: float
    impact_domain_component: float
    coverage_component: float
    inconclusive_component: float
    regression_component: float
    critical_open_count: int
    high_open_count: int
    coverage_by_risk_family: dict[str, float]
    score_explanation: str
