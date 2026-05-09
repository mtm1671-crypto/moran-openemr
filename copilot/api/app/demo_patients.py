from __future__ import annotations

from datetime import UTC, datetime

from app.models import EvidenceObject, PatientSummary


_CANONICAL_DEMO_PATIENTS: tuple[PatientSummary, ...] = (
    PatientSummary(
        patient_id="p1",
        display_name="Margaret Chen",
        birth_date="1967-08-14",
        gender="female",
    ),
    PatientSummary(
        patient_id="p2",
        display_name="James Whitaker",
        birth_date="1958-11-03",
        gender="male",
    ),
    PatientSummary(
        patient_id="p3",
        display_name="Sofia Reyes",
        birth_date="1983-12-19",
        gender="female",
    ),
    PatientSummary(
        patient_id="p4",
        display_name="Robert Kowalski",
        birth_date="1971-06-08",
        gender="male",
    ),
    PatientSummary(
        patient_id="demo-diabetes-001",
        display_name="Demo Patient",
        birth_date="1975-04-12",
        gender="female",
    ),
)

_DEMO_PATIENT_ALIASES = {
    "p01": "p1",
    "p02": "p2",
    "p03": "p3",
    "p04": "p4",
}

DEMO_PATIENT_IDS = {
    patient.patient_id for patient in _CANONICAL_DEMO_PATIENTS
} | set(_DEMO_PATIENT_ALIASES)


def demo_patient_summaries() -> list[PatientSummary]:
    return list(_CANONICAL_DEMO_PATIENTS)


def demo_patient_summary(patient_id: str) -> PatientSummary | None:
    canonical_id = _canonical_demo_patient_id(patient_id)
    for patient in _CANONICAL_DEMO_PATIENTS:
        if patient.patient_id == canonical_id:
            if patient_id == canonical_id:
                return patient
            return patient.model_copy(update={"patient_id": patient_id})
    return None


def demo_patient_fhir_resource(patient_id: str) -> dict[str, object] | None:
    patient = demo_patient_summary(patient_id)
    if patient is None:
        return None
    given, family = _split_display_name(patient.display_name)
    return {
        "resourceType": "Patient",
        "id": patient.patient_id,
        "name": [{"given": given, "family": family}],
        "birthDate": patient.birth_date,
        "gender": patient.gender,
    }


def demo_evidence(patient_id: str) -> list[EvidenceObject]:
    now = datetime.now(tz=UTC)
    patient = demo_patient_summary(patient_id)
    if patient is None:
        return []
    evidence = _demographic_evidence(patient=patient, retrieved_at=now)
    evidence.extend(_profile_evidence(patient_id=patient_id, retrieved_at=now))
    return evidence


def _canonical_demo_patient_id(patient_id: str) -> str:
    return _DEMO_PATIENT_ALIASES.get(patient_id, patient_id)


def _split_display_name(display_name: str) -> tuple[list[str], str]:
    parts = display_name.split()
    if not parts:
        return [], display_name
    if len(parts) == 1:
        return [], parts[0]
    return parts[:-1], parts[-1]


def _demographic_evidence(
    *,
    patient: PatientSummary,
    retrieved_at: datetime,
) -> list[EvidenceObject]:
    source_url = f"/api/source/demo-patient/{patient.patient_id}"
    evidence = [
        EvidenceObject(
            evidence_id=f"ev_demo_patient_{patient.patient_id}_name",
            patient_id=patient.patient_id,
            source_type="patient_demographics",
            source_id=patient.patient_id,
            display_name="Patient name",
            fact=f"Patient name is {patient.display_name}.",
            retrieved_at=retrieved_at,
            source_url=source_url,
            metadata={"field": "name"},
        )
    ]
    if patient.birth_date:
        evidence.append(
            EvidenceObject(
                evidence_id=f"ev_demo_patient_{patient.patient_id}_birthDate",
                patient_id=patient.patient_id,
                source_type="patient_demographics",
                source_id=patient.patient_id,
                display_name="Patient birth date",
                fact=f"Patient birth date is {patient.birth_date}.",
                effective_at=datetime.fromisoformat(patient.birth_date).replace(tzinfo=UTC),
                retrieved_at=retrieved_at,
                source_url=source_url,
                metadata={"field": "birthDate"},
            )
        )
    if patient.gender:
        evidence.append(
            EvidenceObject(
                evidence_id=f"ev_demo_patient_{patient.patient_id}_gender",
                patient_id=patient.patient_id,
                source_type="patient_demographics",
                source_id=patient.patient_id,
                display_name="Patient gender",
                fact=f"Patient gender is {patient.gender}.",
                retrieved_at=retrieved_at,
                source_url=source_url,
                metadata={"field": "gender"},
            )
        )
    return evidence


