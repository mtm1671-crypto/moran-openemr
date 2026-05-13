"""Documentation Agent for vulnerability report drafts."""

from __future__ import annotations

from .models import AttackCase, JudgeVerdict, ReportStatus, Verdict, VulnerabilityReport


class DocumentationAgent:
    def draft_report(self, case: AttackCase, verdict: JudgeVerdict) -> VulnerabilityReport | None:
        if verdict.verdict == Verdict.PASS:
            return None
        status = ReportStatus.NEEDS_HUMAN_REVIEW if verdict.requires_human_review else ReportStatus.DRAFT
        return VulnerabilityReport(
            source_run_id=verdict.run_id,
            case_id=case.case_id,
            severity=verdict.severity,
            impact_domain=verdict.impact_domain,
            clinical_or_privacy_impact=self._impact(case, verdict),
            minimal_reproduction=case.input_sequence,
            observed_behavior=verdict.reason,
            expected_behavior=case.expected_safe_behavior,
            recommended_remediation=self._remediation(case, verdict),
            status=status,
            evidence=verdict.evidence,
            export_links=[
                f"/runs/{verdict.run_id}.json",
                f"/runs/{verdict.run_id}.md",
            ],
        )

    def _impact(self, case: AttackCase, verdict: JudgeVerdict) -> str:
        return (
            f"{case.name} produced a {verdict.verdict} verdict for "
            f"{verdict.severity} / {verdict.impact_domain}: {verdict.reason}"
        )

    def _remediation(self, case: AttackCase, verdict: JudgeVerdict) -> str:
        return (
            "Reproduce the case, inspect the black-box evidence, and strengthen the "
            f"{case.category} defense that maps to reason code {verdict.reason_code}."
        )
