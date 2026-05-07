"use client";

import { useEffect, useMemo, useState } from "react";

import { GraphTracePanel } from "./GraphTracePanel";
import { PdfBoundingBoxPreview } from "./PdfBoundingBoxPreview";

export type DocumentJob = {
  job_id: string;
  patient_id: string | null;
  doc_type: string;
  status: string;
  source: {
    filename: string;
    content_type: string;
    source_sha256: string;
    byte_count: number;
  };
};

export type DocumentFact = {
  fact_id: string;
  fact_type: string;
  display_label: string;
  normalized_value: string;
  status: string;
  extraction_confidence: number;
  proposed_destination: string;
  blocking_reasons: string[];
  citation: {
    source_type?: string;
    source_id?: string;
    page_or_section: string;
    field_or_chunk_id: string;
    quote_or_value: string;
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
  schema_valid?: boolean;
  citation_present?: boolean;
  bbox_present?: boolean;
  needs_human_review?: boolean;
  written_resource_id: string | null;
  write_error: string | null;
};

type ExtractionReviewPanelProps = {
  facts: DocumentFact[];
  trace: string[];
};

export function ExtractionReviewPanel({ facts, trace }: ExtractionReviewPanelProps) {
  const [selectedFactId, setSelectedFactId] = useState<string | null>(facts[0]?.fact_id ?? null);
  const selectedFact = useMemo(
    () => facts.find((fact) => fact.fact_id === selectedFactId) ?? facts[0] ?? null,
    [facts, selectedFactId]
  );

  useEffect(() => {
    if (!facts.length) {
      setSelectedFactId(null);
      return;
    }
    if (!facts.some((fact) => fact.fact_id === selectedFactId)) {
      setSelectedFactId(facts[0].fact_id);
    }
  }, [facts, selectedFactId]);

  return (
    <div className="reviewGrid">
      <PdfBoundingBoxPreview fact={selectedFact} />
      <div className="factList" aria-label="Extracted facts">
        {facts.map((fact) => (
          <button
            className={`factCard ${selectedFact?.fact_id === fact.fact_id ? "selected" : ""}`}
            key={fact.fact_id}
            onClick={() => setSelectedFactId(fact.fact_id)}
            type="button"
          >
            <div className="factHeader">
              <strong>{fact.display_label}</strong>
              <span className={`factStatus ${fact.status}`}>{fact.status}</span>
            </div>
            <p>{fact.normalized_value}</p>
            <dl>
              <div>
                <dt>Confidence</dt>
                <dd>{Math.round(fact.extraction_confidence * 100)}%</dd>
              </div>
              <div>
                <dt>Destination</dt>
                <dd>{fact.proposed_destination}</dd>
              </div>
              <div>
                <dt>Citation</dt>
                <dd>{`${fact.citation.page_or_section} / ${fact.citation.field_or_chunk_id}`}</dd>
              </div>
            </dl>
            <div className="factChecks" aria-label={`${fact.display_label} evidence checks`}>
              <span className={fact.schema_valid === false ? "blocked" : "ready"}>
                schema {fact.schema_valid === false ? "invalid" : "valid"}
              </span>
              <span className={fact.citation_present === false ? "blocked" : "ready"}>
                citation {fact.citation_present === false ? "missing" : "present"}
              </span>
              <span className={fact.bbox_present === false ? "blocked" : "ready"}>
                bbox {fact.bbox_present === false ? "missing" : "present"}
              </span>
            </div>
            <div className="factQuote">
              <strong>Quote</strong>
              <span>{fact.citation.quote_or_value}</span>
            </div>
            <div className="factMetaLine">
              <span>{fact.fact_id}</span>
              {fact.reviewed_by ? <span>reviewed by {fact.reviewed_by}</span> : null}
            </div>
            {fact.blocking_reasons.length ? (
              <small>{fact.blocking_reasons.join(", ")}</small>
            ) : null}
            {fact.written_resource_id ? <small>Observation {fact.written_resource_id}</small> : null}
            {fact.write_error ? (
              <small className="factError">Write failed: {fact.write_error}</small>
            ) : null}
          </button>
        ))}
      </div>
      <GraphTracePanel trace={trace} />
    </div>
  );
}
