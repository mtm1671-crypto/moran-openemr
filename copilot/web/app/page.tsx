"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { DocumentUploadPanel } from "./components/DocumentUploadPanel";

type RequestUser = {
  user_id: string;
  role: string;
  scopes: string[];
};

type PatientSummary = {
  patient_id: string;
  display_name: string;
  birth_date: string | null;
  gender: string | null;
};

type Citation = {
  evidence_id: string;
  label: string;
  source_url: string | null;
};

type ChatAudit = {
  verification?: string;
  tools?: string[];
  limitations?: string[];
  evidence_count?: number;
  evidence_used_count?: number;
  reasoning_summary?: string;
  [key: string]: unknown;
};

type ChatLine = {
  role: "user" | "assistant" | "status";
  text: string;
  citations?: Citation[];
  audit?: ChatAudit;
};

type SsePayload = {
  message?: string;
  answer?: string;
  citations?: Citation[];
  audit?: ChatAudit;
  evidence_count?: number;
  tools?: string[];
};

type AuthStatus = "checking" | "authenticated" | "authenticating" | "failed";

const API_REQUEST_TIMEOUT_MS = 20_000;
const CHAT_STALL_TIMEOUT_MS = 45_000;

const quickQuestions = [
  {
    id: "pre_room_brief",
    label: "Pre-room brief",
    prompt: "What should I know before seeing this patient?"
  },
  {
    id: "patient_demographics",
    label: "Demographics",
    prompt: "What is the patient's name and date of birth?"
  },
  {
    id: "active_problems",
    label: "Active problems",
    prompt: "Summarize active problems and relevant history."
  },
  {
    id: "recent_labs",
    label: "Recent labs",
    prompt: "Show recent labs and abnormal results."
  },
  {
    id: "meds_allergies",
    label: "Meds + allergies",
    prompt: "Show current medications and allergies."
  },
  {
    id: "recent_notes",
    label: "Recent notes",
    prompt: "Summarize recent clinical notes for this patient."
  },
  {
    id: "barriers_context",
    label: "Barriers",
    prompt: "What adherence or social barriers are documented?"
  }
];

