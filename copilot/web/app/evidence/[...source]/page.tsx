"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";

import { evidenceApiHrefFromViewerLocation } from "../../lib/evidence-links";

type EvidenceLoadState = "resolving" | "loading" | "ready" | "error";

type FhirResource = Record<string, unknown>;

type DocumentJob = {
  job_id: string;
  patient_id: string | null;
  doc_type: string;
  status: string;
  source: {
    filename: string;
    content_type: string;
    source_id?: string;
    source_sha256: string;
    byte_count: number;
  };
  created_at?: string;
  updated_at?: string;
  trace?: string[];
};

type DocumentFact = {
  fact_id: string;
  fact_type: string;
  display_label: string;
  normalized_value: string;
  status: string;
  extraction_confidence: number;
  proposed_destination: string;
  blocking_reasons?: string[];
  citation: {
    source_type?: string;
    source_id?: string;
    page_or_section: string;
    field_or_chunk_id: string;
    quote_or_value: string;
    confidence?: number;
    bbox: {
      page: number;
      x0: number;
      y0: number;
      x1: number;
      y1: number;
    } | null;
  };
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  written_resource_id?: string | null;
  write_error?: string | null;
};

type DocumentReviewPayload = {
  job: DocumentJob;
  facts: DocumentFact[];
  trace: string[];
};

type KeyValue = {
  label: string;
  value: string;
};

const REQUEST_TIMEOUT_MS = 20_000;

