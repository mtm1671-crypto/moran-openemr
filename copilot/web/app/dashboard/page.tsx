"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

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

type FhirResource = Record<string, unknown>;

type FhirBundle = {
  resourceType?: string;
  entry?: Array<{
    resource?: FhirResource;
  }>;
};

type DashboardItem = {
  id: string;
  title: string;
  detail: string;
  meta: string;
  status?: string;
};

type PatientHeader = {
  id: string;
  name: string;
  birthDate: string;
  sex: string;
  mrn: string;
  active: string;
};

type DashboardData = {
  patient: PatientHeader;
  allergies: DashboardItem[];
  problems: DashboardItem[];
  medications: DashboardItem[];
  prescriptions: DashboardItem[];
  careTeam: DashboardItem[];
  labs: DashboardItem[];
  fetchedAt: string;
  isStale: boolean;
  warning?: string;
};

type AuthStatus = "checking" | "authenticated" | "authenticating" | "failed";

const REQUEST_TIMEOUT_MS = 20_000;

export default function PatientDashboard() {
  const apiBase = useMemo(
    () => (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, ""),
    []
  );
  const [session, setSession] = useState<RequestUser | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");
  const [patientRoster, setPatientRoster] = useState<PatientSummary[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<PatientSummary | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState("Checking OpenEMR authorization.");
  const [refreshCounter, setRefreshCounter] = useState(0);

  const beginSmartAuth = useCallback((launchParams: URLSearchParams) => {
    setAuthStatus("authenticating");
    setStatusText("OpenEMR authorization required. Redirecting to sign in.");

    const startUrl = new URL("/api/auth/start", window.location.origin);
    startUrl.searchParams.set("redirect_to", `${window.location.pathname}${window.location.search}`);
    for (const key of ["iss", "aud", "launch"]) {
      const value = launchParams.get(key);
      if (value) {
        startUrl.searchParams.set(key, value);
      }
    }
    window.location.assign(startUrl.toString());
  }, []);

  const loadSession = useCallback(async (launchParams: URLSearchParams) => {
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
      setStatusText(`Authenticated as ${user.role}.`);
      return true;
    } catch (error) {
      setAuthStatus("failed");
      setStatusText(errorMessage(error, "Auth check failed"));
      return false;
    }
  }, [apiBase, beginSmartAuth]);

  const loadPatientRoster = useCallback(async (selectPatientId: string | null) => {
    const response = await fetchWithTimeout(`${apiBase}/api/patients?count=100`, {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`Patient roster returned ${response.status}`);
    }
    const results = (await response.json()) as PatientSummary[];
    setPatientRoster(results);
    const selected =
      results.find((patient) => patient.patient_id === selectPatientId) ?? results[0] ?? null;
    setSelectedPatient(selected);
    setStatusText(`${results.length} authorized patients loaded for dashboard.`);
    return selected;
  }, [apiBase]);

  useEffect(() => {
    async function initialize() {
      const launchParams = new URLSearchParams(window.location.search);
      const authError = launchParams.get("auth_error");
      if (authError) {
        setAuthStatus("failed");
        setStatusText(`OpenEMR authorization failed: ${authError}`);
        return;
      }
      const authenticated = await loadSession(launchParams);
      if (!authenticated) return;

      try {
        await loadPatientRoster(launchParams.get("patient_id"));
      } catch (error) {
        setStatusText(errorMessage(error, "Patient roster failed"));
      }
    }

    void initialize();
  }, [loadPatientRoster, loadSession]);

  useEffect(() => {
    const patientId = selectedPatient?.patient_id ?? "";
    if (!patientId || authStatus !== "authenticated") return;

    async function loadDashboard() {
      setIsLoading(true);
      setStatusText("Refreshing dashboard from OpenEMR FHIR.");
      try {
        const next = await fetchDashboardData(patientId);
        setDashboard(next);
        setStatusText("Dashboard refreshed from OpenEMR FHIR.");
      } catch (error) {
        setDashboard((current) =>
          current && current.patient.id === patientId
            ? {
                ...current,
                isStale: true,
                warning: errorMessage(error, "OpenEMR refresh failed")
              }
            : null
        );
        setStatusText(errorMessage(error, "OpenEMR refresh failed"));
      } finally {
        setIsLoading(false);
      }
    }

    void loadDashboard();
  }, [authStatus, refreshCounter, selectedPatient]);

  function onPatientSelect(patientId: string) {
    const patient = patientRoster.find((item) => item.patient_id === patientId);
    if (!patient) return;
    setSelectedPatient(patient);
  }

  const chatHref = selectedPatient?.patient_id
    ? `/?patient_id=${encodeURIComponent(selectedPatient.patient_id)}`
    : "/";

  return (
    <main className="dashboardShell">
      <header className="dashboardTopbar">
        <div className="brandBlock">
          <p className="eyebrow">OpenEMR patient dashboard</p>
          <h1>Modern Patient Dashboard</h1>
          <p className="sessionLine">{sessionLabel(session, authStatus)}</p>
        </div>

        <div className="dashboardActions">
          <a className="secondaryLink" href={chatHref}>
            Ask Co-Pilot
          </a>
          <a className="secondaryLink" href="/status">
            System status
          </a>
          <button
            disabled={!selectedPatient || isLoading}
            onClick={() => setRefreshCounter((value) => value + 1)}
            type="button"
          >
            {isLoading ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </header>

      <section className="dashboardPatientBar" aria-label="Patient selection">
        <div className="patientSwitcher dashboardPatientSelect">
          <label htmlFor="dashboard-patient-switcher">Dashboard patient</label>
          <select
            disabled={!patientRoster.length}
            id="dashboard-patient-switcher"
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
        </div>
        <div className="dashboardStatus">
          <span className={dashboard?.isStale ? "sourceBadge stale" : "sourceBadge"}>
            {dashboard?.isStale ? "Cached in session" : "Live FHIR"}
          </span>
          <span>{statusText}</span>
        </div>
      </section>

      {dashboard ? (
        <>
          <PatientIdentityPanel patient={dashboard.patient} fetchedAt={dashboard.fetchedAt} />
          {dashboard.warning ? <p className="dashboardWarning">{dashboard.warning}</p> : null}
          <section className="dashboardGrid" aria-label="Clinical dashboard cards">
            <ClinicalCard title="Allergies" source="AllergyIntolerance" items={dashboard.allergies} />
            <ClinicalCard title="Problem List" source="Condition" items={dashboard.problems} />
            <ClinicalCard title="Medications" source="MedicationRequest" items={dashboard.medications} />
            <ClinicalCard title="Prescriptions" source="MedicationRequest" items={dashboard.prescriptions} />
            <ClinicalCard title="Care Team" source="CareTeam" items={dashboard.careTeam} />
            <ClinicalCard title="Recent Labs" source="Observation" items={dashboard.labs} />
          </section>
        </>
      ) : (
        <section className="dashboardEmpty">
          <h2>{isLoading ? "Loading dashboard" : "No dashboard data loaded"}</h2>
          <p>Select an authorized OpenEMR patient to load live FHIR-backed dashboard cards.</p>
        </section>
      )}
    </main>
  );
}

function PatientIdentityPanel({ patient, fetchedAt }: { patient: PatientHeader; fetchedAt: string }) {
  return (
    <section className="patientIdentityPanel" aria-label="Patient header">
      <div>
        <p className="eyebrow">Patient header</p>
        <h2>{patient.name}</h2>
        <span className={patient.active === "active" ? "activeBadge" : "inactiveBadge"}>
          {patient.active}
        </span>
      </div>
      <dl>
        <div>
          <dt>Date of birth</dt>
          <dd>{patient.birthDate}</dd>
        </div>
        <div>
          <dt>Sex</dt>
          <dd>{patient.sex}</dd>
        </div>
        <div>
          <dt>MRN</dt>
          <dd>{patient.mrn}</dd>
        </div>
        <div>
          <dt>Last verified</dt>
          <dd>{formatTimestamp(fetchedAt)}</dd>
        </div>
      </dl>
    </section>
  );
}

function ClinicalCard({
  title,
  source,
  items
}: {
  title: string;
  source: string;
  items: DashboardItem[];
}) {
  return (
    <article className="clinicalCard">
      <header>
        <div>
          <h2>{title}</h2>
          <span>{source}</span>
        </div>
        <strong>{items.length}</strong>
      </header>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </div>
              <span>
                {item.status ? `${item.status} - ` : ""}
                {item.meta}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cardEmpty">No records exposed by OpenEMR FHIR for this section.</p>
      )}
    </article>
  );
}