export default function Home() {
  const apiBase = useMemo(
    () => (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, ""),
    []
  );
  const [session, setSession] = useState<RequestUser | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");
  const [patientRoster, setPatientRoster] = useState<PatientSummary[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<PatientSummary | null>(null);
  const [message, setMessage] = useState(quickQuestions[0].prompt);
  const [lines, setLines] = useState<ChatLine[]>([
    {
      role: "status",
      text: "Checking OpenEMR authorization."
    }
  ]);
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    async function initialize() {
      const launchParams = new URLSearchParams(window.location.search);
      const authError = launchParams.get("auth_error");
      if (authError) {
        setAuthStatus("failed");
        setLines((current) => [
          ...current,
          { role: "status", text: `OpenEMR authorization failed: ${authError}` }
        ]);
        return;
      }

      const authenticated = await loadSession(launchParams);
      if (!authenticated) {
        return;
      }

      const launchPatientId = launchParams.get("patient_id");
      if (launchPatientId) {
        await loadLaunchPatient(launchPatientId, launchParams);
        await loadPatientRoster(false);
      } else {
        await loadPatientRoster(true);
      }
    }

    void initialize();
  }, [apiBase]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [lines]);

  async function loadSession(launchParams: URLSearchParams) {
    try {
      const response = await fetchWithTimeout(`${apiBase}/api/me`, { cache: "no-store" });
      if (response.status === 401) {
        beginSmartAuth(launchParams);
        return false;
      }
      if (!response.ok) {
        throw new Error(`Auth check returned ${response.status}`);
      }
      const user = (await response.json()) as RequestUser;
      setSession(user);
      setAuthStatus("authenticated");
      setLines((current) => [
        ...current,
        { role: "status", text: `Authenticated as ${user.role}` }
      ]);
      return true;
    } catch (error) {
      setAuthStatus("failed");
      setLines((current) => [
        ...current,
        {
          role: "status",
          text: errorMessage(error, "Auth check failed")
        }
      ]);
      return false;
    }
  }

  function beginSmartAuth(launchParams: URLSearchParams) {
    setAuthStatus("authenticating");
    setLines((current) => [
      ...current,
      { role: "status", text: "OpenEMR authorization required. Redirecting to sign in." }
    ]);

    const startUrl = new URL("/api/auth/start", window.location.origin);
    startUrl.searchParams.set("redirect_to", `${window.location.pathname}${window.location.search}`);
    for (const key of ["iss", "aud", "launch"]) {
      const value = launchParams.get(key);
      if (value) {
        startUrl.searchParams.set(key, value);
      }
    }
    window.location.assign(startUrl.toString());
  }

  async function loadLaunchPatient(patientId: string, launchParams: URLSearchParams) {
    try {
      const response = await fetchWithTimeout(
        `${apiBase}/api/patients/${encodeURIComponent(patientId)}`,
        {
          cache: "no-store"
        }
      );
      if (!response.ok) {
        throw new Error(`Patient context returned ${response.status}`);
      }
      const patient = (await response.json()) as PatientSummary;
      setPatientRoster((current) => mergePatients(current, [patient]));
      setSelectedPatient(patient);
      setLines((current) => [
        ...current,
        { role: "status", text: "Loaded patient context from OpenEMR launch." }
      ]);
      if (launchParams.get("launch_context") === "schedule") {
        setLines((current) => [
          ...current,
          { role: "status", text: "Schedule appointment context included." }
        ]);
      }
    } catch (error) {
      setLines((current) => [
        ...current,
        {
          role: "status",
          text: errorMessage(error, "Patient context failed")
        }
      ]);
    }
  }

  async function loadPatientRoster(selectFirst: boolean) {
    try {
      const response = await fetchWithTimeout(`${apiBase}/api/patients?count=100`, {
        cache: "no-store"
      });
      if (!response.ok) {
        throw new Error(`Patient roster returned ${response.status}`);
      }
      const results = (await response.json()) as PatientSummary[];
      setPatientRoster((current) => mergePatients(current, results));
      if (selectFirst && results.length) {
        setSelectedPatient((current) => current ?? results[0]);
      }
      setLines((current) => [
        ...current,
        { role: "status", text: `${results.length} authorized patients loaded.` }
      ]);
    } catch (error) {
      setLines((current) => [
        ...current,
        {
          role: "status",
          text: errorMessage(error, "Patient roster failed")
        }
      ]);
    }
  }

  async function sendChat(nextMessage: string, quickQuestionId?: string) {
    if (!selectedPatient?.patient_id || !nextMessage.trim()) {
      setLines((current) => [
        ...current,
        { role: "status", text: "Select a patient before sending a chart question." }
      ]);
      return;
    }

    setIsSending(true);
    setLines((current) => [...current, { role: "user", text: nextMessage }]);

    const controller = new AbortController();
    let stallTimer: ReturnType<typeof setTimeout> | undefined;
    let sawFinal = false;
    const armStallTimer = () => {
      if (stallTimer) clearTimeout(stallTimer);
      stallTimer = setTimeout(() => controller.abort(), CHAT_STALL_TIMEOUT_MS);
    };

    try {
      armStallTimer();
      const response = await fetch(`${apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        signal: controller.signal,
        body: JSON.stringify({
          patient_id: selectedPatient.patient_id,
          message: nextMessage,
          quick_question_id: quickQuestionId
        })
      });

      if (!response.ok || !response.body) {
        throw new Error(`API returned ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        armStallTimer();
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const event of events) {
          if (handleSseEvent(event) === "final") {
            sawFinal = true;
          }
        }
      }
      if (!sawFinal) {
        throw new Error("The assistant stream ended before a verified answer arrived.");
      }
    } catch (error) {
      setLines((current) => [
        ...current,
        { role: "status", text: errorMessage(error, "Request failed") }
      ]);
    } finally {
      if (stallTimer) clearTimeout(stallTimer);
      setIsSending(false);
    }
  }

  function handleSseEvent(raw: string): "status" | "final" | null {
    const eventLine = raw.split("\n").find((line) => line.startsWith("event:"));
    const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
    const event = eventLine?.replace("event:", "").trim();
    const data = dataLine?.replace("data:", "").trim();
    if (!event || !data) return null;

    let parsed: SsePayload;
    try {
      parsed = JSON.parse(data) as SsePayload;
    } catch {
      setLines((current) => [
        ...current,
        { role: "status", text: "A malformed streaming event was ignored." }
      ]);
      return null;
    }
    if (event === "status") {
      const toolText = parsed.tools?.length ? ` - ${parsed.tools.join(", ")}` : "";
      const countText =
        typeof parsed.evidence_count === "number" ? ` - ${parsed.evidence_count} evidence` : "";
      setLines((current) => [
        ...current,
        { role: "status", text: `${parsed.message ?? "working"}${toolText}${countText}` }
      ]);
      return "status";
    }
    if (event === "final") {
      setLines((current) => [
        ...current,
        {
          role: "assistant",
          text: parsed.answer ?? "No verified answer returned.",
          citations: parsed.citations,
          audit: parsed.audit
        }
      ]);
      return "final";
    }
    return null;
  }

  function onPatientSelect(patientId: string) {
    const patient = patientRoster.find((item) => item.patient_id === patientId);
    if (!patient) return;
    setSelectedPatient(patient);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendChat(message);
  }

  function resetTranscript() {
    setLines([
      {
        role: "status",
        text: session ? `Authenticated as ${session.role}` : "Checking OpenEMR authorization."
      }
    ]);
  }

  function sourceHref(citation: Citation) {
    if (!citation.source_url) return undefined;
    if (
      !citation.source_url.startsWith("/api/source/") &&
      !citation.source_url.startsWith("/api/documents/")
    ) {
      return undefined;
    }
    return `${apiBase}${citation.source_url}`;
  }

  function sessionLabel() {
    if (session) {
      return `Authenticated as ${session.role} (${session.user_id})`;
    }
    if (authStatus === "authenticating") {
      return "Opening OpenEMR sign-in";
    }
    if (authStatus === "failed") {
      return "Authorization required";
    }
    return "Checking auth";
  }

  function patientOptionLabel(patient: PatientSummary) {
    const details = [patient.birth_date, patient.gender].filter(Boolean).join(" - ");
    return details ? `${patient.display_name} (${details})` : patient.display_name;
  }

  const isAuthenticated = authStatus === "authenticated";

  return (
    <main className="workspace">
      <header className="topbar">
        <div className="brandBlock">
          <p className="eyebrow">OpenEMR workspace</p>
          <h1>AgentForge Clinical Co-Pilot</h1>
          <p className="sessionLine">{sessionLabel()}</p>
        </div>

        <div className="patientHeaderIdentity">
          <span className="headerLabel">Patient</span>
          <strong>{selectedPatient?.display_name ?? "None selected"}</strong>
          <small>
            {selectedPatient
              ? [selectedPatient.birth_date ?? "DOB unknown", selectedPatient.gender ?? "gender unknown"].join(
                  " - "
                )
              : "Patient roster loading"}
          </small>
        </div>

        <div className="patientSwitcher">
          <label htmlFor="patient-switcher">Switch patient</label>
          <select
            disabled={!patientRoster.length}
            id="patient-switcher"
            onChange={(event) => onPatientSelect(event.target.value)}
            value={selectedPatient?.patient_id ?? ""}
          >
            {!selectedPatient ? <option value="">No patient selected</option> : null}
            {patientRoster.map((patient) => (
              <option key={patient.patient_id} value={patient.patient_id}>
                {patientOptionLabel(patient)}
              </option>
            ))}
          </select>
          <code>{selectedPatient?.patient_id ?? "No patient selected"}</code>
        </div>
      </header>

      <nav className="actionBar" aria-label="Quick chart actions">
        {quickQuestions.map((question) => (
          <button
            className={question.id === "pre_room_brief" ? "quickButton primary" : "quickButton"}
            disabled={isSending || !selectedPatient || !isAuthenticated}
            key={question.id}
            onClick={() => {
              setMessage(question.prompt);
              void sendChat(question.prompt, question.id);
            }}
            title={question.prompt}
            type="button"
          >
            <strong>{question.label}</strong>
            <span>{question.prompt}</span>
          </button>
        ))}
      </nav>

      <DocumentUploadPanel
        apiBase={apiBase}
        disabled={!selectedPatient || !isAuthenticated}
        patientId={selectedPatient?.patient_id ?? null}
        onStatus={(text) => setLines((current) => [...current, { role: "status", text }])}
      />

      <section className="chat" aria-label="Chat">
        <div className="messages">
          {lines.map((line, index) => (
            <div className={`line ${line.role}`} key={`${line.role}-${index}`}>
              <span className="lineText">{line.text}</span>
              {line.citations?.length ? (
                <div className="citationList">
                  {line.citations.map((citation) => (
                    <a
                      href={sourceHref(citation)}
                      key={citation.evidence_id}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {citation.label}
                    </a>
                  ))}
                </div>
              ) : null}
              {line.audit ? (
                <div className="auditTrace">
                  {line.audit.tools?.length ? <span>{line.audit.tools.join(" -> ")}</span> : null}
                  {line.audit.verification ? <span>{line.audit.verification}</span> : null}
                  {line.audit.reasoning_summary ? <span>{line.audit.reasoning_summary}</span> : null}
                </div>
              ) : null}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <form className="composer" onSubmit={onSubmit}>
          <input
            aria-label="Message"
            disabled={!isAuthenticated}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about this chart"
          />
          <button
            className="secondaryButton"
            disabled={isSending}
            onClick={resetTranscript}
            type="button"
          >
            Clear
          </button>
          <button disabled={isSending || !selectedPatient || !isAuthenticated} type="submit">
            {isSending ? "Verifying" : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = API_REQUEST_TIMEOUT_MS
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

function mergePatients(current: PatientSummary[], next: PatientSummary[]) {
  const byId = new Map(current.map((patient) => [patient.patient_id, patient]));
  for (const patient of next) {
    byId.set(patient.patient_id, patient);
  }
  return [...byId.values()].sort((left, right) =>
    left.display_name.localeCompare(right.display_name)
  );
}
