"""Encrypted Co-Pilot persistence and derived read-model storage.

OpenEMR is still the clinical system of record. The tables here store Co-Pilot
product/audit data and rebuildable projections: evidence cache, vector index,
semantic relationships, job status, and encrypted conversation history.
"""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    delete,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.config import Settings
from app.document_models import DocumentJobRecord, ExtractedFact, W2FactStatus, W2DocType
from app.document_storage import StoredDocumentSource, document_fact_to_evidence, document_source_id
from app.models import EvidenceObject
from app.security import PhiCipher, assert_metadata_payload_is_phi_safe

metadata = MetaData()

# PHI-safe audit metadata for Co-Pilot operations. Future production compliance
# audit can move to a stricter insert-only/WORM surface without changing callers.
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("actor_user_id", String(255), nullable=False),
    Column("patient_ref", String(64), nullable=True),
    Column("action", String(80), nullable=False),
    Column("resource_type", String(80), nullable=True),
    Column("resource_ref", String(64), nullable=True),
    Column("outcome", String(40), nullable=False),
    Column("reason_code", String(80), nullable=True),
    Column("metadata_json", JSON, nullable=False),
)

# Short-lived encrypted evidence bundles. These speed repeated questions but are
# not final-answer cache and are not a substitute for OpenEMR source truth.
evidence_cache = Table(
    "evidence_cache",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("patient_ref", String(64), nullable=False),
    Column("cache_key_ref", String(64), nullable=False),
    Column("source_system", String(80), nullable=False),
    Column("payload_version", String(20), nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_payload", LargeBinary, nullable=False),
)

# Patient-scoped vector projection for unstructured or semi-structured evidence.
# The encrypted payload lets search return source-backed evidence without putting
# raw chart text in logs or process metadata.
evidence_vector_index = Table(
    "evidence_vector_index",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("patient_ref", String(64), nullable=False),
    Column("evidence_ref", String(64), nullable=False),
    Column("source_system", String(80), nullable=False),
    Column("source_type", String(80), nullable=False),
    Column("source_ref", String(64), nullable=False),
    Column("embedding_provider", String(40), nullable=False),
    Column("embedding_model", String(120), nullable=False),
    Column("embedding_dimension", Integer, nullable=False),
    Column("embedding_json", JSON, nullable=False),
    Column("content_ref", String(64), nullable=False),
    Column("payload_version", String(20), nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_evidence", LargeBinary, nullable=False),
    Column("metadata_json", JSON, nullable=False),
    UniqueConstraint(
        "patient_ref",
        "evidence_ref",
        "embedding_model",
        name="uq_evidence_vector_patient_evidence_model",
    ),
)

# Product memory. Conversations are encrypted and expire by retention policy.
conversations = Table(
    "conversations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("actor_user_id", String(255), nullable=False),
    Column("patient_ref", String(64), nullable=False),
    Column("status", String(40), nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_title", LargeBinary, nullable=False),
    Column("metadata_json", JSON, nullable=False),
)

conversation_messages = Table(
    "conversation_messages",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("conversation_id", String(36), ForeignKey("conversations.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("role", String(40), nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_payload", LargeBinary, nullable=False),
    Column("metadata_json", JSON, nullable=False),
)

# Background/document workflow state. Jobs make long-running work observable and
# retryable instead of hiding OCR/reindex/write work inside a browser request.
job_runs = Table(
    "job_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("job_type", String(80), nullable=False),
    Column("status", String(40), nullable=False),
    Column("actor_user_id", String(255), nullable=False),
    Column("patient_ref", String(64), nullable=True),
    Column("metadata_json", JSON, nullable=False),
    Column("error_code", String(80), nullable=True),
)

document_sources = Table(
    "document_sources",
    metadata,
    Column("source_id", String(180), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("patient_ref", String(64), nullable=True),
    Column("source_sha256", String(64), nullable=False),
    Column("content_type", String(120), nullable=False),
    Column("byte_count", Integer, nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_source", LargeBinary, nullable=False),
)

document_jobs = Table(
    "document_jobs",
    metadata,
    Column("job_id", String(80), primary_key=True),
    Column("source_id", String(180), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("patient_ref", String(64), nullable=True),
    Column("status", String(40), nullable=False),
    Column("doc_type", String(40), nullable=False),
    Column("actor_user_id", String(255), nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_job", LargeBinary, nullable=False),
)

document_facts = Table(
    "document_facts",
    metadata,
    Column("fact_id", String(80), primary_key=True),
    Column("job_id", String(80), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("patient_ref", String(64), nullable=True),
    Column("status", String(40), nullable=False),
    Column("fact_type", String(80), nullable=False),
    Column("destination", String(80), nullable=False),
    Column("encryption_key_id", String(80), nullable=False),
    Column("encrypted_fact", LargeBinary, nullable=False),
)

semantic_relationships = Table(
    "semantic_relationships",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("patient_ref", String(64), nullable=False),
    Column("subject_ref", String(64), nullable=False),
    Column("predicate", String(80), nullable=False),
    Column("object_ref", String(64), nullable=False),
    Column("source_evidence_ref", String(64), nullable=False),
    Column("confidence", String(40), nullable=False),
    Column("metadata_json", JSON, nullable=False),
    UniqueConstraint(
        "patient_ref",
        "subject_ref",
        "predicate",
        "object_ref",
        "source_evidence_ref",
        name="uq_semantic_relationship_patient_fact",
    ),
)


@dataclass(frozen=True)
class EvidenceCacheRecord:
    patient_ref: str
    cache_key_ref: str
    payload: dict[str, Any]
    expires_at: datetime


@dataclass(frozen=True)
class EvidenceVectorSearchHit:
    evidence: EvidenceObject
    score: float


@dataclass(frozen=True)
class JobRunRecord:
    job_id: str
    job_type: str
    status: str
    actor_user_id: str
    patient_id_hash: str | None
    metadata: dict[str, Any]
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def build_phi_cipher(settings: Settings) -> PhiCipher:
    if settings.encryption_key is None:
        raise RuntimeError("ENCRYPTION_KEY is required")
    return PhiCipher(settings.encryption_key, settings.encryption_key_id)


def build_audit_event(
    *,
    settings: Settings,
    actor_user_id: str,
    action: str,
    outcome: str,
    patient_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    reason_code: str | None = None,
    metadata_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_metadata = metadata_payload or {}
    assert_metadata_payload_is_phi_safe(safe_metadata)
    cipher = build_phi_cipher(settings)
    return {
        "id": str(uuid4()),
        "occurred_at": datetime.now(tz=UTC),
        "actor_user_id": actor_user_id,
        "patient_ref": cipher.fingerprint(patient_id) if patient_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_ref": cipher.fingerprint(resource_id) if resource_id else None,
        "outcome": outcome,
        "reason_code": reason_code,
        "metadata_json": safe_metadata,
    }


def build_evidence_cache_record(
    *,
    settings: Settings,
    patient_id: str,
    cache_key: str,
    payload: dict[str, Any],
    ttl_seconds: int,
    source_system: str = "openemr",
    payload_version: str = "1",
) -> dict[str, Any]:
    cipher = build_phi_cipher(settings)
    now = datetime.now(tz=UTC)
    return {
        "id": str(uuid4()),
        "created_at": now,
        "expires_at": now + timedelta(seconds=ttl_seconds),
        "patient_ref": cipher.fingerprint(patient_id),
        "cache_key_ref": cipher.fingerprint(cache_key),
        "source_system": source_system,
        "payload_version": payload_version,
        "encryption_key_id": cipher.key_id,
        "encrypted_payload": cipher.encrypt_json(payload),
    }


def build_evidence_vector_record(
    *,
    settings: Settings,
    evidence: EvidenceObject,
    embedding: list[float],
    embedding_provider: str,
    embedding_model: str,
    ttl_days: int,
    payload_version: str = "1",
) -> dict[str, Any]:
    cipher = build_phi_cipher(settings)
    now = datetime.now(tz=UTC)
    safe_metadata = {
        "source_system": evidence.source_system,
        "source_type": evidence.source_type,
        "embedding_provider": embedding_provider,
    }
    assert_metadata_payload_is_phi_safe(safe_metadata)
    return {
        "id": str(uuid4()),
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(days=ttl_days),
        "patient_ref": cipher.fingerprint(evidence.patient_id),
        "evidence_ref": cipher.fingerprint(evidence.evidence_id),
        "source_system": evidence.source_system,
        "source_type": evidence.source_type,
        "source_ref": cipher.fingerprint(f"{evidence.source_type}:{evidence.source_id}"),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimension": len(embedding),
        "embedding_json": embedding,
        "content_ref": cipher.fingerprint(f"{evidence.evidence_id}:{evidence.fact}"),
        "payload_version": payload_version,
        "encryption_key_id": cipher.key_id,
        "encrypted_evidence": cipher.encrypt_json(evidence.model_dump(mode="json")),
        "metadata_json": safe_metadata,
    }


def build_conversation_record(
    *,
    settings: Settings,
    actor_user_id: str,
    patient_id: str,
    title: str,
    ttl_days: int,
) -> dict[str, Any]:
    cipher = build_phi_cipher(settings)
    now = datetime.now(tz=UTC)
    safe_metadata = {"schema": "conversation_v1"}
    assert_metadata_payload_is_phi_safe(safe_metadata)
    return {
        "id": str(uuid4()),
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(days=ttl_days),
        "actor_user_id": actor_user_id,
        "patient_ref": cipher.fingerprint(patient_id),
        "status": "active",
        "encryption_key_id": cipher.key_id,
        "encrypted_title": cipher.encrypt_json({"title": title[:160]}),
        "metadata_json": safe_metadata,
    }


def build_conversation_message_record(
    *,
    settings: Settings,
    conversation_id: str,
    role: str,
    payload: dict[str, Any],
    metadata_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_metadata = metadata_payload or {}
    assert_metadata_payload_is_phi_safe(safe_metadata)
    cipher = build_phi_cipher(settings)
    return {
        "id": str(uuid4()),
        "conversation_id": conversation_id,
        "created_at": datetime.now(tz=UTC),
        "role": role,
        "encryption_key_id": cipher.key_id,
        "encrypted_payload": cipher.encrypt_json(payload),
        "metadata_json": safe_metadata,
    }


def build_job_run_record(
    *,
    settings: Settings,
    job_type: str,
    status: str,
    actor_user_id: str,
    patient_id: str | None = None,
    metadata_payload: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    safe_metadata = metadata_payload or {}
    assert_metadata_payload_is_phi_safe(safe_metadata)
    cipher = build_phi_cipher(settings)
    now = datetime.now(tz=UTC)
    return {
        "id": str(uuid4()),
        "created_at": now,
        "updated_at": now,
        "started_at": now if status == "running" else None,
        "finished_at": now if status in {"succeeded", "failed", "skipped"} else None,
        "job_type": job_type,
        "status": status,
        "actor_user_id": actor_user_id,
        "patient_ref": cipher.fingerprint(patient_id) if patient_id else None,
        "metadata_json": safe_metadata,
        "error_code": error_code,
    }


def build_document_source_record(
    *,
    settings: Settings,
    source: StoredDocumentSource,
) -> dict[str, Any]:
    cipher = build_phi_cipher(settings)
    payload = {
        "source_id": source.source_id,
        "patient_id": source.patient_id,
        "doc_type": source.doc_type.value,
        "filename": source.filename,
        "content_type": source.content_type,
        "source_sha256": source.source_sha256,
        "content_base64": base64.b64encode(source.content).decode("ascii"),
        "created_at": source.created_at.isoformat(),
    }
    return {
        "source_id": source.source_id,
        "created_at": source.created_at,
        "patient_ref": cipher.fingerprint(source.patient_id) if source.patient_id else None,
        "source_sha256": source.source_sha256,
        "content_type": source.content_type,
        "byte_count": len(source.content),
        "encryption_key_id": cipher.key_id,
        "encrypted_source": cipher.encrypt_json(payload),
    }


def build_document_job_record(
    *,
    settings: Settings,
    job: DocumentJobRecord,
) -> dict[str, Any]:
    cipher = build_phi_cipher(settings)
    return {
        "job_id": job.job_id,
        "source_id": job.source.source_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "patient_ref": cipher.fingerprint(job.patient_id) if job.patient_id else None,
        "status": job.status.value,
        "doc_type": job.doc_type.value,
        "actor_user_id": job.actor_user_id,
        "encryption_key_id": cipher.key_id,
        "encrypted_job": cipher.encrypt_json(job.model_dump(mode="json")),
    }


def build_document_fact_record(
    *,
    settings: Settings,
    fact: ExtractedFact,
) -> dict[str, Any]:
    cipher = build_phi_cipher(settings)
    return {
        "fact_id": fact.fact_id,
        "job_id": fact.document_job_id,
        "updated_at": datetime.now(tz=UTC),
        "patient_ref": cipher.fingerprint(fact.patient_id) if fact.patient_id else None,
        "status": fact.status.value,
        "fact_type": fact.fact_type.value,
        "destination": fact.proposed_destination.value,
        "encryption_key_id": cipher.key_id,
        "encrypted_fact": cipher.encrypt_json(fact.model_dump(mode="json")),
    }


def build_semantic_relationship_records(
    *,
    settings: Settings,
    evidence: list[EvidenceObject],
    ttl_days: int,
) -> list[dict[str, Any]]:
    cipher = build_phi_cipher(settings)
    now = datetime.now(tz=UTC)
    records: list[dict[str, Any]] = []
    for item in evidence:
        metadata_payload = {
            "source_system": item.source_system,
            "source_type": item.source_type,
            "relationship_schema": "evidence_relationship_v1",
        }
        assert_metadata_payload_is_phi_safe(metadata_payload)
        records.append(
            {
                "id": str(uuid4()),
                "created_at": now,
                "updated_at": now,
                "expires_at": now + timedelta(days=ttl_days),
                "patient_ref": cipher.fingerprint(item.patient_id),
                "subject_ref": cipher.fingerprint(f"Patient:{item.patient_id}"),
                "predicate": _relationship_predicate(item.source_type),
                "object_ref": cipher.fingerprint(f"{item.source_type}:{item.source_id}"),
                "source_evidence_ref": cipher.fingerprint(item.evidence_id),
                "confidence": item.confidence,
                "metadata_json": metadata_payload,
            }
        )
    return records


async def initialize_phi_schema(settings: Settings) -> None:
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            if settings.vector_index_backend == "pgvector":
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(metadata.create_all)
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_evidence_vector_patient_model_expires "
                    "ON evidence_vector_index (patient_ref, embedding_model, expires_at)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_conversations_actor_patient_expires "
                    "ON conversations (actor_user_id, patient_ref, expires_at)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_conversation_messages_conversation_created "
                    "ON conversation_messages (conversation_id, created_at)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_job_runs_type_status_created "
                    "ON job_runs (job_type, status, created_at)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_jobs_patient_status_updated "
                    "ON document_jobs (patient_ref, status, updated_at)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_facts_job_status "
                    "ON document_facts (job_id, status)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_facts_patient_status "
                    "ON document_facts (patient_ref, status)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_semantic_relationship_patient_predicate "
                    "ON semantic_relationships (patient_ref, predicate, expires_at)"
                )
            )
            if settings.vector_index_backend == "pgvector":
                await _initialize_pgvector_schema(settings, connection)
    finally:
        await engine.dispose()


async def database_ready(settings: Settings) -> bool:
    if settings.database_url is None:
        return False
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def vector_store_ready(settings: Settings) -> bool:
    if not settings.vector_search_enabled:
        return True
    if settings.database_url is None:
        return False
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            if settings.vector_index_backend == "pgvector":
                extension_exists = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                )
                table_name = "evidence_pgvector_index"
            else:
                extension_exists = True
                table_name = "evidence_vector_index"
            table_exists = await connection.scalar(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :table_name"
                    ")"
                ),
                {"table_name": table_name},
            )
        exists = bool(extension_exists) and bool(table_exists)
        return bool(exists)
    except Exception:
        return False
    finally:
        await engine.dispose()


async def evidence_cache_ready(settings: Settings) -> bool:
    if not settings.evidence_cache_enabled:
        return True
    if settings.database_url is None:
        return False
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'evidence_cache'"
                    ")"
                )
            )
        return bool(exists)
    except Exception:
        return False
    finally:
        await engine.dispose()


async def document_workflow_storage_ready(settings: Settings) -> bool:
    if not settings.document_workflow_persistence_enabled:
        return True
    if settings.database_url is None or settings.encryption_key is None:
        return False

    engine = _create_engine(settings)
    table_names = ["document_sources", "document_jobs", "document_facts"]
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = ANY(:table_names)"
                    ),
                    {"table_names": table_names},
                )
            ).scalars()
        return set(rows) == set(table_names)
    except Exception:
        return False
    finally:
        await engine.dispose()


async def operational_storage_ready(settings: Settings) -> bool:
    if not settings.requires_phi_controls() and not settings.conversation_persistence_enabled:
        return True
    if settings.database_url is None:
        return False
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            table_names = [
                "audit_events",
                "conversations",
                "conversation_messages",
                "job_runs",
                "document_sources",
                "document_jobs",
                "document_facts",
                "semantic_relationships",
            ]
            rows = (
                await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = ANY(:table_names)"
                    ),
                    {"table_names": table_names},
                )
            ).scalars()
        return set(rows) == set(table_names)
    except Exception:
        return False
    finally:
        await engine.dispose()


async def write_audit_event(settings: Settings, event: dict[str, Any]) -> None:
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(insert(audit_events).values(event))
    finally:
        await engine.dispose()


async def append_chat_messages(
    *,
    settings: Settings,
    actor_user_id: str,
    patient_id: str,
    user_message: str,
    assistant_payload: dict[str, Any],
    conversation_id: str | None = None,
) -> str:
    cipher = build_phi_cipher(settings)
    patient_ref = cipher.fingerprint(patient_id)
    now = datetime.now(tz=UTC)
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            selected_conversation_id = conversation_id
            if selected_conversation_id is not None:
                existing = await connection.scalar(
                    select(conversations.c.id)
                    .where(conversations.c.id == selected_conversation_id)
                    .where(conversations.c.actor_user_id == actor_user_id)
                    .where(conversations.c.patient_ref == patient_ref)
                    .where(conversations.c.expires_at > now)
                )
                if existing is None:
                    selected_conversation_id = None

            if selected_conversation_id is None:
                record = build_conversation_record(
                    settings=settings,
                    actor_user_id=actor_user_id,
                    patient_id=patient_id,
                    title=user_message,
                    ttl_days=settings.conversation_retention_days,
                )
                selected_conversation_id = str(record["id"])
                await connection.execute(insert(conversations).values(record))
            else:
                await connection.execute(
                    update(conversations)
                    .where(conversations.c.id == selected_conversation_id)
                    .values(updated_at=now)
                )

            user_record = build_conversation_message_record(
                settings=settings,
                conversation_id=selected_conversation_id,
                role="user",
                payload={"message": user_message},
                metadata_payload={"schema": "chat_message_v1"},
            )
            assistant_record = build_conversation_message_record(
                settings=settings,
                conversation_id=selected_conversation_id,
                role="assistant",
                payload=assistant_payload,
                metadata_payload={"schema": "chat_message_v1"},
            )
            await connection.execute(insert(conversation_messages).values(user_record))
            await connection.execute(insert(conversation_messages).values(assistant_record))
            return selected_conversation_id
    finally:
        await engine.dispose()


async def create_job_run(settings: Settings, record: dict[str, Any]) -> str:
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(insert(job_runs).values(record))
        return str(record["id"])
    finally:
        await engine.dispose()


async def update_job_run(
    *,
    settings: Settings,
    job_id: str,
    status: str,
    metadata_payload: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    safe_metadata = metadata_payload or {}
    assert_metadata_payload_is_phi_safe(safe_metadata)
    now = datetime.now(tz=UTC)
    values: dict[str, Any] = {
        "updated_at": now,
        "status": status,
        "metadata_json": safe_metadata,
        "error_code": error_code,
    }
    if status in {"succeeded", "failed", "skipped"}:
        values["finished_at"] = now
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(update(job_runs).where(job_runs.c.id == job_id).values(**values))
    finally:
        await engine.dispose()


async def read_job_run(settings: Settings, job_id: str) -> JobRunRecord | None:
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(select(job_runs).where(job_runs.c.id == job_id).limit(1))
            ).mappings().first()
    finally:
        await engine.dispose()
    if row is None:
        return None
    return _job_run_from_row(dict(row))


def document_workflow_persistence_configured(settings: Settings) -> bool:
    return (
        settings.document_workflow_persistence_enabled
        and settings.database_url is not None
        and settings.encryption_key is not None
    )


async def upsert_document_workflow_snapshot(
    *,
    settings: Settings,
    job: DocumentJobRecord,
    source: StoredDocumentSource,
    facts: list[ExtractedFact],
) -> None:
    if not document_workflow_persistence_configured(settings):
        return

    source_record = build_document_source_record(settings=settings, source=source)
    job_record = build_document_job_record(settings=settings, job=job)
    fact_records = [build_document_fact_record(settings=settings, fact=fact) for fact in facts]

    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            source_insert = pg_insert(document_sources).values(source_record)
            await connection.execute(
                source_insert.on_conflict_do_update(
                    index_elements=["source_id"],
                    set_={
                        "created_at": source_insert.excluded.created_at,
                        "patient_ref": source_insert.excluded.patient_ref,
                        "source_sha256": source_insert.excluded.source_sha256,
                        "content_type": source_insert.excluded.content_type,
                        "byte_count": source_insert.excluded.byte_count,
                        "encryption_key_id": source_insert.excluded.encryption_key_id,
                        "encrypted_source": source_insert.excluded.encrypted_source,
                    },
                )
            )

            job_insert = pg_insert(document_jobs).values(job_record)
            await connection.execute(
                job_insert.on_conflict_do_update(
                    index_elements=["job_id"],
                    set_={
                        "source_id": job_insert.excluded.source_id,
                        "created_at": job_insert.excluded.created_at,
                        "updated_at": job_insert.excluded.updated_at,
                        "patient_ref": job_insert.excluded.patient_ref,
                        "status": job_insert.excluded.status,
                        "doc_type": job_insert.excluded.doc_type,
                        "actor_user_id": job_insert.excluded.actor_user_id,
                        "encryption_key_id": job_insert.excluded.encryption_key_id,
                        "encrypted_job": job_insert.excluded.encrypted_job,
                    },
                )
            )

            if fact_records:
                current_fact_ids = [str(record["fact_id"]) for record in fact_records]
                await connection.execute(
                    delete(document_facts)
                    .where(document_facts.c.job_id == job.job_id)
                    .where(~document_facts.c.fact_id.in_(current_fact_ids))
                )
            else:
                await connection.execute(
                    delete(document_facts).where(document_facts.c.job_id == job.job_id)
                )

            for record in fact_records:
                fact_insert = pg_insert(document_facts).values(record)
                await connection.execute(
                    fact_insert.on_conflict_do_update(
                        index_elements=["fact_id"],
                        set_={
                            "job_id": fact_insert.excluded.job_id,
                            "updated_at": fact_insert.excluded.updated_at,
                            "patient_ref": fact_insert.excluded.patient_ref,
                            "status": fact_insert.excluded.status,
                            "fact_type": fact_insert.excluded.fact_type,
                            "destination": fact_insert.excluded.destination,
                            "encryption_key_id": fact_insert.excluded.encryption_key_id,
                            "encrypted_fact": fact_insert.excluded.encrypted_fact,
                        },
                    )
                )
    finally:
        await engine.dispose()


async def read_document_workflow_snapshot(
    settings: Settings,
    job_id: str,
) -> tuple[DocumentJobRecord, StoredDocumentSource, list[ExtractedFact]] | None:
    if not document_workflow_persistence_configured(settings):
        return None
    cipher = build_phi_cipher(settings)
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            job_row = (
                await connection.execute(
                    select(document_jobs.c.encrypted_job).where(document_jobs.c.job_id == job_id).limit(1)
                )
            ).mappings().first()
            if job_row is None:
                return None
            encrypted_job = _row_bytes(job_row["encrypted_job"])
            job = DocumentJobRecord.model_validate(cipher.decrypt_json(encrypted_job))

            source_row = (
                await connection.execute(
                    select(document_sources.c.encrypted_source)
                    .where(document_sources.c.source_id == job.source.source_id)
                    .limit(1)
                )
            ).mappings().first()
            if source_row is None:
                return None
            source_payload = cipher.decrypt_json(_row_bytes(source_row["encrypted_source"]))

            fact_rows = list(
                (
                    await connection.execute(
                        select(document_facts.c.encrypted_fact)
                        .where(document_facts.c.job_id == job_id)
                        .order_by(document_facts.c.fact_id)
                    )
                ).mappings()
            )
    finally:
        await engine.dispose()

    source = _stored_document_source_from_payload(source_payload)
    facts = [
        ExtractedFact.model_validate(cipher.decrypt_json(_row_bytes(row["encrypted_fact"])))
        for row in fact_rows
    ]
    return job, source, facts


async def read_document_workflow_snapshot_by_source_key(
    *,
    settings: Settings,
    patient_id: str | None,
    doc_type: W2DocType,
    source_hash: str,
    content_type: str,
) -> tuple[DocumentJobRecord, StoredDocumentSource, list[ExtractedFact]] | None:
    if not document_workflow_persistence_configured(settings):
        return None

    source_id = document_source_id(
        patient_id=patient_id,
        doc_type=doc_type,
        source_hash=source_hash,
        content_type=content_type,
    )
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            job_id = await connection.scalar(
                select(document_jobs.c.job_id)
                .where(document_jobs.c.source_id == source_id)
                .where(document_jobs.c.doc_type == doc_type.value)
                .order_by(document_jobs.c.updated_at.desc())
                .limit(1)
            )
    finally:
        await engine.dispose()

    if not isinstance(job_id, str):
        return None
    return await read_document_workflow_snapshot(settings, job_id)


async def read_approved_document_evidence(
    settings: Settings,
    patient_id: str,
) -> list[EvidenceObject]:
    if not document_workflow_persistence_configured(settings):
        return []

    cipher = build_phi_cipher(settings)
    patient_ref = cipher.fingerprint(patient_id)
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            rows = list(
                (
                    await connection.execute(
                        select(
                            document_jobs.c.encrypted_job,
                            document_facts.c.encrypted_fact,
                        )
                        .select_from(
                            document_facts.join(
                                document_jobs,
                                document_facts.c.job_id == document_jobs.c.job_id,
                            )
                        )
                        .where(document_facts.c.patient_ref == patient_ref)
                        .where(
                            document_facts.c.status.in_(
                                [W2FactStatus.approved.value, W2FactStatus.written.value]
                            )
                        )
                        .order_by(document_facts.c.updated_at)
                    )
                ).mappings()
            )
    finally:
        await engine.dispose()

    evidence: list[EvidenceObject] = []
    for row in rows:
        job = DocumentJobRecord.model_validate(cipher.decrypt_json(_row_bytes(row["encrypted_job"])))
        fact = ExtractedFact.model_validate(cipher.decrypt_json(_row_bytes(row["encrypted_fact"])))
        evidence.append(document_fact_to_evidence(job, fact))
    return evidence


async def write_evidence_cache_record(settings: Settings, record: dict[str, Any]) -> None:
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(insert(evidence_cache).values(record))
    finally:
        await engine.dispose()


async def upsert_evidence_vector_records(
    settings: Settings,
    records: list[dict[str, Any]],
) -> None:
    if not records:
        return
    if settings.vector_index_backend == "pgvector":
        await upsert_pgvector_evidence_records(settings, records)
        return
    engine = _create_engine(settings)
    try:
        insert_statement = pg_insert(evidence_vector_index).values(records)
        update_columns = {
            "updated_at": insert_statement.excluded.updated_at,
            "expires_at": insert_statement.excluded.expires_at,
            "source_system": insert_statement.excluded.source_system,
            "source_type": insert_statement.excluded.source_type,
            "source_ref": insert_statement.excluded.source_ref,
            "embedding_provider": insert_statement.excluded.embedding_provider,
            "embedding_dimension": insert_statement.excluded.embedding_dimension,
            "embedding_json": insert_statement.excluded.embedding_json,
            "content_ref": insert_statement.excluded.content_ref,
            "payload_version": insert_statement.excluded.payload_version,
            "encryption_key_id": insert_statement.excluded.encryption_key_id,
            "encrypted_evidence": insert_statement.excluded.encrypted_evidence,
            "metadata_json": insert_statement.excluded.metadata_json,
        }
        statement = insert_statement.on_conflict_do_update(
            index_elements=["patient_ref", "evidence_ref", "embedding_model"],
            set_=update_columns,
        )
        async with engine.begin() as connection:
            await connection.execute(statement)
    finally:
        await engine.dispose()


async def upsert_semantic_relationship_records(
    settings: Settings,
    records: list[dict[str, Any]],
) -> None:
    if not records:
        return
    engine = _create_engine(settings)
    try:
        insert_statement = pg_insert(semantic_relationships).values(records)
        statement = insert_statement.on_conflict_do_update(
            index_elements=[
                "patient_ref",
                "subject_ref",
                "predicate",
                "object_ref",
                "source_evidence_ref",
            ],
            set_={
                "updated_at": insert_statement.excluded.updated_at,
                "expires_at": insert_statement.excluded.expires_at,
                "confidence": insert_statement.excluded.confidence,
                "metadata_json": insert_statement.excluded.metadata_json,
            },
        )
        async with engine.begin() as connection:
            await connection.execute(statement)
    finally:
        await engine.dispose()


async def upsert_pgvector_evidence_records(
    settings: Settings,
    records: list[dict[str, Any]],
) -> None:
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            await _initialize_pgvector_schema(settings, connection)
            for record in records:
                values = dict(record)
                values["embedding_vector"] = _vector_literal(_coerce_embedding(record["embedding_json"]) or [])
                values["metadata_json"] = json.dumps(record["metadata_json"], sort_keys=True)
                await connection.execute(
                    text(
                        "INSERT INTO evidence_pgvector_index ("
                        "id, created_at, updated_at, expires_at, patient_ref, evidence_ref, "
                        "source_system, source_type, source_ref, embedding_provider, embedding_model, "
                        "embedding_dimension, embedding, content_ref, payload_version, encryption_key_id, "
                        "encrypted_evidence, metadata_json"
                        ") VALUES ("
                        ":id, :created_at, :updated_at, :expires_at, :patient_ref, :evidence_ref, "
                        ":source_system, :source_type, :source_ref, :embedding_provider, :embedding_model, "
                        ":embedding_dimension, CAST(:embedding_vector AS vector), :content_ref, "
                        ":payload_version, :encryption_key_id, :encrypted_evidence, CAST(:metadata_json AS jsonb)"
                        ") ON CONFLICT (patient_ref, evidence_ref, embedding_model) DO UPDATE SET "
                        "updated_at = EXCLUDED.updated_at, "
                        "expires_at = EXCLUDED.expires_at, "
                        "source_system = EXCLUDED.source_system, "
                        "source_type = EXCLUDED.source_type, "
                        "source_ref = EXCLUDED.source_ref, "
                        "embedding_provider = EXCLUDED.embedding_provider, "
                        "embedding_dimension = EXCLUDED.embedding_dimension, "
                        "embedding = EXCLUDED.embedding, "
                        "content_ref = EXCLUDED.content_ref, "
                        "payload_version = EXCLUDED.payload_version, "
                        "encryption_key_id = EXCLUDED.encryption_key_id, "
                        "encrypted_evidence = EXCLUDED.encrypted_evidence, "
                        "metadata_json = EXCLUDED.metadata_json"
                    ),
                    values,
                )
    finally:
        await engine.dispose()


async def search_evidence_vectors(
    *,
    settings: Settings,
    patient_id: str,
    query_embedding: list[float],
    embedding_model: str,
    limit: int,
    min_score: float,
    candidate_limit: int,
) -> list[EvidenceVectorSearchHit]:
    if settings.vector_index_backend == "pgvector":
        return await search_pgvector_evidence_vectors(
            settings=settings,
            patient_id=patient_id,
            query_embedding=query_embedding,
            embedding_model=embedding_model,
            limit=limit,
            min_score=min_score,
            candidate_limit=candidate_limit,
        )
    cipher = build_phi_cipher(settings)
    patient_ref = cipher.fingerprint(patient_id)
    engine = _create_engine(settings)
    try:
        query = (
            select(
                evidence_vector_index.c.embedding_json,
                evidence_vector_index.c.encrypted_evidence,
            )
            .where(evidence_vector_index.c.patient_ref == patient_ref)
            .where(evidence_vector_index.c.embedding_model == embedding_model)
            .where(evidence_vector_index.c.expires_at > datetime.now(tz=UTC))
            .limit(candidate_limit)
        )
        async with engine.connect() as connection:
            rows = list((await connection.execute(query)).mappings())
    finally:
        await engine.dispose()

    hits: list[EvidenceVectorSearchHit] = []
    for row in rows:
        embedding = _coerce_embedding(row["embedding_json"])
        if embedding is None:
            continue
        score = _cosine_similarity(query_embedding, embedding)
        if score < min_score:
            continue
        encrypted_evidence = row["encrypted_evidence"]
        if not isinstance(encrypted_evidence, bytes):
            encrypted_evidence = bytes(encrypted_evidence)
        evidence = EvidenceObject.model_validate(cipher.decrypt_json(encrypted_evidence))
        hits.append(EvidenceVectorSearchHit(evidence=evidence, score=score))

    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]


