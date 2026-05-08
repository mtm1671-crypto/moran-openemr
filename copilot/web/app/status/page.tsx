"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type ReadyPayload = {
  ok?: boolean;
  service?: string;
  environment?: string;
  checks?: Record<string, boolean>;
  errors?: string[];
};

type CapabilityPayload = {
  providers?: Record<string, boolean>;
};

type SessionPayload = {
  authenticated?: boolean;
  scope?: string | null;
};

type StatusState = {
  ready: ReadyPayload | null;
  capabilities: CapabilityPayload | null;
  session: SessionPayload | null;
  error: string | null;
};

type StatusItem = {
  label: string;
  detail: string;
  state: "working" | "limited" | "blocked";
};

export default function StatusPage() {
  const [state, setState] = useState<StatusState>({
    ready: null,
    capabilities: null,
    session: null,
    error: null
  });
  const [isLoading, setIsLoading] = useState(true);

  const loadStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      const [readyResponse, capabilityResponse, sessionResponse] = await Promise.all([
        fetch("/api/readyz", { cache: "no-store" }),
        fetch("/api/capabilities", { cache: "no-store" }),
        fetch("/api/auth/session", { cache: "no-store" })
      ]);
      const ready = readyResponse.ok ? ((await readyResponse.json()) as ReadyPayload) : null;
      const capabilities = capabilityResponse.ok
        ? ((await capabilityResponse.json()) as CapabilityPayload)
        : null;
      const session = sessionResponse.ok ? ((await sessionResponse.json()) as SessionPayload) : null;
      setState({
        ready,
        capabilities,
        session,
        error:
          readyResponse.ok && capabilityResponse.ok
            ? null
            : `Readiness returned ${readyResponse.status}; capabilities returned ${capabilityResponse.status}.`
      });
    } catch (error) {
      setState({
        ready: null,
        capabilities: null,
        session: null,
        error: errorMessage(error, "Status checks failed")
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const statusItems = useMemo(() => buildStatusItems(state), [state]);
  const working = statusItems.filter((item) => item.state === "working");
  const limited = statusItems.filter((item) => item.state === "limited");
  const blocked = statusItems.filter((item) => item.state === "blocked");
  const checks = state.ready?.checks ?? {};

  return (
    <main className="statusShell">
      <header className="dashboardTopbar">
        <div className="brandBlock">
          <p className="eyebrow">Operational truth</p>
          <h1>Co-Pilot Status</h1>
          <p className="sessionLine">{statusSummary(state.ready, isLoading)}</p>
        </div>
        <div className="dashboardActions">
          <Link className="secondaryLink" href="/">
            Co-Pilot
          </Link>
          <button disabled={isLoading} onClick={() => void loadStatus()} type="button">
            {isLoading ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </header>

      <section className="statusOverview" aria-label="System status overview">
        <StatusColumn title="Working" items={working} empty="No green checks loaded yet." />
        <StatusColumn title="Limited" items={limited} empty="No conditional items detected." />
        <StatusColumn title="Blocked" items={blocked} empty="No blocked critical checks detected." />
      </section>

      {state.error ? <p className="dashboardWarning">{state.error}</p> : null}

      <section className="statusDetailGrid" aria-label="Detailed readiness checks">
        <article className="statusDetailPanel">
          <header>
            <h2>Readiness</h2>
            <span>{state.ready?.environment ?? "unknown environment"}</span>
          </header>
          <dl>
            {Object.entries(checks).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd className={value ? "readyText" : "blockedText"}>{String(value)}</dd>
              </div>
            ))}
          </dl>
        </article>

        <article className="statusDetailPanel">
          <header>
            <h2>Capabilities</h2>
            <span>Provider and feature flags</span>
          </header>
          <dl>
            {Object.entries(state.capabilities?.providers ?? {}).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd className={value ? "readyText" : "mutedText"}>{String(value)}</dd>
              </div>
            ))}
          </dl>
        </article>

        <article className="statusDetailPanel">
          <header>
            <h2>Current Session</h2>
            <span>{state.session?.authenticated ? "Authenticated" : "No web session"}</span>
          </header>
          <p>
            Observation write is available only when the SMART session includes
            `user/Observation.write` or `patient/Observation.write`.
          </p>
          <code>{state.session?.scope ?? "No session scope loaded."}</code>
        </article>
      </section>
    </main>
  );
}

