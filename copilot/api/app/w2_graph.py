from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.document_models import ExtractedFact, W2FactStatus, W2ProposedDestination
from app.w2_verifier import W2VerificationResult, verify_document_facts


class W2Route(StrEnum):
    intake_extractor = "intake_extractor"
    human_review = "human_review"
    observation_writer = "observation_writer"
    evidence_retriever = "evidence_retriever"
    verifier = "verifier"
    done = "done"


@dataclass(frozen=True)
class W2RoutingDecision:
    route: W2Route
    reason: str


@dataclass(frozen=True)
class W2WorkerHandoff:
    supervisor: str
    worker: W2Route
    reason: str
    input_contract: str
    output_contract: str


@dataclass
class W2GraphState:
    document_job_id: str
    patient_id: str
    extracted_facts: list[ExtractedFact] = field(default_factory=list)
    review_submitted: bool = False
    guideline_retrieved: bool = False
    verification_result: W2VerificationResult | None = None


def supervisor_route(state: W2GraphState) -> W2RoutingDecision:
    if not state.extracted_facts:
        return W2RoutingDecision(W2Route.intake_extractor, "document_not_extracted")
    if _has_reviewable_facts(state) and not state.review_submitted:
        return W2RoutingDecision(W2Route.human_review, "facts_require_review")
    if _has_approved_labs_not_written(state):
        return W2RoutingDecision(W2Route.observation_writer, "approved_lab_facts_pending_write")
    if not state.guideline_retrieved:
        return W2RoutingDecision(W2Route.evidence_retriever, "guideline_evidence_needed")
    if state.verification_result is None:
        return W2RoutingDecision(W2Route.verifier, "ready_for_verification")
    return W2RoutingDecision(W2Route.done, "graph_complete")


def worker_handoff(decision: W2RoutingDecision) -> W2WorkerHandoff:
    contracts = {
        W2Route.intake_extractor: (
            "DocumentSourceSummary + W2DocType + source bytes",
            "ExtractedFact[] with schema, citation, bbox, confidence",
        ),
        W2Route.human_review: (
            "ExtractedFact[] in review_required status",
            "approved/rejected ExtractedFact[] with reviewer metadata",
        ),
        W2Route.observation_writer: (
            "approved lab_result ExtractedFact[]",
            "FHIR Observation ids or per-fact write errors",
        ),
        W2Route.evidence_retriever: (
            "patient_id + approved document facts + clinician question",
            "ranked patient-record and guideline EvidenceObject[]",
        ),
        W2Route.verifier: (
            "draft facts/answer + cited evidence ids",
            "blocking/pass verification result",
        ),
        W2Route.done: ("terminal graph state", "no-op"),
    }
    input_contract, output_contract = contracts[decision.route]
    return W2WorkerHandoff(
        supervisor="w2_supervisor",
        worker=decision.route,
        reason=decision.reason,
        input_contract=input_contract,
        output_contract=output_contract,
    )


def handoff_trace_events(decision: W2RoutingDecision) -> list[str]:
    handoff = worker_handoff(decision)
    if handoff.worker == W2Route.done:
        return ["supervisor:done:graph_complete"]
    return [
        f"handoff:{handoff.supervisor}->{handoff.worker.value}:{handoff.reason}",
        f"worker_contract:{handoff.worker.value}:{handoff.input_contract}->{handoff.output_contract}",
    ]


def verify_state(state: W2GraphState) -> W2GraphState:
    state.verification_result = verify_document_facts(state.extracted_facts)
    return state


def _has_reviewable_facts(state: W2GraphState) -> bool:
    return any(fact.status == W2FactStatus.review_required for fact in state.extracted_facts)


def _has_approved_labs_not_written(state: W2GraphState) -> bool:
    return any(
        fact.status == W2FactStatus.approved
        and fact.proposed_destination == W2ProposedDestination.openemr_observation
        for fact in state.extracted_facts
    )