async def search_pgvector_evidence_vectors(
    *,
    settings: Settings,
    patient_id: str,
    query_embedding: list[float],
    embedding_model: str,
    limit: int,
    min_score: float,
    candidate_limit: int,
) -> list[EvidenceVectorSearchHit]:
    cipher = build_phi_cipher(settings)
    patient_ref = cipher.fingerprint(patient_id)
    engine = _create_engine(settings)
    try:
        async with engine.connect() as connection:
            rows = list(
                (
                    await connection.execute(
                        text(
                            "SELECT encrypted_evidence, "
                            "1 - (embedding <=> CAST(:query_embedding AS vector)) AS score "
                            "FROM evidence_pgvector_index "
                            "WHERE patient_ref = :patient_ref "
                            "AND embedding_model = :embedding_model "
                            "AND expires_at > NOW() "
                            "ORDER BY embedding <=> CAST(:query_embedding AS vector) "
                            "LIMIT :candidate_limit"
                        ),
                        {
                            "query_embedding": _vector_literal(query_embedding),
                            "patient_ref": patient_ref,
                            "embedding_model": embedding_model,
                            "candidate_limit": candidate_limit,
                        },
                    )
                ).mappings()
            )
    finally:
        await engine.dispose()

    hits: list[EvidenceVectorSearchHit] = []
    for row in rows:
        score = float(row["score"])
        if score < min_score:
            continue
        encrypted_evidence = row["encrypted_evidence"]
        if not isinstance(encrypted_evidence, bytes):
            encrypted_evidence = bytes(encrypted_evidence)
        evidence = EvidenceObject.model_validate(cipher.decrypt_json(encrypted_evidence))
        hits.append(EvidenceVectorSearchHit(evidence=evidence, score=score))
    return hits[:limit]


