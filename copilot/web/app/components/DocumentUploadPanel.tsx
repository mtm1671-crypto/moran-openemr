"use client";

import { useState } from "react";

import { ExtractionReviewPanel, type DocumentFact, type DocumentJob } from "./ExtractionReviewPanel";

type DocumentUploadPanelProps = {
  apiBase: string;
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

export function DocumentUploadPanel({
  apiBase,
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
      onStatus(
        `Document write finished: ${payload.written_count} written, ${payload.skipped_count} skipped, ${payload.failed_count} failed.`
      );
    } catch (error) {
      onStatus(errorMessage(error, "Observation write failed"));
    } finally {
      setIsWorking(false);
    }
  }

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
        <button disabled={disabled || isWorking || !job?.patient_id || !facts.some((fact) => fact.status === "approved")} onClick={writeApproved} type="button">
          Write labs
        </button>
      </div>
      {job ? <ExtractionReviewPanel facts={facts} trace={trace} /> : null}
    </section>
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

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
