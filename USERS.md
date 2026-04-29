# Clinical Co-Pilot Users and Use Cases

## Summary

The MVP is designed for a primary care clinic workflow where clinicians have very little time to recover patient context between visits. The primary user is a primary care physician with a packed clinic day. The supporting users are nurses and medical assistants who prepare charts and room patients. The current product implementation is a standalone chat-first Clinical Co-Pilot connected to OpenEMR: the user authenticates through OpenEMR SMART/OAuth, role-based access control determines which patients and data categories they can access, the user searches for or selects an authorized patient, and then asks patient-scoped questions in a chat window.

The final clinician experience should live inside OpenEMR as a top-level `Co-Pilot` tab alongside major workflow areas such as Schedule/Calendar. Opening the tab globally should show patient search and today's schedule context. Opening it from a chart or schedule row should carry the selected patient into the Co-Pilot automatically. The assistant can remain a separate Next.js/FastAPI service behind that tab, but the user should experience it as part of the EMR workspace.

The agent is information-only and read-only. It retrieves and summarizes facts from the selected patient's OpenEMR record, but it does not diagnose, recommend treatment, prescribe, draft notes, place orders, or write back to the chart. Every factual claim in the answer must have an inline clickable source label that links back to the underlying OpenEMR record, document, lab result, or source detail view when available.

The MVP should include a standalone patient selector and a lightweight schedule shortcut. The schedule is useful for preloading evidence for common questions, but the chat should also support searching across all patients the current user is authorized to access. The chat is one-patient-at-a-time. Cross-patient comparison and population questions are out of scope.

## Primary User

### Primary Care Physician With a Packed Clinic Day

The primary user is a PCP seeing roughly 18-24 patients in a full clinic day, often with 10-15 minute visits and only 1-2 minutes between rooms. Their immediate problem is not a lack of data; it is that the data is spread across demographics, problem lists, lab results, medications, allergies, prior encounters, and documents. In the moment before entering the room, they need the relevant facts quickly enough to use them.

The physician's tolerance for vague or unsupported output is low. A generic medical answer is not useful. A confident but unsupported patient-specific claim is dangerous. The answer must be short, patient-specific, and source-backed. The physician should be able to click a citation, verify where the fact came from, and ask a follow-up without leaving the workflow.

The physician can access the fullest MVP Co-Pilot data set when OpenEMR permissions allow it:

- Patient demographics and context.
- Active problems and relevant history.
- Recent labs.
- Medications and allergies as secondary context.
- Source-backed follow-up questions.

NPs and PAs have the same Co-Pilot abilities as physicians for MVP when OpenEMR treats them as licensed clinicians for the patient/workflow.

## Supporting Users

### Nurse or Medical Assistant Preparing Charts

Nurses and MAs support the same clinic workflow, but their Co-Pilot access should be more conservative by default. Their main use is chart prep and rooming support: confirming patient identity/context, seeing schedule-related context, surfacing active problem names or summaries when permitted, and checking meds/allergies when OpenEMR permissions allow.

For MVP, supporting users should not receive the same depth of clinical detail as physicians by default. RN/LPN users may access recent labs only when OpenEMR ACL permits. MA users should not see deep lab details by default. This can be relaxed later through explicit site policy and OpenEMR permissions, but not through prompt instructions.

## MVP Workflow

The core moment is the 1-2 minute window between patient rooms.

The user opens the Clinical Co-Pilot from the top-level OpenEMR `Co-Pilot` tab, a patient chart, a schedule entry, or a Co-Pilot launcher. The user is already authenticated through OpenEMR. The chat shows a permission-filtered patient search/selector across patients the user is authorized to access. The user selects one patient, or arrives with a patient already selected from chart/schedule context, then asks either a custom question or one of the common quick questions.

The default answer should be a concise clinical brief: short sections or bullets, factual claims cited inline, and no broad explanation unless the user asks for more. Citation labels should be clickable. While the agent is working, the UI can show status updates such as "Checking demographics," "Checking active problems," "Checking recent labs," and "Verifying sources." It should not show factual answer text until verification is complete.

Under each answer, the agent should show a concise audit trail by default:

- Tools checked.
- Source categories used.
- Verification result.
- Missing or unavailable data.
- Role/access limitations.

This is not hidden chain-of-thought. It is a structured trace summary that helps the user understand what the agent checked and what it did not check.

## Role-Based Abilities

HIPAA does not prescribe an exact permission table by job title. The defensible approach is to use OpenEMR authentication and ACLs as the authority, then add a narrow Co-Pilot role policy so the agent only exposes evidence appropriate to the user's role and task.

| Role | MVP Co-Pilot Abilities |
|---|---|
| Physician | Search/select authorized patients; ask patient-scoped questions; retrieve demographics, active problems/history, recent labs, and secondary meds/allergies. |
| NP/PA | Same as physician when OpenEMR permissions treat the user as a licensed clinician for the patient/workflow. |
| RN/LPN | Search/select authorized patients; retrieve demographics, active problems summary, meds/allergies, and recent labs only when OpenEMR ACL permits. |
| MA | Search/select authorized patients; retrieve demographics, schedule/rooming context, meds/allergies, and active problem names when OpenEMR ACL permits; no deep lab details by default. |
| Admin/Billing | No clinical Co-Pilot access by default in MVP. |

The chat must never rely on a prompt like "I am a doctor" or "I am a nurse." Role, patient access, and data-category access must come from OpenEMR authentication and authorization.

## Draft Quick Questions

