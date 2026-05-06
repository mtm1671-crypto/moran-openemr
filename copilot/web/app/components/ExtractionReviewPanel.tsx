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
  written_resource_id: string | null;
  write_error: string | null;
};

type ExtractionReviewPanelProps = {
  facts: DocumentFact[];
  trace: string[];
};

export function ExtractionReviewPanel({ facts, trace }: ExtractionReviewPanelProps) {
  const selectedFact = facts[0] ?? null;

  return (
    <div className="reviewGrid">
      <PdfBoundingBoxPreview fact={selectedFact} />
      <div className="factList" aria-label="Extracted facts">
        {facts.map((fact) => (
          <article className="factCard" key={fact.fact_id}>
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
                <dd>{fact.citation.page_or_section}</dd>
              </div>
            </dl>
            {fact.blocking_reasons.length ? (
              <small>{fact.blocking_reasons.join(", ")}</small>
            ) : null}
            {fact.written_resource_id ? <small>Observation {fact.written_resource_id}</small> : null}
            {fact.write_error ? <small>{fact.write_error}</small> : null}
          </article>
        ))}
      </div>
      <GraphTracePanel trace={trace} />
    </div>
  );
}