function StatusColumn({
  title,
  items,
  empty
}: {
  title: string;
  items: StatusItem[];
  empty: string;
}) {
  return (
    <section className="statusColumn">
      <header>
        <h2>{title}</h2>
        <strong>{items.length}</strong>
      </header>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li className={item.state} key={item.label}>
              <strong>{item.label}</strong>
              <span>{item.detail}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </section>
  );
}

function buildStatusItems(state: StatusState): StatusItem[] {
  const checks = state.ready?.checks ?? {};
  const providers = state.capabilities?.providers ?? {};
  const sessionScope = state.session?.scope ?? "";
  const hasObservationWrite =
    sessionScope.includes("user/Observation.write") ||
    sessionScope.includes("patient/Observation.write") ||
    sessionScope.includes("user/Observation.cud") ||
    sessionScope.includes("patient/Observation.cud");
  const observationCreateSupported = providers.openemr_observation_create_supported !== false;

  return [
    item("API readiness", Boolean(state.ready?.ok), "FastAPI /readyz returns ok."),
    item("OpenEMR FHIR", checks.openemr_fhir_configured, "OpenEMR source-of-truth FHIR is configured."),
    item("Database", checks.database, "Database connectivity is available for durable state."),
    item(
      "Document persistence",
      checks.document_workflow_persistence_ready || providers.document_workflow_persistence_ready,
      "Document workflow storage is enabled and readable."
    ),
    item("Approved evidence retrieval", providers.document_workflow_persistence_ready, "Approved facts can be retrieved through the document evidence endpoint."),
    item("Vector search", providers.vector_search_enabled, "Hybrid/vector retrieval is enabled."),
    item("Evidence cache", providers.evidence_cache_enabled, "Evidence cache is enabled."),
    item("OCR", providers.ocr_enabled, "OCR or vision OCR is configured for image scans."),
    item("Audit persistence", checks.audit_persistence, "Clinical audit rows can be persisted."),
    item("Conversation persistence", checks.conversation_persistence, "Conversation rows can be persisted."),
    {
      label: "Observation writes",
      detail: !observationCreateSupported
        ? "This OpenEMR deployment does not expose FHIR Observation.create; approved evidence retrieval still works."
        : hasObservationWrite
        ? "Current SMART session has Observation write scope."
        : "Requires SMART Observation.write scope before Write labs is enabled.",
      state: !observationCreateSupported ? "blocked" : hasObservationWrite ? "working" : "limited"
    },
    {
      label: "Service-account reindex",
      detail: checks.service_account_configured
        ? "Background service account is configured."
        : "Nightly/backend reindex is limited until service account credentials are configured.",
      state: checks.service_account_configured ? "working" : "limited"
    },
    {
      label: "Nightly reindex",
      detail: checks.nightly_reindex_enabled
        ? "Nightly reindex is enabled."
        : "Nightly reindex is off; on-demand retrieval still works.",
      state: checks.nightly_reindex_enabled ? "working" : "limited"
    }
  ];
}

function item(label: string, ok: boolean | undefined, detail: string): StatusItem {
  return {
    label,
    detail,
    state: ok ? "working" : "blocked"
  };
}

function statusSummary(ready: ReadyPayload | null, loading: boolean): string {
  if (loading) return "Checking live status";
  if (!ready) return "Status unavailable";
  return ready.ok ? "Ready checks loaded" : "Readiness has failures";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