The exact labels can change, but the first version should expose no more than five common questions:

1. What should I know before seeing this patient?
2. Summarize active problems and relevant history.
3. Show recent labs and abnormal results.
4. Show the source for this problem or lab result.
5. Show meds and allergies as additional context.

These quick questions should be backed by cached normalized evidence when possible. Cached evidence must be revalidated before answer generation. If freshness cannot be proven, the evidence must be refreshed before the answer is shown.

## Use Cases

### Use Case 1: Pre-Room Patient Context

The physician has just finished one visit and is about to enter the next room. They open the Co-Pilot, select the next patient from an authorized list or launch directly from that patient's schedule/chart row, and ask, "What should I know before seeing this patient?"

The agent returns a concise, cited clinical brief focused on the selected patient. The response should prioritize demographics/context, active problems, and recent labs. Medications and allergies can appear as secondary context after the main problem-focused information.

Why an agent:

The physician's need changes depending on the patient and visit. A static dashboard cannot anticipate every follow-up, and manually scanning the chart is too slow. A patient-scoped agent can answer the first common question quickly, then let the physician ask a more specific follow-up without leaving the chart.

### Use Case 2: Active Problems and Relevant History

The physician asks, "Summarize active problems and relevant history." The agent retrieves the selected patient's active problem evidence from OpenEMR and returns a short list with source labels. It should distinguish supported facts from missing or unavailable information and avoid turning problem-list data into diagnosis or treatment advice.

Why an agent:

Problem lists can be noisy, stale, or incomplete. The agent can present the relevant items in a compact form, preserve source traceability, and let the physician ask follow-ups like "when was this added?" or "show the source." That conversational follow-up is more useful than a static list when the physician has only a minute or two.

### Use Case 3: Recent Labs With Sources

The physician asks for recent labs, especially abnormal results. The agent retrieves recent lab evidence for the selected patient, returns a concise summary, and cites each factual lab claim inline. If the lab data is stale, missing, or unavailable, the agent should say that the result was not found in retrieved records rather than implying the patient does not have the condition or result.

Why an agent:

Lab result views often contain more detail than the physician needs in the moment. The agent can reduce friction by pulling the relevant recent results into a short source-backed brief, while clickable citations preserve the physician's ability to inspect the original record.

### Use Case 4: Source-Backed Follow-Up

The physician asks an uncommon follow-up that was not part of the quick-question set, such as "show the source for that A1c" or "when was this problem first recorded?" The agent uses the current patient context and previous turn references within the same session, retrieves any additional evidence needed, and answers with citations.

Why an agent:

This is the core reason the product is chat-shaped. The first answer creates context, but the next useful question is often specific and unpredictable. A source-backed chat lets the physician ask that question without manually traversing several chart sections.

### Use Case 5: Secondary Meds and Allergies Context

After the main requested information is answered, the physician asks for meds and allergies as additional context. The agent retrieves only the allowed medication and allergy evidence for the selected patient and presents it as secondary information with inline sources.

Why an agent:

Meds and allergies are often clinically important, but they should not crowd every answer. A chat flow lets the physician pull them in when relevant, while preserving a concise default brief.

### Use Case 6: Nurse/MA Chart Prep

A nurse or MA opens the Co-Pilot while preparing a patient for the physician. The user selects an authorized patient and asks for rooming/chart-prep context. The agent can surface demographics, schedule context, meds/allergies, and active problem names or summaries when OpenEMR permissions allow. It should avoid deeper clinical detail, such as lab interpretation, unless permitted by the user's role and site policy.

Why an agent:

Nurses and MAs need a narrower view than physicians, but they still benefit from a quick, source-backed way to confirm what is relevant before the physician enters. The agent can provide that support while respecting role boundaries.

## Demo Scenario

The first demo and eval scenario should use sample/demo data plus a serious synthetic primary-care patient:

- Adult patient presenting for type 2 diabetes and hypertension follow-up.
- Active problems include type 2 diabetes, hypertension, and hyperlipidemia.
- Recent labs include A1c, creatinine/eGFR, lipid panel, and optionally urine microalbumin.
- The agent answers information-only questions about patient context, active problems, and recent labs.
- The agent does not provide diagnosis, treatment recommendations, prescribing advice, dosage changes, or chart writes.

## Explicit Non-Goals

- Diagnose the patient.
- Recommend treatments.
- Prescribe medications or suggest dosages.
- Write back to the chart.
- Draft notes, orders, or chart updates.
- Replace physician judgment.
- Answer general medical questions disconnected from the selected patient record.
- Compare multiple patients or answer population-style questions in the chat.
- Persist raw unencrypted chat history or retain chat history beyond the configured retention window by default.

When refusing, the agent should be brief and redirect to allowed information retrieval. Example: "I can't recommend treatment or medication changes. I can show the patient's active problems, recent labs, and current meds with sources."

## Conversation Scope and Retention

Visible chat history is available in the Co-Pilot during the configured retention window. For MVP, conversations are retained for 30 days by default, with prompt text and answer payloads encrypted. The system should persist queryable metadata separately for audit and observability, but should not store raw unencrypted prompts or responses.

Multi-turn behavior is allowed only within the selected patient and current conversation. If the user changes patients, the chat context resets so references like "those labs" cannot accidentally carry over to another patient.

The chat answers for one selected patient at a time. Cross-patient comparisons and population-style questions are out of scope for MVP.

## Future Users

Possible later users, not MVP targets:

- Care coordinator.
- Specialist.
- Clinic manager.
- Patient-facing portal user.
