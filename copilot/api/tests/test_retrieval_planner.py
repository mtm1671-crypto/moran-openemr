from app.retrieval_planner import plan_retrieval


def test_chief_concern_plan_is_document_only_and_tiny() -> None:
    plan = plan_retrieval("Tell me Chen's chief concern and nothing else")

    assert plan.intent == "chief_concern_lookup"
    assert plan.evidence_limit == 1
    assert plan.fhir_tools == ()
    assert plan.use_demo_evidence is False
    assert plan.use_approved_documents is True
    assert plan.approved_document_source_types == ("intake_chief_concern",)
    assert plan.use_guidelines is False
    assert plan.use_vector_search is False


def test_broad_brief_plan_keeps_broader_budget() -> None:
    plan = plan_retrieval("What should I know before seeing this patient?")

    assert plan.intent == "broad_brief"
    assert plan.evidence_limit == 12
    assert plan.fhir_tools == (
        "get_patient_demographics",
        "get_active_problems",
        "get_recent_labs",
        "get_recent_notes",
    )
    assert plan.use_demo_evidence is True
    assert plan.use_vector_search is True


def test_guideline_plan_enables_guidelines() -> None:
    plan = plan_retrieval(
        "Using patient record and diabetes guideline evidence, what changed?"
    )

    assert plan.intent == "guideline_context"
    assert plan.use_guidelines is True
    assert plan.use_vector_search is True
    assert "get_recent_labs" in plan.fhir_tools


def test_lipid_review_plan_enables_guideline_grounding() -> None:
    plan = plan_retrieval("What LDL or triglyceride values should I review?")

    assert plan.intent == "guideline_context"
    assert plan.use_guidelines is True
    assert "get_recent_labs" in plan.fhir_tools


def test_intake_medication_family_history_plan_keeps_both_document_types() -> None:
    plan = plan_retrieval("What intake medication and family history facts are available?")

    assert plan.intent == "document_medication_history_lookup"
    assert plan.use_demo_evidence is False
    assert "intake_medication" in plan.approved_document_source_types
    assert "intake_history" in plan.approved_document_source_types


def test_recreational_drug_question_routes_to_document_context() -> None:
    plan = plan_retrieval("Has this patient ever taken recreational drugs?")

    assert plan.intent == "document_context_lookup"
    assert plan.fhir_tools == ("get_recent_notes",)
    assert plan.use_demo_evidence is False
    assert plan.approved_document_source_types == (
        "intake_history",
        "intake_chief_concern",
    )