export default function EvidenceViewerPage() {
  const [apiHref, setApiHref] = useState<string | null>(null);
  const [payload, setPayload] = useState<unknown>(null);
  const [state, setState] = useState<EvidenceLoadState>("resolving");
  const [message, setMessage] = useState("Resolving evidence source.");

  useEffect(() => {
    const nextHref = evidenceApiHrefFromViewerLocation(window.location.pathname, window.location.search);
    if (!nextHref) {
      setState("error");
      setMessage("This evidence link is not recognized.");
      return;
    }
    setApiHref(nextHref);
  }, []);

  useEffect(() => {
    if (!apiHref) return;
    const currentHref = apiHref;

    async function loadEvidence() {
      setState("loading");
      setMessage("Loading source record.");
      try {
        const response = await fetchWithTimeout(currentHref, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Evidence source returned ${response.status}`);
        }
        setPayload(await response.json());
        setState("ready");
        setMessage("Source record loaded.");
      } catch (error) {
        setState("error");
        setMessage(errorMessage(error, "Evidence source unavailable"));
      }
    }

    void loadEvidence();
  }, [apiHref]);

  const view = useMemo(() => classifyPayload(payload), [payload]);

  return (
    <main className="evidenceShell">
      <header className="evidenceTopbar">
        <div className="brandBlock">
          <p className="eyebrow">Evidence source</p>
          <h1>{view.title}</h1>
          <p className="sessionLine">{apiHref ?? "Waiting for source path"}</p>
        </div>
        <div className="dashboardActions">
          <Link className="secondaryLink" href="/">
            Co-Pilot
          </Link>
          <Link className="secondaryLink" href="/dashboard">
            Dashboard
          </Link>
        </div>
      </header>

      <section className="evidenceStatusBar" aria-label="Evidence load status">
        <span className={`sourceBadge ${state === "error" ? "stale" : ""}`}>
          {state === "ready" ? "Readable source" : state}
        </span>
        <span>{message}</span>
      </section>

      {state === "ready" && view.kind === "fhir" ? (
        <FhirEvidenceView apiHref={apiHref ?? ""} resource={view.resource} />
      ) : null}
      {state === "ready" && view.kind === "document" ? (
        <DocumentEvidenceView apiHref={apiHref ?? ""} payload={view.payload} />
      ) : null}
      {state === "ready" && view.kind === "generic" ? (
        <GenericEvidenceView apiHref={apiHref ?? ""} payload={view.payload} />
      ) : null}
      {state !== "ready" ? (
        <section className="dashboardEmpty">
          <h2>{state === "error" ? "Evidence unavailable" : "Loading evidence"}</h2>
          <p>{message}</p>
        </section>
      ) : null}
    </main>
  );
}

function FhirEvidenceView({ apiHref, resource }: { apiHref: string; resource: FhirResource }) {
  const title = fhirTitle(resource);
  const resourceType = asString(resource.resourceType) || "FHIR";
  const primaryFacts = fhirPrimaryFacts(resource, apiHref);
  const details = fhirDetailFacts(resource);

  return (
    <>
      <section className="evidenceHero" aria-label="FHIR source record">
        <div>
          <p className="eyebrow">FHIR source record</p>
          <h2>{title}</h2>
          <p>{fhirSummary(resource)}</p>
        </div>
        <dl>
          <Metric label="Resource" value={resourceType} />
          <Metric label="Identifier" value={asString(resource.id) || "unknown"} />
          <Metric label="Status" value={fhirStatus(resource) || "not recorded"} />
        </dl>
      </section>

      <section className="evidenceContentGrid">
        <article className="evidencePanel">
          <h2>Clinical Summary</h2>
          <dl className="evidenceKeyValues">
            {primaryFacts.map((item) => (
              <KeyValueRow item={item} key={item.label} />
            ))}
          </dl>
        </article>

        <article className="evidencePanel">
          <h2>Source Details</h2>
          <dl className="evidenceKeyValues">
            {details.map((item) => (
              <KeyValueRow item={item} key={item.label} />
            ))}
          </dl>
        </article>
      </section>

      <JsonDisclosure label="FHIR JSON" payload={resource} />
    </>
  );
}

function DocumentEvidenceView({
  apiHref,
  payload
}: {
  apiHref: string;
  payload: DocumentReviewPayload;
}) {
  const [selectedFactId, setSelectedFactId] = useState<string | null>(payload.facts[0]?.fact_id ?? null);
  const selectedFact = useMemo(
    () => payload.facts.find((fact) => fact.fact_id === selectedFactId) ?? payload.facts[0] ?? null,
    [payload.facts, selectedFactId]
  );
  const sourceFileHref = documentSourceApiHref(apiHref);

  useEffect(() => {
    if (!payload.facts.length) {
      setSelectedFactId(null);
      return;
    }
    if (!payload.facts.some((fact) => fact.fact_id === selectedFactId)) {
      setSelectedFactId(payload.facts[0].fact_id);
    }
  }, [payload.facts, selectedFactId]);

  return (
    <>
      <section className="evidenceHero document" aria-label="Document evidence source">
        <div>
          <p className="eyebrow">Document review source</p>
          <h2>{payload.job.source.filename}</h2>
          <p>{payload.job.patient_id ? `Patient ${payload.job.patient_id}` : "Unassigned document evidence"}</p>
        </div>
        <dl>
          <Metric label="Facts" value={String(payload.facts.length)} />
          <Metric label="Status" value={payload.job.status} />
          <Metric label="Type" value={payload.job.doc_type} />
        </dl>
      </section>

      <section className="documentEvidenceGrid">
        <article className="evidencePanel">
          <h2>Source File</h2>
          <dl className="evidenceKeyValues">
            <KeyValueRow item={{ label: "Job", value: payload.job.job_id }} />
            <KeyValueRow item={{ label: "Content type", value: payload.job.source.content_type }} />
            <KeyValueRow item={{ label: "Size", value: `${payload.job.source.byte_count} bytes` }} />
            <KeyValueRow item={{ label: "SHA-256", value: payload.job.source.source_sha256 }} />
            <KeyValueRow item={{ label: "API source", value: apiHref }} />
            {sourceFileHref ? <KeyValueRow item={{ label: "Source file", value: sourceFileHref }} /> : null}
          </dl>
        </article>

        <article className="evidencePanel factInspector">
          <h2>Selected Fact</h2>
          {selectedFact ? (
            <DocumentFactPreview
              contentType={payload.job.source.content_type}
              fact={selectedFact}
              sourceFileHref={sourceFileHref}
            />
          ) : (
            <p>No extracted facts.</p>
          )}
        </article>
      </section>

      {payload.facts.length ? (
        <section className="evidenceFactGrid" aria-label="Document facts">
          {payload.facts.map((fact) => (
            <button
              className={`evidenceFactButton ${fact.fact_id === selectedFact?.fact_id ? "selected" : ""}`}
              key={fact.fact_id}
              onClick={() => setSelectedFactId(fact.fact_id)}
              type="button"
            >
              <span className={`factStatus ${fact.status}`}>{fact.status}</span>
              <strong>{fact.display_label}</strong>
              <p>{fact.normalized_value}</p>
              <small>{`${fact.citation.page_or_section} / ${fact.citation.field_or_chunk_id}`}</small>
            </button>
          ))}
        </section>
      ) : null}

      {payload.trace.length ? (
        <section className="evidenceTrace" aria-label="Evidence trace">
          <h2>Trace</h2>
          <ol>
            {payload.trace.map((step, index) => (
              <li key={`${step}-${index}`}>{step}</li>
            ))}
          </ol>
        </section>
      ) : null}

      <JsonDisclosure label="Document JSON" payload={payload} />
    </>
  );
}

function GenericEvidenceView({ apiHref, payload }: { apiHref: string; payload: unknown }) {
  return (
    <>
      <section className="evidenceHero" aria-label="Evidence source record">
        <div>
          <p className="eyebrow">Source record</p>
          <h2>Evidence Record</h2>
          <p>{apiHref}</p>
        </div>
      </section>
      <JsonDisclosure label="Source JSON" payload={payload} open />
    </>
  );
}

function DocumentFactPreview({
  contentType,
  fact,
  sourceFileHref
}: {
  contentType: string;
  fact: DocumentFact;
  sourceFileHref: string | null;
}) {
  const bbox = fact.citation.bbox;
  const confidence = Math.round(fact.extraction_confidence * 100);
  const isImage = contentType.startsWith("image/");

  return (
    <div className="documentFactPreview">
      <div className="sourcePage" aria-label="Citation page preview">
        {sourceFileHref && isImage ? (
          <Image
            alt=""
            className="sourceDocumentImage"
            fill
            sizes="190px"
            src={sourceFileHref}
            unoptimized
          />
        ) : null}
        {sourceFileHref && !isImage ? (
          <iframe className="sourceDocumentFrame" src={sourceFileHref} title="Source document page" />
        ) : null}
        {bbox ? (
          <span
            className="bbox"
            style={{
              left: `${bbox.x0 * 100}%`,
              top: `${bbox.y0 * 100}%`,
              width: `${(bbox.x1 - bbox.x0) * 100}%`,
              height: `${(bbox.y1 - bbox.y0) * 100}%`
            }}
          />
        ) : null}
      </div>
      <dl className="evidenceKeyValues">
        <KeyValueRow item={{ label: "Fact", value: fact.display_label }} />
        <KeyValueRow item={{ label: "Value", value: fact.normalized_value }} />
        <KeyValueRow item={{ label: "Quote", value: fact.citation.quote_or_value }} />
        <KeyValueRow item={{ label: "Confidence", value: `${confidence}%` }} />
        <KeyValueRow item={{ label: "Destination", value: fact.proposed_destination }} />
        <KeyValueRow item={{ label: "Source", value: fact.citation.source_type ?? "document" }} />
        {fact.reviewed_by ? <KeyValueRow item={{ label: "Reviewed by", value: fact.reviewed_by }} /> : null}
        {fact.written_resource_id ? (
          <KeyValueRow item={{ label: "Observation", value: fact.written_resource_id }} />
        ) : null}
        {fact.write_error ? <KeyValueRow item={{ label: "Write error", value: fact.write_error }} /> : null}
      </dl>
    </div>
  );
}

function JsonDisclosure({
  label,
  payload,
  open = false
}: {
  label: string;
  payload: unknown;
  open?: boolean;
}) {
  return (
    <details className="rawEvidencePanel" open={open}>
      <summary>{label}</summary>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </details>
  );
}

function documentSourceApiHref(reviewApiHref: string): string | null {
  if (!reviewApiHref.endsWith("/review")) return null;
  return reviewApiHref.replace(/\/review$/, "/source-file");
}

function Metric({ label, value }: KeyValue) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function KeyValueRow({ item }: { item: KeyValue }) {
  return (
    <div>
      <dt>{item.label}</dt>
      <dd>{item.value || "not recorded"}</dd>
    </div>
  );
}

function classifyPayload(payload: unknown):
  | { kind: "empty"; title: "Evidence Viewer" }
  | { kind: "document"; title: string; payload: DocumentReviewPayload }
  | { kind: "fhir"; title: string; resource: FhirResource }
  | { kind: "generic"; title: "Evidence Record"; payload: unknown } {
  if (!payload) {
    return { kind: "empty", title: "Evidence Viewer" };
  }
  if (isDocumentReviewPayload(payload)) {
    return { kind: "document", title: payload.job.source.filename, payload };
  }
  if (isRecord(payload) && typeof payload.resourceType === "string") {
    return { kind: "fhir", title: fhirTitle(payload), resource: payload };
  }
  return { kind: "generic", title: "Evidence Record", payload };
}

function isDocumentReviewPayload(payload: unknown): payload is DocumentReviewPayload {
  if (!isRecord(payload)) return false;
  const job = payload.job;
  return isRecord(job) && isRecord(job.source) && Array.isArray(payload.facts);
}

function fhirTitle(resource: FhirResource): string {
  const resourceType = asString(resource.resourceType);
  if (resourceType === "Patient") return patientName(resource) || asString(resource.id) || "Patient";
  if (resourceType === "Observation") return codeableText(resource.code) || "Observation";
  if (resourceType === "MedicationRequest") return medicationName(resource);
  if (resourceType === "Condition") return codeableText(resource.code) || "Condition";
  if (resourceType === "AllergyIntolerance") return codeableText(resource.code) || "Allergy";
  if (resourceType === "DocumentReference") {
    return asString(resource.description) || codeableText(resource.type) || "Clinical Document";
  }
  return resourceType || "FHIR Resource";
}

function fhirSummary(resource: FhirResource): string {
  const resourceType = asString(resource.resourceType);
  if (resourceType === "Observation") {
    return [observationValue(resource), primaryDate(resource)].filter(Boolean).join(" on ") || "Observation source";
  }
  if (resourceType === "MedicationRequest") {
    return dosageText(resource) || requesterText(resource) || "Medication request source";
  }
  if (resourceType === "Condition") {
    return [fhirStatus(resource), primaryDate(resource)].filter(Boolean).join(" since ") || "Problem list source";
  }
  if (resourceType === "AllergyIntolerance") {
    return [criticalityText(resource.criticality), reactionText(resource)].filter(Boolean).join(" - ") || "Allergy source";
  }
  if (resourceType === "Patient") {
    return [asString(resource.birthDate), titleCase(asString(resource.gender))].filter(Boolean).join(" - ") || "Patient source";
  }
  return "OpenEMR FHIR source record";
}

function fhirPrimaryFacts(resource: FhirResource, apiHref: string): KeyValue[] {
  const resourceType = asString(resource.resourceType);
  const facts: KeyValue[] = [
    { label: "Display", value: fhirTitle(resource) },
    { label: "Value", value: observationValue(resource) || dosageText(resource) || reactionText(resource) },
    { label: "Date", value: primaryDate(resource) },
    { label: "Patient", value: patientReference(resource) },
    { label: "API source", value: apiHref }
  ];

  if (resourceType === "Patient") {
    facts.splice(1, 0, { label: "Birth date", value: asString(resource.birthDate) });
    facts.splice(2, 0, { label: "Sex", value: titleCase(asString(resource.gender)) });
  }

  return facts.filter((item) => item.value);
}

function fhirDetailFacts(resource: FhirResource): KeyValue[] {
  const meta = asRecord(resource.meta);
  return [
    { label: "Resource type", value: asString(resource.resourceType) },
    { label: "FHIR ID", value: asString(resource.id) },
    { label: "Status", value: fhirStatus(resource) },
    { label: "Code", value: codeableText(resource.code) || codeableText(resource.type) },
    { label: "Requester", value: requesterText(resource) },
    { label: "Recorded", value: asString(resource.recordedDate) || asString(resource.authoredOn) },
    { label: "Updated", value: asString(meta?.lastUpdated) }
  ].filter((item) => item.value);
}

function fhirStatus(resource: FhirResource): string {
  return (
    nestedCodingText(resource.clinicalStatus) ||
    nestedCodingText(resource.verificationStatus) ||
    asString(resource.status) ||
    nestedCodingText(arrayValue(resource.interpretation)[0]) ||
    (resource.active === false ? "inactive" : resource.active === true ? "active" : "")
  );
}

function primaryDate(resource: FhirResource): string {
  return (
    asString(resource.effectiveDateTime) ||
    asString(resource.issued) ||
    asString(resource.authoredOn) ||
    asString(resource.recordedDate) ||
    asString(resource.onsetDateTime) ||
    asString(resource.date) ||
    asString(resource.birthDate)
  );
}

function patientReference(resource: FhirResource): string {
  if (asString(resource.resourceType) === "Patient") return asString(resource.id);
  return (
    displayReference(resource.subject) ||
    displayReference(resource.patient) ||
    displayReference(asRecord(arrayValue(resource.participant)[0])?.member)
  );
}

function patientName(resource: FhirResource): string {
  const firstName = asRecord(arrayValue(resource.name)[0]);
  if (!firstName) return "";
  const given = arrayValue(firstName.given).map(asString).filter(Boolean).join(" ");
  const family = asString(firstName.family);
  return [given, family].filter(Boolean).join(" ");
}

function medicationName(resource: FhirResource): string {
  return (
    codeableText(resource.medicationCodeableConcept) ||
    displayReference(resource.medicationReference) ||
    "Medication"
  );
}

function dosageText(resource: FhirResource): string {
  const dosage = asRecord(arrayValue(resource.dosageInstruction)[0]);
  return asString(dosage?.text);
}

function requesterText(resource: FhirResource): string {
  return displayReference(resource.requester);
}

function reactionText(resource: FhirResource): string {
  const reaction = asRecord(arrayValue(resource.reaction)[0]);
  return codeableText(reaction?.manifestation) || asString(reaction?.description);
}

function criticalityText(value: unknown): string {
  const criticality = asString(value);
  return criticality ? `Criticality: ${criticality}` : "";
}

function observationValue(resource: FhirResource): string {
  const quantity = asRecord(resource.valueQuantity);
  if (quantity) {
    const value = asString(quantity.value);
    const unit = asString(quantity.unit) || asString(quantity.code);
    return [value, unit].filter(Boolean).join(" ");
  }
  return (
    asString(resource.valueString) ||
    codeableText(resource.valueCodeableConcept) ||
    asString(resource.valueDateTime)
  );
}

function codeableText(value: unknown): string {
  const record = asRecord(value);
  if (!record) {
    const first = asRecord(arrayValue(value)[0]);
    return first ? codeableText(first) : "";
  }
  return asString(record.text) || nestedCodingText(record);
}

function nestedCodingText(value: unknown): string {
  const record = asRecord(value);
  if (!record) return "";
  const firstCoding = asRecord(arrayValue(record.coding)[0]);
  return asString(firstCoding?.display) || asString(firstCoding?.code);
}

function displayReference(value: unknown): string {
  const record = asRecord(value);
  return asString(record?.display) || asString(record?.reference);
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(asRecord(value));
}

function asString(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function titleCase(value: string): string {
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1).toLowerCase()}` : value;
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.name === "AbortError") {
    return `${fallback}: request timed out.`;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