async function fetchDashboardData(patientId: string): Promise<DashboardData> {
  const [
    patient,
    allergies,
    problems,
    medicationRequests,
    careTeams,
    observations
  ] = await Promise.all([
    fetchFhirResource(`/api/dashboard/fhir/Patient/${encodeURIComponent(patientId)}`),
    fetchFhirBundle(`/api/dashboard/fhir/AllergyIntolerance?patient=${encodeURIComponent(patientId)}&_count=20`),
    fetchFhirBundle(`/api/dashboard/fhir/Condition?patient=${encodeURIComponent(patientId)}&_count=20`),
    fetchFhirBundle(`/api/dashboard/fhir/MedicationRequest?patient=${encodeURIComponent(patientId)}&_count=30`),
    fetchFhirBundle(`/api/dashboard/fhir/CareTeam?patient=${encodeURIComponent(patientId)}&_count=20`),
    fetchFhirBundle(`/api/dashboard/fhir/Observation?patient=${encodeURIComponent(patientId)}&_count=20&_sort=-date`)
  ]);
  const medicationResources = resourcesFromBundle(medicationRequests);

  return {
    patient: parsePatient(patient, patientId),
    allergies: resourcesFromBundle(allergies).map(parseAllergy),
    problems: resourcesFromBundle(problems).map(parseCondition),
    medications: medicationResources.map(parseMedication),
    prescriptions: medicationResources.map(parsePrescription),
    careTeam: resourcesFromBundle(careTeams).map(parseCareTeam),
    labs: resourcesFromBundle(observations)
      .map(parseObservation)
      .filter((item): item is DashboardItem => item !== null)
      .slice(0, 8),
    fetchedAt: new Date().toISOString(),
    isStale: false
  };
}