def _profile_evidence(patient_id: str, retrieved_at: datetime) -> list[EvidenceObject]:
    canonical_id = _canonical_demo_patient_id(patient_id)
    if canonical_id == "p1":
        return [
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_chen_ldl",
                source_id="demo-chen-lipid-panel",
                display_name="Margaret Chen LDL Cholesterol",
                fact="LDL Cholesterol was 158 mg/dL on 2026-04-23 (high).",
                effective_at=datetime(2026, 4, 23, tzinfo=UTC),
                retrieved_at=retrieved_at,
                source_url="/api/source/demo-chen-lipid-panel",
            ),
            _problem(patient_id, "type 2 diabetes mellitus", "Type 2 diabetes mellitus is active.", retrieved_at),
            _problem(patient_id, "essential hypertension", "Essential hypertension is active.", retrieved_at),
            _medication(patient_id, "Metformin", "Metformin 500 mg PO twice daily.", retrieved_at),
            _allergy(patient_id, "Penicillin", "Penicillin allergy: hives, moderate severity.", retrieved_at),
        ]
    if canonical_id == "p2":
        return [
            _problem(patient_id, "atrial fibrillation", "Atrial fibrillation is active.", retrieved_at),
            _problem(patient_id, "hyperlipidemia", "Hyperlipidemia is active.", retrieved_at),
            _problem(patient_id, "benign prostatic hyperplasia", "Benign prostatic hyperplasia is active.", retrieved_at),
            _medication(patient_id, "Apixaban", "Apixaban 5 mg PO twice daily.", retrieved_at),
            _medication(patient_id, "Tamsulosin", "Tamsulosin 0.4 mg PO daily.", retrieved_at),
            _medication(patient_id, "Atorvastatin", "Atorvastatin 40 mg PO at bedtime.", retrieved_at),
            _allergy(patient_id, "NKDA", "No known drug allergies are documented.", retrieved_at),
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_whitaker_hemoglobin",
                source_id="demo-whitaker-cbc",
                display_name="Hemoglobin",
                fact="Hemoglobin was 11.1 g/dL on 2026-04-21 (low).",
                effective_at=datetime(2026, 4, 21, tzinfo=UTC),
                retrieved_at=retrieved_at,
            ),
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_whitaker_hematocrit",
                source_id="demo-whitaker-cbc",
                display_name="Hematocrit",
                fact="Hematocrit was 33.5% on 2026-04-21 (low).",
                effective_at=datetime(2026, 4, 21, tzinfo=UTC),
                retrieved_at=retrieved_at,
            ),
        ]
    if canonical_id == "p3":
        return [
            _problem(patient_id, "type 2 diabetes", "Type 2 diabetes is active.", retrieved_at),
            _problem(patient_id, "mild recurrent depression", "Mild recurrent depression is active.", retrieved_at),
            _medication(patient_id, "Metformin", "Metformin 1000 mg BID.", retrieved_at),
            _medication(patient_id, "Ozempic", "Ozempic 1 mg SQ weekly.", retrieved_at),
            _medication(patient_id, "Sertraline", "Sertraline 50 mg daily.", retrieved_at),
            _allergy(patient_id, "Ibuprofen", "Ibuprofen allergy/intolerance: GI bleed, severe.", retrieved_at),
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_reyes_hba1c",
                source_id="demo-reyes-hba1c",
                display_name="Hemoglobin A1c",
                fact="Hemoglobin A1c was 7.4% on 2026-04-20 (high).",
                effective_at=datetime(2026, 4, 20, tzinfo=UTC),
                retrieved_at=retrieved_at,
            ),
        ]
    if canonical_id == "p4":
        return [
            _problem(patient_id, "hypertension", "Hypertension is active.", retrieved_at),
            _problem(patient_id, "hyperlipidemia", "Hyperlipidemia is active.", retrieved_at),
            _problem(patient_id, "alcohol use disorder", "Alcohol use disorder is in remission.", retrieved_at),
            _medication(patient_id, "Lisinopril", "Lisinopril 20 mg PO daily.", retrieved_at),
            _medication(patient_id, "Atorvastatin", "Atorvastatin 40 mg QHS.", retrieved_at),
            _allergy(patient_id, "Codeine", "Codeine allergy/intolerance: nausea, mild.", retrieved_at),
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_kowalski_creatinine",
                source_id="demo-kowalski-cmp",
                display_name="Creatinine",
                fact="Creatinine was 1.4 mg/dL on 2026-04-15 (high).",
                effective_at=datetime(2026, 4, 15, tzinfo=UTC),
                retrieved_at=retrieved_at,
            ),
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_kowalski_potassium",
                source_id="demo-kowalski-cmp",
                display_name="Potassium",
                fact="Potassium was 3.3 mmol/L on 2026-04-15 (low).",
                effective_at=datetime(2026, 4, 15, tzinfo=UTC),
                retrieved_at=retrieved_at,
            ),
            _lab(
                patient_id=patient_id,
                evidence_id="ev_demo_kowalski_alt",
                source_id="demo-kowalski-cmp",
                display_name="ALT",
                fact="ALT was 56 U/L on 2026-04-15 (high).",
                effective_at=datetime(2026, 4, 15, tzinfo=UTC),
                retrieved_at=retrieved_at,
            ),
        ]
    return [
        _lab(
            patient_id=patient_id,
            evidence_id="ev_demo_a1c",
            source_id="demo-lab-a1c",
            display_name="Demo A1c",
            fact="Demo A1c was 8.6% on 2026-03-12",
            effective_at=datetime(2026, 3, 12, tzinfo=UTC),
            retrieved_at=retrieved_at,
            source_url="/api/source/demo-lab-a1c",
        )
    ]


