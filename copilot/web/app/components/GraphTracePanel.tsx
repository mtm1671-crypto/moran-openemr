type GraphTracePanelProps = {
  trace: string[];
};

export function GraphTracePanel({ trace }: GraphTracePanelProps) {
  return (
    <div className="tracePanel" aria-label="Workflow trace">
      <strong>Trace</strong>
      {trace.length ? (
        <ol>
          {trace.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ol>
      ) : (
        <span>No trace events yet</span>
      )}
    </div>
  );
}

