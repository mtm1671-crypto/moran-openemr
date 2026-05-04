from __future__ import annotations

from dataclasses import dataclass

from app.document_models import ExtractedFact, W2FactStatus, W2ProposedDestination


@dataclass(frozen=True)
class W2RuleResult:
    code: str
    passed: bool
    message: str


@dataclass(frozen=True)
class W2VerificationResult:
    ok: bool
    results: list[W2RuleResult]


def verify_document_facts(facts: list[ExtractedFact]) -> W2VerificationResult:
    results = [
        _schema_valid(facts),
        _citations_present(facts),
        _bounding_boxes_present_for_reviewed_facts(facts),
        _low_confidence_writes_blocked(facts),
        _unapproved_writes_blocked(facts),
    ]
    return W2VerificationResult(
        ok=all(result.passed for result in results),
        results=results,
    )


def _schema_valid(facts: list[ExtractedFact]) -> W2RuleResult:
    invalid = [fact.fact_id for fact in facts if fact.blocking_reasons and fact.status != W2FactStatus.rejected]
    return W2RuleResult(
        code="schema_valid",
        passed=not invalid,
        message="All non-rejected facts satisfy schema gates." if not invalid else f"Invalid facts: {invalid}",
    )


def _citations_present(facts: list[ExtractedFact]) -> W2RuleResult:
    missing = [fact.fact_id for fact in facts if not fact.citation_present]
    return W2RuleResult(
        code="citation_present",
        passed=not missing,
        message="All facts include citations." if not missing else f"Missing citations: {missing}",
    )


def _bounding_boxes_present_for_reviewed_facts(facts: list[ExtractedFact]) -> W2RuleResult:
    missing = [
        fact.fact_id
        for fact in facts
        if fact.status in {W2FactStatus.approved, W2FactStatus.written} and not fact.bbox_present
    ]
    return W2RuleResult(
        code="bbox_valid",
        passed=not missing,
        message="Reviewed facts include bounding boxes." if not missing else f"Missing bboxes: {missing}",
    )


def _low_confidence_writes_blocked(facts: list[ExtractedFact]) -> W2RuleResult:
    violations = [
        fact.fact_id
        for fact in facts
        if fact.status == W2FactStatus.written and "extraction_confidence_below_review_threshold" in fact.blocking_reasons
    ]
    return W2RuleResult(
        code="low_confidence_write_blocked",
        passed=not violations,
        message="No low-confidence facts were written." if not violations else f"Written low-confidence facts: {violations}",
    )


def _unapproved_writes_blocked(facts: list[ExtractedFact]) -> W2RuleResult:
    violations = [
        fact.fact_id
        for fact in facts
        if fact.status == W2FactStatus.written
        and fact.proposed_destination != W2ProposedDestination.openemr_observation
    ]
    return W2RuleResult(
        code="no_unapproved_chart_write",
        passed=not violations,
        message="Only approved Observation destinations were written."
        if not violations
        else f"Unexpected written facts: {violations}",
    )