def _problem(
    patient_id: str,
    name: str,
    fact: str,
    retrieved_at: datetime,
) -> EvidenceObject:
    source_id = name.replace(" ", "-")
    return EvidenceObject(
        evidence_id=f"ev_demo_{patient_id}_problem_{source_id}",
        patient_id=patient_id,
        source_type="active_problem",
        source_id=source_id,
        display_name=name.title(),
        fact=fact,
        retrieved_at=retrieved_at,
        source_url=f"/api/source/demo-patient/{patient_id}",
    )


def _medication(
    patient_id: str,
    display_name: str,
    fact: str,
    retrieved_at: datetime,
) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=f"ev_demo_{patient_id}_medication_{display_name.lower().replace(' ', '-')}",
        patient_id=patient_id,
        source_type="medication",
        source_id=display_name.lower().replace(" ", "-"),
        display_name=display_name,
        fact=f"Medication request (active): {fact}",
        retrieved_at=retrieved_at,
        source_url=f"/api/source/demo-patient/{patient_id}",
    )


def _allergy(
    patient_id: str,
    display_name: str,
    fact: str,
    retrieved_at: datetime,
) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=f"ev_demo_{patient_id}_allergy_{display_name.lower().replace(' ', '-')}",
        patient_id=patient_id,
        source_type="allergy",
        source_id=display_name.lower().replace(" ", "-"),
        display_name=display_name,
        fact=f"Allergy/intolerance: {fact}",
        retrieved_at=retrieved_at,
        source_url=f"/api/source/demo-patient/{patient_id}",
    )


def _lab(
    *,
    patient_id: str,
    evidence_id: str,
    source_id: str,
    display_name: str,
    fact: str,
    effective_at: datetime,
    retrieved_at: datetime,
    source_url: str | None = None,
) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=evidence_id,
        patient_id=patient_id,
        source_type="lab_result",
        source_id=source_id,
        display_name=display_name,
        fact=fact,
        effective_at=effective_at,
        source_updated_at=effective_at,
        retrieved_at=retrieved_at,
        source_url=source_url or f"/api/source/demo-patient/{patient_id}",
    )