async def read_evidence_cache_record(
    *,
    settings: Settings,
    patient_id: str,
    cache_key: str,
) -> EvidenceCacheRecord | None:
    cipher = build_phi_cipher(settings)
    patient_ref = cipher.fingerprint(patient_id)
    cache_key_ref = cipher.fingerprint(cache_key)
    engine = _create_engine(settings)
    try:
        query = (
            select(
                evidence_cache.c.patient_ref,
                evidence_cache.c.cache_key_ref,
                evidence_cache.c.encrypted_payload,
                evidence_cache.c.expires_at,
            )
            .where(evidence_cache.c.patient_ref == patient_ref)
            .where(evidence_cache.c.cache_key_ref == cache_key_ref)
            .where(evidence_cache.c.expires_at > datetime.now(tz=UTC))
            .limit(1)
        )
        async with engine.connect() as connection:
            row = (await connection.execute(query)).mappings().first()
    finally:
        await engine.dispose()

    if row is None:
        return None
    encrypted_payload = row["encrypted_payload"]
    if not isinstance(encrypted_payload, bytes):
        encrypted_payload = bytes(encrypted_payload)
    expires_at = row["expires_at"]
    if not isinstance(expires_at, datetime):
        raise RuntimeError("Evidence cache row had invalid expires_at")
    return EvidenceCacheRecord(
        patient_ref=str(row["patient_ref"]),
        cache_key_ref=str(row["cache_key_ref"]),
        payload=cipher.decrypt_json(encrypted_payload),
        expires_at=expires_at,
    )


