"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

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
  }
];

export default function Home() {
  const apiBase = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001",
    []
  );
  const [session, setSession] = useState<RequestUser | null>(null);
  const [patientQuery, setPatientQuery] = useState("de");
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<PatientSummary | null>(null);
  const [message, setMessage] = useState(quickQuestions[0].prompt);
  const [lines, setLines] = useState<ChatLine[]>([
    {
      role: "status",
      text: "Authenticated session and patient-scoped evidence will appear here."
    }
  ]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    async function loadSession() {
      try {
        const response = await fetch(`${apiBase}/api/me`);
        if (!response.ok) {
          throw new Error(`Auth check returned ${response.status}`);
        }
        const user = (await response.json()) as RequestUser;
        setSession(user);
        setLines((current) => [
          ...current,
          { role: "status", text: `Authenticated as ${user.role}` }
        ]);
      } catch (error) {
        setLines((current) => [
          ...current,
          {
            role: "status",
            text: error instanceof Error ? error.message : "Auth check failed"
          }
        ]);
      }
    }

    void loadSession();
    void searchPatients("de", false);
  }, [apiBase]);

  async function searchPatients(query: string, showStatus = true) {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      if (showStatus) {
        setLines((current) => [
          ...current,
          { role: "status", text: "Patient search needs at least 2 characters." }
        ]);
      }
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch(`${apiBase}/api/patients?query=${encodeURIComponent(trimmed)}`);
      if (!response.ok) {
        throw new Error(`Patient search returned ${response.status}`);
      }
      const results = (await response.json()) as PatientSummary[];
      setPatients(results);
      setSelectedPatient(results[0] ?? null);
      if (showStatus) {
        setLines((current) => [
          ...current,
          { role: "status", text: `${results.length} patient matches returned.` }
        ]);
      }
    } catch (error) {
      setLines((current) => [
        ...current,
        {
          role: "status",
          text: error instanceof Error ? error.message : "Patient search failed"
        }
      ]);
    } finally {
      setIsSearching(false);
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

    try {
      const response = await fetch(`${apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const event of events) {
          handleSseEvent(event);
        }
      }
    } catch (error) {
      setLines((current) => [
        ...current,
        { role: "status", text: error instanceof Error ? error.message : "Request failed" }
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleSseEvent(raw: string) {
    const eventLine = raw.split("\n").find((line) => line.startsWith("event:"));
    const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
    const event = eventLine?.replace("event:", "").trim();
    const data = dataLine?.replace("data:", "").trim();
    if (!event || !data) return;

    const parsed = JSON.parse(data) as SsePayload;
    if (event === "status") {
      const toolText = parsed.tools?.length ? ` - ${parsed.tools.join(", ")}` : "";
      const countText =
        typeof parsed.evidence_count === "number" ? ` - ${parsed.evidence_count} evidence` : "";
      setLines((current) => [
        ...current,
        { role: "status", text: `${parsed.message ?? "working"}${toolText}${countText}` }
      ]);
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
    }
  }

  function onPatientSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void searchPatients(patientQuery);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendChat(message);
  }

  function sourceHref(citation: Citation) {
    if (!citation.source_url) return undefined;
    if (citation.source_url.startsWith("http")) return citation.source_url;
    return `${apiBase}${citation.source_url}`;
  }

  return (
    <main className="shell">
      <aside className="sidebar" aria-label="Patient context">
        <div>
          <p className="eyebrow">Clinical Co-Pilot</p>
          <h1>Patient-scoped chat</h1>
          <p className="sessionLine">
            {session ? `Local demo auth - ${session.role} - ${session.user_id}` : "Checking auth"}
          </p>
        </div>

        <form className="field" onSubmit={onPatientSearch}>
          <span>Patient search</span>
          <div className="searchRow">
            <input
              value={patientQuery}
              onChange={(event) => setPatientQuery(event.target.value)}
              placeholder="Name"
            />
            <button disabled={isSearching} type="submit">
              {isSearching ? "..." : "Search"}
            </button>
          </div>
        </form>

        <div className="patientList" aria-label="Patient results">
          {patients.map((patient) => (
            <button
              className={
                patient.patient_id === selectedPatient?.patient_id
                  ? "patientButton selected"
                  : "patientButton"
              }
              key={patient.patient_id}
              onClick={() => setSelectedPatient(patient)}
              type="button"
            >
              <strong>{patient.display_name}</strong>
              <span>
                {patient.birth_date ?? "DOB unknown"} - {patient.gender ?? "gender unknown"}
              </span>
            </button>
          ))}
          {!patients.length ? <p className="emptyState">No patient matches returned.</p> : null}
        </div>

        <div className="quickList" aria-label="Quick questions">
          {quickQuestions.map((question) => (
            <button
              className="quickButton"
              disabled={isSending || !selectedPatient}
              key={question.id}
              onClick={() => {
                setMessage(question.prompt);
                void sendChat(question.prompt, question.id);
              }}
              type="button"
            >
              <strong>{question.label}</strong>
              <span>{question.prompt}</span>
            </button>
          ))}
        </div>
      </aside>

      <section className="chat" aria-label="Chat">
        <header className="patientHeader">
          <div>
            <span>Selected patient</span>
            <strong>{selectedPatient?.display_name ?? "None selected"}</strong>
          </div>
          <code>{selectedPatient?.patient_id ?? "Search by name"}</code>
        </header>

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
        </div>

        <form className="composer" onSubmit={onSubmit}>
          <input
            aria-label="Message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about the selected patient"
          />
          <button disabled={isSending || !selectedPatient} type="submit">
            {isSending ? "Verifying" : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}
