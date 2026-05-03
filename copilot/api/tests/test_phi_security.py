import json
from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.models import EvidenceObject
from app.persistence import (
    build_audit_event,
    build_conversation_message_record,
    build_conversation_record,
    build_evidence_cache_record,
    build_evidence_vector_record,
    build_job_run_record,
    build_semantic_relationship_records,
)
from app.security import PhiCipher, assert_metadata_payload_is_phi_safe

TEST_FERNET_KEY = "PAAhZkguTNgLSk3R268DyJ-Lu6c_M4_87k7s2Prrt_8="


def test_phi_cipher_encrypts_json_and_fingerprints_identifiers() -> None:
    settings = Settings(encryption_key=TEST_FERNET_KEY)
    assert settings.encryption_key is not None
    cipher = PhiCipher(settings.encryption_key, settings.encryption_key_id)

    ciphertext = cipher.encrypt_json({"patient_name": "Elena Morrison", "a1c": 8.6})

    assert b"Elena" not in ciphertext
    assert cipher.decrypt_json(ciphertext) == {"patient_name": "Elena Morrison", "a1c": 8.6}
    assert cipher.fingerprint("patient-1") == cipher.fingerprint("patient-1")
    assert cipher.fingerprint("patient-1") != "patient-1"


def test_phi_safe_audit_metadata_rejects_obvious_phi() -> None:
    assert_metadata_payload_is_phi_safe({"tool": "recent_labs", "result": "success"})

    with pytest.raises(ValueError, match="raw PHI"):
        assert_metadata_payload_is_phi_safe({"note": "DOB 1975-04-12"})


def test_audit_event_hashes_patient_and_resource_references() -> None:
    settings = Settings(encryption_key=TEST_FERNET_KEY)

    event = build_audit_event(
        settings=settings,
        actor_user_id="doctor-1",
        action="source_read",
        outcome="success",
        patient_id="patient-123",
        resource_type="Observation",
        resource_id="observation-456",
        metadata_payload={"tool": "source"},
    )
    serialized = json.dumps(event, default=str)

    assert "patient-123" not in serialized
    assert "observation-456" not in serialized
    assert event["patient_ref"]
    assert event["resource_ref"]


def test_evidence_cache_record_encrypts_payload_and_hashes_cache_key() -> None:
    settings = Settings(encryption_key=TEST_FERNET_KEY, encryption_key_id="test-key")

    record = build_evidence_cache_record(
        settings=settings,
        patient_id="patient-123",
        cache_key="recent-labs",
        payload={"fact": "A1c was 8.6%"},
        ttl_seconds=300,
    )

    assert record["encryption_key_id"] == "test-key"
    assert record["patient_ref"] != "patient-123"
    assert record["cache_key_ref"] != "recent-labs"
    assert b"A1c" not in record["encrypted_payload"]


def test_evidence_vector_record_encrypts_evidence_and_hashes_identifiers() -> None:
    settings = Settings(encryption_key=TEST_FERNET_KEY, encryption_key_id="test-key")
    evidence = EvidenceObject(
        evidence_id="ev-note-1",
        patient_id="patient-123",
        source_type="clinical_note",
        source_id="note-456",
        display_name="Progress Note",
        fact="Patient Elena Morrison reports trouble affording medication.",
        retrieved_at=datetime.now(tz=UTC),
        source_url="/api/source/openemr/DocumentReference/note-456?patient_id=patient-123",
    )

    record = build_evidence_vector_record(
        settings=settings,
        evidence=evidence,
        embedding=[0.1, 0.2, 0.3],
        embedding_provider="hash",
        embedding_model="local-hash-v1-3",
        ttl_days=30,
    )
    serialized = json.dumps(record, default=str)

    assert "patient-123" not in serialized
    assert "note-456" not in serialized
    assert "Elena" not in serialized
    assert record["patient_ref"] != "patient-123"
    assert record["source_ref"] != "note-456"
    assert record["embedding_json"] == [0.1, 0.2, 0.3]
    assert b"Elena" not in record["encrypted_evidence"]


def test_conversation_records_encrypt_prompt_answer_payloads() -> None:
    settings = Settings(encryption_key=TEST_FERNET_KEY, encryption_key_id="test-key")

    conversation = build_conversation_record(
        settings=settings,
        actor_user_id="doctor-1",
        patient_id="patient-123",
        title="Question about Elena Morrison",
        ttl_days=30,
    )
    message = build_conversation_message_record(
        settings=settings,
        conversation_id=str(conversation["id"]),
        role="assistant",
        payload={"answer": "Elena Morrison has an elevated A1c."},
        metadata_payload={"schema": "chat_message_v1"},
    )
    serialized = json.dumps({**conversation, **message}, default=str)

    assert "patient-123" not in serialized
    assert "Elena" not in serialized
    assert b"Elena" not in conversation["encrypted_title"]
    assert b"Elena" not in message["encrypted_payload"]


def test_job_and_semantic_relationship_records_hash_phi_references() -> None:
    settings = Settings(encryption_key=TEST_FERNET_KEY, encryption_key_id="test-key")
    evidence = EvidenceObject(
        evidence_id="ev-note-1",
        patient_id="patient-123",
        source_type="clinical_note",
        source_id="note-456",
        display_name="Progress Note",
        fact="Patient reports improved sleep.",
        retrieved_at=datetime.now(tz=UTC),
    )

    job = build_job_run_record(
        settings=settings,
        job_type="patient_reindex",
        status="running",
        actor_user_id="doctor-1",
        patient_id="patient-123",
        metadata_payload={"trigger": "api_or_worker"},
    )
    relationships = build_semantic_relationship_records(
        settings=settings,
        evidence=[evidence],
        ttl_days=30,
    )
    serialized = json.dumps({"job": job, "relationships": relationships}, default=str)

    assert "patient-123" not in serialized
    assert "note-456" not in serialized
    assert job["patient_ref"] != "patient-123"
    assert relationships[0]["predicate"] == "has_clinical_note"