async def purge_expired_phi_records(settings: Settings) -> dict[str, int]:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required")
    now = datetime.now(tz=UTC)
    audit_cutoff = now - timedelta(days=settings.conversation_retention_days)
    engine = _create_engine(settings)
    try:
        async with engine.begin() as connection:
            cache_result = await connection.execute(
                delete(evidence_cache).where(evidence_cache.c.expires_at <= now)
            )
            vector_result = await connection.execute(
                delete(evidence_vector_index).where(evidence_vector_index.c.expires_at <= now)
            )
            audit_result = await connection.execute(
                delete(audit_events).where(audit_events.c.occurred_at < audit_cutoff)
            )
            conversation_message_result = await connection.execute(
                delete(conversation_messages).where(
                    conversation_messages.c.conversation_id.in_(
                        select(conversations.c.id).where(conversations.c.expires_at <= now)
                    )
                )
            )
            conversation_result = await connection.execute(
                delete(conversations).where(conversations.c.expires_at <= now)
            )
            job_cutoff = now - timedelta(days=settings.job_status_retention_days)
            job_result = await connection.execute(
                delete(job_runs).where(job_runs.c.updated_at < job_cutoff)
            )
            relationship_result = await connection.execute(
                delete(semantic_relationships).where(semantic_relationships.c.expires_at <= now)
            )
            if settings.vector_index_backend == "pgvector":
                pgvector_result = await connection.execute(
                    text("DELETE FROM evidence_pgvector_index WHERE expires_at <= NOW()")
                )
            else:
                pgvector_result = None
    finally:
        await engine.dispose()

    return {
        "evidence_cache_deleted": int(cache_result.rowcount or 0),
        "evidence_vectors_deleted": int(vector_result.rowcount or 0),
        "audit_events_deleted": int(audit_result.rowcount or 0),
        "conversation_messages_deleted": int(conversation_message_result.rowcount or 0),
        "conversations_deleted": int(conversation_result.rowcount or 0),
        "job_runs_deleted": int(job_result.rowcount or 0),
        "semantic_relationships_deleted": int(relationship_result.rowcount or 0),
        "pgvector_evidence_deleted": int(pgvector_result.rowcount or 0) if pgvector_result else 0,
    }


