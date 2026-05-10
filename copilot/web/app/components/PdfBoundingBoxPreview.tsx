import Image from "next/image";

import type { DocumentFact } from "./ExtractionReviewPanel";

type PdfBoundingBoxPreviewProps = {
  fact: DocumentFact | null;
  sourceUrl: string | null;
  contentType: string | null;
};

export function PdfBoundingBoxPreview({ fact, sourceUrl, contentType }: PdfBoundingBoxPreviewProps) {
  const bbox = fact?.citation.bbox;
  const isImage = contentType?.startsWith("image/") ?? false;
  const canEmbedSource = Boolean(sourceUrl);

  return (
    <div className="sourcePreview" aria-label="Source preview">
      <div className="sourcePage">
        {canEmbedSource && isImage ? (
          <Image
            alt=""
            className="sourceDocumentImage"
            fill
            sizes="170px"
            src={sourceUrl ?? ""}
            unoptimized
          />
        ) : null}
        {canEmbedSource && !isImage ? (
          <iframe className="sourceDocumentFrame" src={sourceUrl ?? ""} title="Source document page" />
        ) : null}
        {bbox ? (
          <span
            className="bbox"
            aria-label="Selected citation bounding box"
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
