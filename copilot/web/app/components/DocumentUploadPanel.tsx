"use client";

import { useCallback, useEffect, useState } from "react";

import { ExtractionReviewPanel, type DocumentFact, type DocumentJob } from "./ExtractionReviewPanel";

type DocumentUploadPanelProps = {
  apiBase: string;
  canWriteObservations: boolean;
  disabled: boolean;
  patientId: string | null;
  onStatus: (message: string) => void;
};

type DocumentJobResponse = {
  job: DocumentJob;
  fact_counts: Record<string, number>;
};

type DocumentReviewPayload = {
  job: DocumentJob;
  facts: DocumentFact[];
  trace: string[];
};

type CapabilityResponse = {
  providers?: Record<string, boolean>;
};

type ApprovedEvidence = {
  evidence_id: string;
  source_type: string;
  source_id: string;
  display_name: string;
  fact: string;
  confidence: string;
  source_url: string | null;
  retrieved_at: string;
  metadata?: Record<string, unknown>;
};

type ApprovedEvidencePayload = {
  patient_id: string;
  evidence_count: number;
  evidence: ApprovedEvidence[];
};

export function DocumentUploadPanel({
  apiBase,
  canWriteObservations,
  disabled,
  patientId,
  onStatus
}: DocumentUploadPanelProps) {
  const [docType, setDocType] = useState("lab_pdf");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<DocumentJob | null>(null);
  const [facts, setFacts] = useState<DocumentFact[]>([]);
  const [trace, setTrace] = useState<string[]>([]);
  const [isWorking, setIsWorking] = useState(false);
  const [extractUnassigned, setExtractUnassigned] = useState(false);
  const [persistenceReady, setPersistenceReady] = useState<boolean | null>(null);
  const [capabilityStatus, setCapabilityStatus] = useState("Checking storage readiness.");
  const [observationWriteSupported, setObservationWriteSupported] = useState<boolean | null>(null);
  const [approvedEvidence, setApprovedEvidence] = useState<ApprovedEvidence[]>([]);
  const [approvedEvidenceStatus, setApprovedEvidenceStatus] = useState(
    "No approved document evidence loaded."
  );

  const loadCapabilities = useCallback(async () => {
    try {
      const response = await fetch(`${apiBase}/api/capabilities`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Capabilities returned ${response.status}`);
      }
      const payload = (await response.json()) as CapabilityResponse;
      const providers = payload.providers ?? {};
      const enabled = providers.document_workflow_persistence_enabled ?? false;
      const ready = providers.document_workflow_persistence_ready ?? false;
      const observationCreateSupported = providers.openemr_observation_create_supported ?? false;
      setPersistenceReady(ready);
      setObservationWriteSupported(observationCreateSupported);
      setCapabilityStatus(ready ? "Durable storage ready." : enabled ? "Storage configured, not ready." : "Memory-only document workflow.");
    } catch (error) {
      setPersistenceReady(null);
      setObservationWriteSupported(null);
      setCapabilityStatus(errorMessage(error, "Storage readiness unavailable"));
    }
  }, [apiBase]);

  const loadApprovedEvidence = useCallback(async () => {
    if (!patientId || disabled) {
      setApprovedEvidence([]);
      setApprovedEvidenceStatus("Select an authorized patient to load approved evidence.");
      return;
    }
    try {
      const response = await fetch(
        `${apiBase}/api/documents/patients/${encodeURIComponent(patientId)}/approved-evidence`,
        { cache: "no-store" }
      );
      if (!response.ok) {
        throw new Error(`Approved evidence returned ${response.status}`);
      }
      const payload = (await response.json()) as ApprovedEvidencePayload;
      setApprovedEvidence(payload.evidence);
      setApprovedEvidenceStatus(`${payload.evidence_count} approved evidence objects for ${payload.patient_id}.`);
    } catch (error) {
      setApprovedEvidence([]);
      setApprovedEvidenceStatus(errorMessage(error, "Approved evidence unavailable"));
    }
  }, [apiBase, disabled, patientId]);

  useEffect(() => {
    void loadCapabilities();
  }, [loadCapabilities]);

  useEffect(() => {
    void loadApprovedEvidence();
  }, [loadApprovedEvidence]);

  async function uploadDocument() {
    if (!file) {
      onStatus("Select a document before extraction.");
      return;
    }
    const effectivePatientId = extractUnassigned ? null : patientId;
    setIsWorking(true);
    try {
      const contentBase64 = await fileToBase64(file);
      const response = await fetch(`${apiBase}/api/documents/attach-and-extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          ...(effectivePatientId ? { patient_id: effectivePatientId } : {}),
          doc_type: docType,
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          content_base64: contentBase64
        })
      });
      if (!response.ok) {
        throw new Error(`Document extraction returned ${response.status}`);
      }
      const payload = (await response.json()) as DocumentJobResponse;
      setJob(payload.job);
      onStatus(
        effectivePatientId
          ? `Document extracted: ${formatCounts(payload.fact_counts)}.`
          : `Unassigned document extracted: ${formatCounts(payload.fact_counts)}.`
      );
      await loadReview(payload.job.job_id);
      await loadApprovedEvidence();
    } catch (error) {
      onStatus(errorMessage(error, "Document extraction failed"));
    } finally {
      setIsWorking(false);
    }
  }

  async function loadReview(jobId: string) {
    const response = await fetch(`${apiBase}/api/documents/${encodeURIComponent(jobId)}/review`, {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`Document review returned ${response.status}`);
    }
    const payload = (await response.json()) as DocumentReviewPayload;
    setJob(payload.job);
    setFacts(payload.facts);
    setTrace(payload.trace);
  }

  async function approveAll() {
    if (!job) return;
    if (!job.patient_id) {
      onStatus("Select a patient before approving document facts.");
      return;
    }
    const reviewable = facts.filter((fact) => fact.status === "review_required");
    if (!reviewable.length) {
      onStatus("No extracted facts need approval.");
      return;
    }
    setIsWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/documents/${job.job_id}/review/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          decisions: reviewable.map((fact) => ({ fact_id: fact.fact_id, action: "approve" }))
        })
      });
      if (!response.ok) {
        throw new Error(`Review approval returned ${response.status}`);
      }
      await loadReview(job.job_id);
      await loadApprovedEvidence();
      onStatus(`${reviewable.length} document facts approved for this patient.`);
    } catch (error) {
      onStatus(errorMessage(error, "Review approval failed"));
    } finally {
      setIsWorking(false);
    }
  }

  async function writeApproved() {
    if (!job) return;
    if (!job.patient_id) {
      onStatus("Select a patient before writing document facts.");
      return;
    }
    if (!canWriteObservations) {
      onStatus("Re-authorize OpenEMR with user/Observation.write before writing labs.");
      return;
    }
    if (observationWriteSupported === false) {
      onStatus("This OpenEMR deployment does not expose FHIR Observation.create; approved evidence remains retrievable, but lab writeback is unavailable.");
      return;
    }
    setIsWorking(true);
    try {
      const response = await fetch(`${apiBase}/api/documents/${job.job_id}/write`, {
        method: "POST",
        cache: "no-store"
      });
      if (!response.ok) {
        throw new Error(`Observation write returned ${response.status}`);
      }
      const payload = (await response.json()) as DocumentJobResponse & {
        written_count: number;
        failed_count: number;
        skipped_count: number;
        facts: DocumentFact[];
      };
      setJob(payload.job);
      setFacts(payload.facts);
      await loadApprovedEvidence();
      onStatus(writeStatusMessage(payload));
    } catch (error) {
      onStatus(errorMessage(error, "Observation write failed"));
    } finally {
      setIsWorking(false);
    }
  }

  const hasWritableFacts = facts.some(
    (fact) => fact.status === "approved" || fact.status === "write_failed"
  );
  const hasOnlyRetryableFailures =
    facts.some((fact) => fact.status === "write_failed") &&
    !facts.some((fact) => fact.status === "approved");
  const reviewRequiredCount = facts.filter((fact) => fact.status === "review_required").length;
  const approvedCount = facts.filter((fact) => fact.status === "approved").length;
  const writtenCount = facts.filter((fact) => fact.status === "written").length;
  const failedWriteCount = facts.filter((fact) => fact.status === "write_failed").length;
  const sourceDigest = job?.source.source_sha256.slice(0, 12) ?? "pending";
  const writeDisabledReason = !canWriteObservations
    ? "Re-authorize OpenEMR with user/Observation.write before writing labs."
    : observationWriteSupported === false
      ? "This OpenEMR deployment does not expose FHIR Observation.create."
      : undefined;
  const canAttemptWrite = canWriteObservations && observationWriteSupported !== false;

  return (
    <section className="documentPanel" aria-label="Document evidence workflow">
      <div className="documentControls">
        <div className="documentTitle">
          <strong>Document evidence</strong>
          <span>
            {job
              ? `${job.patient_id ? "assigned" : "unassigned"} - ${job.status} - ${facts.length} facts`
              : "Upload lab PDF, image, or intake form"}
          </span>
          {!canAttemptWrite && hasWritableFacts ? (
            <span>{writeDisabledReason}</span>
          ) : null}
        </div>
        <select
          aria-label="Document type"
          disabled={disabled || isWorking}
          onChange={(event) => setDocType(event.target.value)}
          value={docType}
        >
          <option value="lab_pdf">Lab PDF</option>
          <option value="intake_form">Intake form</option>
        </select>
        <input
          aria-label="Document file"
          disabled={disabled || isWorking}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          type="file"
          accept=".txt,.pdf,.png,.jpg,.jpeg,text/plain,application/pdf,image/png,image/jpeg"
        />
        <label className="documentUnassignedToggle">
          <input
            aria-label="Extract unassigned"
            checked={extractUnassigned}
            disabled={disabled || isWorking}
            onChange={(event) => setExtractUnassigned(event.target.checked)}
            type="checkbox"
          />
          <span>Unassigned</span>
        </label>
        <button disabled={disabled || isWorking || !file} onClick={uploadDocument} type="button">
          {isWorking ? "Working" : "Extract"}
        </button>
        <button disabled={disabled || isWorking || !job?.patient_id || !facts.length} onClick={approveAll} type="button">
          Approve all
        </button>
        <button
          disabled={
            disabled ||
            isWorking ||
            !job?.patient_id ||
            !canAttemptWrite ||
            !hasWritableFacts
          }
          onClick={writeApproved}
          title={writeDisabledReason}
          type="button"
        >
          {hasOnlyRetryableFailures ? "Retry writes" : "Write labs"}
        </button>
      </div>
      <div className="documentProofStrip" aria-label="Document workflow proof">
        <WorkflowBadge
          label="Storage"
          state={persistenceReady === null ? "checking" : persistenceReady ? "ready" : "blocked"}
          value={capabilityStatus}
        />
        <WorkflowBadge
          label="Assignment"
          state={job?.patient_id || (!job && patientId && !extractUnassigned) ? "ready" : "blocked"}
          value={job ? job.patient_id ?? "unassigned" : patientId ?? "no patient"}
        />
        <WorkflowBadge
          label="Source"
          state={job ? "ready" : "checking"}
          value={job ? `${job.source.filename} - sha256:${sourceDigest}` : file?.name ?? "no file"}
        />
        <WorkflowBadge
          label="Extraction"
          state={facts.length ? "ready" : "checking"}
          value={`${facts.length} facts, ${reviewRequiredCount} need review`}
        />
        <WorkflowBadge
          label="Persistence"
          state={approvedEvidence.length ? "ready" : approvedCount || writtenCount ? "checking" : "blocked"}
          value={`${approvedEvidence.length} retrievable evidence objects`}
        />
        <WorkflowBadge
          label="Write"
          state={observationWriteSupported === false || failedWriteCount ? "blocked" : writtenCount ? "ready" : "checking"}
          value={
            observationWriteSupported === false
              ? "Observation.create unavailable"
              : `${writtenCount} written, ${failedWriteCount} failed`
          }
        />
      </div>
      {job ? <ExtractionReviewPanel facts={facts} trace={trace} /> : null}
      <section className="approvedEvidencePanel" aria-label="Approved patient document evidence">
        <header>
          <div>
            <strong>Approved patient evidence</strong>
            <span>{approvedEvidenceStatus}</span>
          </div>
          <button
            disabled={disabled || isWorking || !patientId}
            onClick={() => void loadApprovedEvidence()}
            type="button"
          >
            Refresh evidence
          </button>
        </header>
        {approvedEvidence.length ? (
          <div className="approvedEvidenceList">
            {approvedEvidence.map((item) => (
              <article className="approvedEvidenceCard" key={item.evidence_id}>
                <div>
                  <strong>{item.display_name}</strong>
                  <span>{item.confidence}</span>
                </div>
                <p>{item.fact}</p>
                <dl>
                  <div>
                    <dt>Evidence ID</dt>
                    <dd>{item.evidence_id}</dd>
                  </div>
                  <div>
                    <dt>Source</dt>
                    <dd>{item.source_type}</dd>
                  </div>
                  <div>
                    <dt>Stored</dt>
                    <dd>{formatTimestamp(item.retrieved_at)}</dd>
                  </div>
                </dl>
                {sourceHref(apiBase, item.source_url) ? (
                  <a href={sourceHref(apiBase, item.source_url)} rel="noreferrer" target="_blank">
                    Open citation
                  </a>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="approvedEvidenceEmpty">No approved document evidence for the selected patient.</p>
        )}
      </section>
    </section>
  );
}

function WorkflowBadge({
  label,
  state,
  value
}: {
  label: string;
  state: "ready" | "checking" | "blocked";
  value: string;
}) {
  return (
    <span className={`workflowBadge ${state}`}>
      <strong>{label}</strong>
      <small>{value}</small>
    </span>
  );
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function formatCounts(counts: Record<string, number>) {
  const entries = Object.entries(counts);
  if (!entries.length) return "no facts";
  return entries.map(([status, count]) => `${count} ${status}`).join(", ");
}

function writeStatusMessage(payload: {
  written_count: number;
  skipped_count: number;
  failed_count: number;
  facts: DocumentFact[];
}) {
  const base = `Document write finished: ${payload.written_count} written, ${payload.skipped_count} skipped, ${payload.failed_count} failed.`;
  const failures = payload.facts.filter((fact) => fact.status === "write_failed" && fact.write_error);
  if (!failures.length) return base;
  const first = failures[0];
  return `${base} First failure: ${first.display_label} - ${first.write_error}`;
}

function sourceHref(apiBase: string, sourceUrl: string | null) {
  if (!sourceUrl?.startsWith("/api/")) return undefined;
  return `${apiBase}${sourceUrl}`;
}

function formatTimestamp(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