def _create_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required")
    return create_async_engine(_async_database_url(settings.database_url.get_secret_value()))


def _async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


async def _initialize_pgvector_schema(settings: Settings, connection: AsyncConnection) -> None:
    dimensions = settings.vector_embedding_dimensions
    await connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS evidence_pgvector_index ("
            "id varchar(36) PRIMARY KEY, "
            "created_at timestamptz NOT NULL, "
            "updated_at timestamptz NOT NULL, "
            "expires_at timestamptz NOT NULL, "
            "patient_ref varchar(64) NOT NULL, "
            "evidence_ref varchar(64) NOT NULL, "
            "source_system varchar(80) NOT NULL, "
            "source_type varchar(80) NOT NULL, "
            "source_ref varchar(64) NOT NULL, "
            "embedding_provider varchar(40) NOT NULL, "
            "embedding_model varchar(120) NOT NULL, "
            "embedding_dimension integer NOT NULL, "
            f"embedding vector({dimensions}) NOT NULL, "
            "content_ref varchar(64) NOT NULL, "
            "payload_version varchar(20) NOT NULL, "
            "encryption_key_id varchar(80) NOT NULL, "
            "encrypted_evidence bytea NOT NULL, "
            "metadata_json jsonb NOT NULL, "
            "CONSTRAINT uq_evidence_pgvector_patient_evidence_model "
            "UNIQUE (patient_ref, evidence_ref, embedding_model)"
            ")"
        )
    )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_evidence_pgvector_patient_model_expires "
            "ON evidence_pgvector_index (patient_ref, embedding_model, expires_at)"
        )
    )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_evidence_pgvector_embedding "
            "ON evidence_pgvector_index USING ivfflat (embedding vector_cosine_ops)"
        )
    )


