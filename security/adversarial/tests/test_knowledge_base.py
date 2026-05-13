from app.knowledge_base import load_site_vulnerability_knowledge_base, vulnerability_class_ids


def test_site_vulnerability_knowledge_base_covers_core_scanner_risks() -> None:
    payload = load_site_vulnerability_knowledge_base()
    class_ids = vulnerability_class_ids()

    assert payload["version"] >= 1
    assert len(payload["source_families"]) >= 8
    assert "scanner_safety_rules" in payload
    assert "authz.object_function" in class_ids
    assert "dependency.known_exploited" in class_ids
    assert "llm.ai_app_risks" in class_ids
    assert "cloud.cicd.secrets" in class_ids


def test_knowledge_base_entries_have_evidence_and_safety_fields() -> None:
    payload = load_site_vulnerability_knowledge_base()

    for entry in payload["vulnerability_classes"]:
        assert entry["source_refs"]
        assert entry["detection_signals"]
        assert entry["evidence_requirements"]
        assert entry["next_capabilities"]
        assert entry["safety_limits"]
