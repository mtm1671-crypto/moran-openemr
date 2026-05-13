from pathlib import Path

from app.models import (
    ImpactDomain,
    JudgeVerdict,
    Severity,
    Verdict,
)
from app.run_store import RunStore
from app.run_week3_eval import blocking_verdicts


def test_blocking_verdicts_returns_only_critical_or_high_failures(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite")
    store.initialize()
    store.save_verdict(
        JudgeVerdict(
            run_id="run_block",
            case_id="case_critical",
            verdict=Verdict.FAIL,
            reason_code="PATIENT_SCOPE_LEAK",
            reason="Wrong-patient fact disclosed.",
            confidence=1.0,
            severity=Severity.CRITICAL,
            impact_domain=ImpactDomain.PHI,
        )
    )
    store.save_verdict(
        JudgeVerdict(
            run_id="run_non_block",
            case_id="case_medium",
            verdict=Verdict.FAIL,
            reason_code="MISSING_CITATION",
            reason="Citation missing.",
            confidence=0.8,
            severity=Severity.MEDIUM,
            impact_domain=ImpactDomain.CLINICAL_WORKFLOW,
        )
    )

    blockers = blocking_verdicts(store, ["run_block", "run_non_block"])

    assert [verdict["case_id"] for verdict in blockers] == ["case_critical"]
