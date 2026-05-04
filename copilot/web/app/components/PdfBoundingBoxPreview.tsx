import type { DocumentFact } from "./ExtractionReviewPanel";

type PdfBoundingBoxPreviewProps = {
  fact: DocumentFact | null;
};

export function PdfBoundingBoxPreview({ fact }: PdfBoundingBoxPreviewProps) {
  const bbox = fact?.citation.bbox;

  return (
    <div className="sourcePreview" aria-label="Source preview">
      <div className="sourcePage">
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
      <strong>{fact?.citation.quote_or_value ?? "No fact selected"}</strong>
      <small>{fact ? `${fact.citation.page_or_section} - ${fact.citation.field_or_chunk_id}` : ""}</small>
    </div>
  );
}