def _coerce_embedding(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    embedding: list[float] = []
    for item in value:
        if not isinstance(item, (float, int)):
            return None
        embedding.append(float(item))
    return embedding


def _stored_document_source_from_payload(payload: dict[str, Any]) -> StoredDocumentSource:
    created_at = payload.get("created_at")
    if not isinstance(created_at, str):
        raise RuntimeError("Document source row had invalid created_at")
    content_base64 = payload.get("content_base64")
    if not isinstance(content_base64, str):
        raise RuntimeError("Document source row had invalid content")
    patient_id = payload.get("patient_id")
    if patient_id is not None and not isinstance(patient_id, str):
        raise RuntimeError("Document source row had invalid patient_id")
    return StoredDocumentSource(
        source_id=str(payload["source_id"]),
        patient_id=patient_id,
        doc_type=W2DocType(str(payload["doc_type"])),
        filename=str(payload["filename"]),
        content_type=str(payload["content_type"]),
        source_sha256=str(payload["source_sha256"]),
        content=base64.b64decode(content_base64.encode("ascii")),
        created_at=datetime.fromisoformat(created_at),
    )


def _row_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    return bytes(value)


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return float(dot / (left_norm * right_norm))


def _relationship_predicate(source_type: str) -> str:
    mapping = {
        "patient_demographics": "has_demographic_fact",
        "active_problem": "has_active_problem",
        "lab_result": "has_lab_result",
        "medication": "has_medication",
        "allergy": "has_allergy",
        "clinical_note": "has_clinical_note",
    }
    return mapping.get(source_type, "has_chart_evidence")


def _job_run_from_row(row: dict[str, Any]) -> JobRunRecord:
    return JobRunRecord(
        job_id=str(row["id"]),
        job_type=str(row["job_type"]),
        status=str(row["status"]),
        actor_user_id=str(row["actor_user_id"]),
        patient_id_hash=str(row["patient_ref"]) if row.get("patient_ref") else None,
        metadata=dict(row["metadata_json"] or {}),
        error_code=str(row["error_code"]) if row.get("error_code") else None,
        created_at=_row_datetime(row["created_at"]),
        updated_at=_row_datetime(row["updated_at"]),
        started_at=_row_optional_datetime(row.get("started_at")),
        finished_at=_row_optional_datetime(row.get("finished_at")),
    )


def _row_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("Database row had invalid datetime")
    return value


def _row_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _row_datetime(value)
