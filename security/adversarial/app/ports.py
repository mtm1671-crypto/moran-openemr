"""Small protocol contracts for workflow dependencies."""

from __future__ import annotations

from typing import Protocol

from .models import (
    AttackCase,
    AuthorizedScope,
    JudgeVerdict,
    ObservedResponse,
    RunBudget,
    SiteScanFinding,
    SiteScanMode,
    SiteScanRun,
    VulnerabilityReport,
)


class TargetCaseExecutor(Protocol):
    async def execute_case(self, case: AttackCase, budget: RunBudget) -> ObservedResponse:
        """Execute one adversarial case against a target."""
        ...


class JudgeEvaluator(Protocol):
    def evaluate(
        self,
        *,
        run_id: str,
        case: AttackCase,
        observed: ObservedResponse,
        budget: RunBudget,
    ) -> JudgeVerdict:
        """Evaluate one observed target response."""
        ...


class ReportDrafter(Protocol):
    def draft_report(self, case: AttackCase, verdict: JudgeVerdict) -> VulnerabilityReport | None:
        """Draft a vulnerability report for a non-passing verdict."""
        ...


class SiteScanner(Protocol):
    def scan(
        self,
        target_url: str,
        authorization_note: str = "Operator attests this target is owned or explicitly authorized.",
        mode: SiteScanMode = SiteScanMode.PASSIVE_HTTP,
        scope: AuthorizedScope | None = None,
    ) -> tuple[SiteScanRun, list[SiteScanFinding]]:
        """Run a bounded scan against an authorized target."""
        ...