async function fetchFhirResource(path: string): Promise<FhirResource> {
  const response = await fetchWithTimeout(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`FHIR ${path} returned ${response.status}`);
  }
  return (await response.json()) as FhirResource;
}

async function fetchFhirBundle(path: string): Promise<FhirBundle> {
  return (await fetchFhirResource(path)) as FhirBundle;
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

function resourcesFromBundle(bundle: FhirBundle): FhirResource[] {
  return Array.isArray(bundle.entry)
    ? bundle.entry.map((entry) => entry.resource).filter((item): item is FhirResource => Boolean(item))
    : [];
}

function parsePatient(resource: FhirResource, fallbackId: string): PatientHeader {
  return {
    id: asString(resource.id) || fallbackId,
    name: patientName(resource) || "Unnamed patient",
    birthDate: asString(resource.birthDate) || "Unknown",
    sex: titleCase(asString(resource.gender) || "Unknown"),
    mrn: patientMrn(resource),
    active: resource.active === false ? "inactive" : "active"
  };
}

function parseAllergy(resource: FhirResource): DashboardItem {
  return {
    id: resourceKey(resource, "allergy"),
    title: codeableText(resource.code) || "Allergy",
    detail: [criticalityText(resource.criticality), reactionText(resource)].filter(Boolean).join(" - ") || "No reaction detail",
    meta: asString(resource.recordedDate) || asString(resource.onsetDateTime) || "date unknown",
    status: asString(resource.clinicalStatus) || asString(resource.verificationStatus)
  };
}

function parseCondition(resource: FhirResource): DashboardItem {
  return {
    id: resourceKey(resource, "condition"),
    title: codeableText(resource.code) || "Condition",
    detail: asString(resource.note) || asString(resource.category) || "Problem list item",
    meta: asString(resource.onsetDateTime) || asString(resource.recordedDate) || "date unknown",
    status: nestedCodingText(resource.clinicalStatus) || asString(resource.clinicalStatus)
  };
}

function parseMedication(resource: FhirResource): DashboardItem {
  return {
    id: `${resourceKey(resource, "med")}-med`,
    title: medicationName(resource),
    detail: dosageText(resource) || "Medication request",
    meta: asString(resource.authoredOn) || "date unknown",
    status: asString(resource.status)
  };
}

function parsePrescription(resource: FhirResource): DashboardItem {
  return {
    id: `${resourceKey(resource, "rx")}-rx`,
    title: medicationName(resource),
    detail: requesterText(resource) || "Prescription request",
    meta: asString(resource.intent) || "intent unknown",
    status: asString(resource.status)
  };
}

function parseCareTeam(resource: FhirResource): DashboardItem {
  const participant = arrayValue(resource.participant)[0];
  const participantRecord = asRecord(participant);
  return {
    id: resourceKey(resource, "care-team"),
    title:
      codeableText(participantRecord?.role) ||
      displayReference(participantRecord?.member) ||
      asString(resource.name) ||
      "Care team member",
    detail: displayReference(participantRecord?.member) || asString(resource.name) || "OpenEMR care team",
    meta: periodText(resource.period) || "period unknown",
    status: asString(resource.status)
  };
}

function parseObservation(resource: FhirResource): DashboardItem | null {
  const code = codeableText(resource.code) || "Observation";
  const value = observationValue(resource);
  if (!value && !code) return null;
  return {
    id: resourceKey(resource, "observation"),
    title: code,
    detail: value || "No value exposed",
    meta: asString(resource.effectiveDateTime) || asString(resource.issued) || "date unknown",
    status: nestedCodingText(arrayValue(resource.interpretation)[0]) || asString(resource.status)
  };
}

function patientName(resource: FhirResource): string {
  const firstName = asRecord(arrayValue(resource.name)[0]);
  if (!firstName) return "";
  const given = arrayValue(firstName.given).map(asString).filter(Boolean).join(" ");
  const family = asString(firstName.family);
  return [given, family].filter(Boolean).join(" ");
}

function patientMrn(resource: FhirResource): string {
  const identifiers = arrayValue(resource.identifier).map(asRecord).filter(Boolean);
  const mrn =
    identifiers.find((identifier) => nestedCodingText(identifier?.type).toLowerCase() === "mr") ??
    identifiers[0];
  return asString(mrn?.value) || "Unknown";
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
    asString(resource.valueCodeableConcept) ||
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

function periodText(value: unknown): string {
  const period = asRecord(value);
  if (!period) return "";
  return [asString(period.start), asString(period.end)].filter(Boolean).join(" to ");
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function resourceKey(resource: FhirResource, prefix: string): string {
  return asString(resource.id) || `${prefix}-${JSON.stringify(resource).length}`;
}

function titleCase(value: string): string {
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1).toLowerCase()}` : value;
}

function patientOptionLabel(patient: PatientSummary) {
  const details = [patient.birth_date, patient.gender].filter(Boolean).join(" - ");
  return details ? `${patient.display_name} (${details})` : patient.display_name;
}

function sessionLabel(user: RequestUser | null, status: AuthStatus) {
  if (user) {
    return `Authenticated as ${user.role} (${user.user_id})`;
  }
  if (status === "authenticating") {
    return "Opening OpenEMR sign-in";
  }
  if (status === "failed") {
    return "Authorization required";
  }
  return "Checking auth";
}

function formatTimestamp(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short"
    }).format(new Date(value));
  } catch {
    return value;
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
