SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;

START TRANSACTION;

CREATE TEMPORARY TABLE af_demo_note_patients (
    pubpid VARCHAR(32) PRIMARY KEY
);

INSERT INTO af_demo_note_patients VALUES
    ('AF-MVP-001'),
    ('AF-MVP-002'),
    ('AF-MVP-003'),
    ('AF-MVP-004'),
    ('AF-MVP-005'),
    ('AF-MVP-006'),
    ('AF-MVP-007'),
    ('AF-MVP-008'),
    ('AF-MVP-009'),
    ('AF-MVP-010'),
    ('AF-MVP-011'),
    ('AF-MVP-012'),
    ('AF-MVP-013'),
    ('AF-MVP-014'),
    ('AF-MVP-015');

DELETE fcn FROM form_clinical_notes fcn
INNER JOIN patient_data pd ON pd.pid = fcn.pid
INNER JOIN af_demo_note_patients seed ON seed.pubpid = pd.pubpid
WHERE fcn.description LIKE 'AgentForge MVP seed note:%';

DELETE f FROM forms f
INNER JOIN patient_data pd ON pd.pid = f.pid
INNER JOIN af_demo_note_patients seed ON seed.pubpid = pd.pubpid
WHERE f.formdir = 'clinical_notes'
  AND f.form_name = 'AgentForge MVP Seed Clinical Note';

DELETE fe FROM form_encounter fe
INNER JOIN patient_data pd ON pd.pid = fe.pid
INNER JOIN af_demo_note_patients seed ON seed.pubpid = pd.pubpid
WHERE fe.reason LIKE 'AgentForge MVP seed note encounter:%';

CREATE TEMPORARY TABLE af_demo_note_content (
    pubpid VARCHAR(32) NOT NULL,
    note_seq INT NOT NULL,
    note_datetime DATETIME NOT NULL,
    code VARCHAR(32) NOT NULL,
    codetext VARCHAR(80) NOT NULL,
    description TEXT NOT NULL
);

INSERT INTO af_demo_note_content VALUES
    ('AF-MVP-001', 1, '2026-04-24 14:20:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Diabetes follow-up. Subjective: Elena reports taking metformin with dinner and breakfast most days. Home glucose log shows fasting readings mostly 150-180. Assessment: A1c remains above goal with stable stage 3a kidney disease. Plan discussed in visit: review diet pattern, confirm medication adherence, and repeat kidney function monitoring. Safety: no hypoglycemia reported.'),
    ('AF-MVP-001', 2, '2026-04-26 09:35:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Care coordination call. Elena confirmed she picked up refills and understands to bring glucose meter to next appointment. She asked about low salt meal options and was given clinic education handout. No chest pain, dyspnea, or foot wound symptoms reported during call.'),
    ('AF-MVP-002', 1, '2026-04-25 15:05:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Metabolic follow-up. Subjective: Margaret reports daytime fatigue and mild chest tightness when walking uphill for three weeks. She takes metformin most days but sometimes misses the evening dose when shelving books late at school. Exam narrative: no resting dyspnea, regular rhythm, no leg edema. Assessment: type 2 diabetes, hypertension, and hyperlipidemia require source-backed lab review before next follow-up. Plan discussed in visit: review scanned lipid panel and home blood pressure log.'),
    ('AF-MVP-002', 2, '2026-04-27 10:15:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Post-visit outreach. Margaret confirmed she completed the lipid panel at Pacific Diagnostics and asked whether the clinic received the scanned report. She denies chest pressure at rest, syncope, or new shortness of breath. She was reminded to bring home blood pressure readings and medication bottles to follow-up.'),
    ('AF-MVP-003', 1, '2026-04-26 13:45:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Anemia and thyroid follow-up. Priya reports fatigue over the last month but denies syncope or heavy bleeding. Labs reviewed in visit show low hemoglobin and low ferritin with mildly elevated TSH. Assessment: iron deficiency anemia and hypothyroidism require close follow-up. Plan discussed in visit: medication adherence review and repeat labs after interval.'),
    ('AF-MVP-003', 2, '2026-04-28 08:55:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Phone check after lab review. Priya started daily iron with food and understands separation from levothyroxine. She reports mild constipation and was advised on hydration and fiber education materials. No dizziness, chest pain, or black stools reported.'),
    ('AF-MVP-004', 1, '2026-04-21 14:10:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Asthma and metabolic follow-up. Rosa reports nighttime cough twice this month and inconsistent controller inhaler use during travel. Labs show elevated LDL and A1c. Assessment: asthma symptoms are present but no acute distress; diabetes and hyperlipidemia need ongoing monitoring. Plan discussed in visit: inhaler technique review and adherence barriers.'),
    ('AF-MVP-004', 2, '2026-04-23 11:40:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Nurse teaching. Rosa demonstrated inhaler technique after coaching and identified a refill timing issue with the pharmacy. She was given a spacer and asked to track rescue inhaler use. No wheezing heard during phone follow-up.'),
    ('AF-MVP-005', 1, '2026-04-22 14:30:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: HIV and mood follow-up. Daniel reports taking antiretroviral therapy daily and denies missed doses in the last month. Mood is improved with sertraline but sleep remains fragmented. Assessment: HIV control appears stable by available labs; depression symptoms improving. Plan discussed in visit: continue adherence supports and review sleep hygiene.'),
    ('AF-MVP-005', 2, '2026-04-24 09:25:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Care management note. Daniel confirmed medication delivery arrived and requested evening appointment reminders by text. He denies fever, rash, or new neurologic symptoms. Vitamin D education handout sent through portal.'),
    ('AF-MVP-006', 1, '2026-04-23 13:20:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Falls and osteoporosis follow-up. Mei reports two near falls at home when rising quickly from a chair. She uses a cane outdoors but not inside the apartment. Assessment: recurrent falls with osteoporosis increases injury risk. Plan discussed in visit: home safety review, physical therapy referral discussion, and vitamin D adherence check.'),
    ('AF-MVP-006', 2, '2026-04-25 10:05:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Safety outreach. Mei confirmed throw rugs were removed from hallway and daughter will install a night light. She reports knee pain after stairs but no fall since visit. Medication list reviewed for weekly alendronate timing.'),
    ('AF-MVP-007', 1, '2026-04-24 14:55:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Heart failure follow-up. Andre reports orthopnea improved compared with last visit but still sleeps on two pillows. Lab narrative includes elevated BNP and low potassium. Assessment: heart failure symptoms need close monitoring. Plan discussed in visit: review daily weight records, diet sodium sources, and medication adherence.'),
    ('AF-MVP-007', 2, '2026-04-26 09:10:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Telephone follow-up. Andre reports weight down one pound and no new dyspnea. He found several high sodium frozen meals at home and agreed to bring labels to next visit. CPAP mask discomfort remains a barrier.'),
    ('AF-MVP-008', 1, '2026-04-25 15:10:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Thyroid and celiac follow-up. Nadia reports palpitations when anxious and recent loose stools after restaurant meals. Labs show suppressed TSH, elevated free T4, and elevated tissue transglutaminase IgA. Assessment: thyroid dosing and gluten exposure need review. Plan discussed in visit: medication timing, diet history, and symptom diary.'),
    ('AF-MVP-008', 2, '2026-04-27 08:45:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Portal message follow-up. Nadia identified a supplement containing biotin and was instructed to document use before future thyroid labs. She requested a dietitian visit for gluten-free planning. No severe abdominal pain or syncope reported.'),
    ('AF-MVP-009', 1, '2026-04-26 13:05:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Kidney disease follow-up. Samuel reports fatigue and intermittent gout pain in the right great toe. Labs show eGFR 24, anemia, and high uric acid. Assessment: stage 4 chronic kidney disease with anemia and gout history. Plan discussed in visit: renal diet education, medication reconciliation, and nephrology follow-up status.'),
    ('AF-MVP-009', 2, '2026-04-28 10:30:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Care coordination. Samuel confirmed nephrology appointment date and understands to avoid over-the-counter NSAIDs because of kidney disease. He reports toe pain improving and no fever. Transportation assistance information provided.'),
    ('AF-MVP-010', 1, '2026-04-20 14:15:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Type 1 diabetes follow-up. Leah reports several missed mealtime insulin doses during exams and wide glucose variability. Labs show A1c 9.1 and microalbuminuria. Assessment: hyperglycemia pattern appears related to missed bolus doses and schedule disruption. Plan discussed in visit: diabetes education refresh and school schedule planning.'),
    ('AF-MVP-010', 2, '2026-04-22 09:50:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Diabetes educator note. Leah set phone reminders for lunch insulin and agreed to upload glucose readings before the next visit. She denies severe hypoglycemia. Gluten-free snack options discussed because of celiac disease.'),
    ('AF-MVP-011', 1, '2026-04-19 13:35:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Sickle cell follow-up. Jamal reports chronic leg and back pain at baseline and no emergency visits this month. Labs show chronic anemia and elevated reticulocyte count. Assessment: sickle cell disease with chronic pain syndrome and asthma history. Plan discussed in visit: hydration, trigger avoidance, and review of hydroxyurea adherence.'),
    ('AF-MVP-011', 2, '2026-04-21 10:20:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Pain check call. Jamal reports pain controlled with current non-opioid routine and heat therapy today. He denies chest pain, fever, or new shortness of breath. Inhaler refill status confirmed with pharmacy.'),
    ('AF-MVP-012', 1, '2026-04-18 14:40:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Coronary disease follow-up. Owen denies exertional chest pain and reports walking six blocks most days. Labs show LDL near goal and hsCRP elevated with negative troponin. Assessment: coronary artery disease clinically stable by symptom report. Plan discussed in visit: continue risk factor monitoring and review reflux triggers.'),
    ('AF-MVP-012', 2, '2026-04-20 11:00:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Follow-up call. Owen confirmed no chest pressure since appointment and understands emergency precautions. He asked whether coffee worsens reflux; education materials on GERD triggers were sent. Medication refill dates reviewed.'),
    ('AF-MVP-013', 1, '2026-04-17 15:25:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Rheumatology monitoring follow-up. Aisha reports morning stiffness lasting about one hour and swelling in small joints. Labs show elevated CRP and ESR with mild ALT elevation. Assessment: rheumatoid arthritis symptoms active with immunosuppressive therapy monitoring needs. Plan discussed in visit: review methotrexate timing and infection precautions.'),
    ('AF-MVP-013', 2, '2026-04-19 09:35:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Medication safety call. Aisha confirmed folic acid use except on methotrexate day and denies mouth sores or fever. She reported missing one dose during travel. Lab monitoring appointment reminder sent.'),
    ('AF-MVP-014', 1, '2026-04-16 13:15:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Geriatric safety follow-up. Victor presents with daughter, who reports increased forgetfulness with bills and medication setup. Labs show hyponatremia and low-normal B12. Assessment: dementia with safety concerns and chronic constipation. Plan discussed in visit: caregiver support, medication box review, and bowel routine tracking.'),
    ('AF-MVP-014', 2, '2026-04-18 10:45:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Caregiver outreach. Victor daughter confirmed pill organizer is filled weekly and no falls occurred since visit. She requested information about advance care planning forms. Constipation diary started.'),
    ('AF-MVP-015', 1, '2026-04-15 14:05:00', 'LOINC:11506-3', 'Progress Note',
     'AgentForge MVP seed note: Oncology survivorship follow-up. Grace reports persistent left arm swelling and neuropathy symptoms in both feet. Labs show normal CA 15-3 with elevated alkaline phosphatase and low B12. Assessment: history of breast cancer with lymphedema and neuropathy symptoms. Plan discussed in visit: survivorship monitoring and symptom tracking.'),
    ('AF-MVP-015', 2, '2026-04-17 09:15:00', 'LOINC:34746-8', 'Nurse Note',
     'AgentForge MVP seed note: Survivorship care call. Grace reports compression sleeve helps arm swelling during the day but is uncomfortable by evening. She denies new breast mass, fever, or acute weakness. Physical therapy contact information resent.'),
    ('AF-MVP-001', 3, '2026-04-28 16:40:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Elena. She wrote that fasting glucose was 172 Monday, 165 Tuesday, and 181 Wednesday after a weekend family event with higher carbohydrate meals. She is worried the numbers will delay dental work. She reports walking 20 minutes after dinner twice this week and asks whether the clinic can review meter upload before the next visit. No dizziness, shakiness, or readings below 90 were reported.'),
    ('AF-MVP-001', 4, '2026-04-30 08:25:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Care management narrative. Elena works early shifts and often eats breakfast in the car, which makes the morning metformin dose easier to miss. She keeps pills in the kitchen but not in her work bag. She prefers text reminders and Spanish language nutrition handouts for her mother, who cooks several shared meals. Main barriers documented today are medication routine, meal timing, and cost of glucose strips.'),
    ('AF-MVP-002', 3, '2026-04-29 17:05:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Margaret. She reports the scanned lab report shows LDL cholesterol was high and asks whether the result is already in the chart. Home blood pressures were 138/84, 142/86, and 136/82 over three mornings. She denies severe chest pain, fainting, or readings below 90 glucose.'),
    ('AF-MVP-002', 4, '2026-04-30 09:10:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Medication routine care coordination. Margaret works as a public-school librarian and often misses the evening metformin dose during late library events. She stores atorvastatin by the bedside but metformin in the kitchen. She prefers phone calendar reminders and wants a one-page summary of lipid results after the scanned panel is reviewed.'),
    ('AF-MVP-003', 3, '2026-04-29 12:05:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Priya. She reports constipation after starting iron and skipped two doses because of stomach upset. Fatigue is worse by late afternoon, especially on workdays with back to back meetings. She denies heavy menstrual bleeding, syncope, chest pain, or black stools. She asks whether taking iron with orange juice and moving levothyroxine earlier would help the schedule.'),
    ('AF-MVP-003', 4, '2026-04-30 13:35:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Medication timing review. Priya described taking levothyroxine with coffee some mornings and iron at lunch when she remembers. Education documented: separate iron from levothyroxine and calcium containing foods. She prefers a written schedule and requested migraine trigger tracking because headaches increased during the same month as fatigue. No neurologic warning symptoms reported.'),
    ('AF-MVP-004', 3, '2026-04-24 16:15:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Rosa. She reports rescue inhaler use on three evenings after cleaning a dusty storage room. She lost the paper asthma action plan during travel and asks for another copy. Peak flow at home was 310, which she says is lower than usual. She denies fever, purulent sputum, chest pain, or severe shortness of breath.'),
    ('AF-MVP-004', 4, '2026-04-29 08:20:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Asthma barrier note. Rosa is sharing one car with her spouse and missed pharmacy pickup twice. She can afford the controller inhaler this month but wants synchronization with atorvastatin refill. Home environment review identified dust exposure from stored blankets and a new scented candle. She agreed to remove the candle and wash bedding before the next symptom check.'),
    ('AF-MVP-005', 3, '2026-04-25 15:45:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Daniel. He reports no missed antiretroviral doses but has been taking sertraline at inconsistent times because of rotating shifts. Sleep log shows bedtime ranging from 10 PM to 2 AM. He denies fever, rash, night sweats, suicidal thoughts, or new sexual exposure concerns. He asks whether vitamin D can be taken with his evening meal.'),
    ('AF-MVP-005', 4, '2026-04-28 11:30:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Adherence support note. Daniel keeps HIV medication in a locked drawer and uses a weekly pill box filled Sunday night. Main barrier is shift work and missed meal breaks. He requested discreet appointment reminders without diagnosis text. Case manager documented stable housing, active insurance, and need for evening lab appointments when available.'),
    ('AF-MVP-006', 3, '2026-04-27 14:55:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Mei daughter. She reports Mei felt unsteady after standing from the couch and held the wall for balance. No fall, head injury, or loss of consciousness occurred. Mei has been skipping cane use inside because the apartment is small. Daughter asks for a printed home exercise handout and whether medication timing could contribute to lightheadedness.'),
    ('AF-MVP-006', 4, '2026-04-29 10:10:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Falls risk care note. Home safety checklist reviewed by phone: hallway rug removed, bathroom grab bar pending, night light installed near bedroom. Mei reports knee stiffness after stairs and uses acetaminophen occasionally. Weekly alendronate routine is Sunday morning with water, but she sometimes eats breakfast within 20 minutes. Physical therapy scheduling is pending daughter work availability.'),
    ('AF-MVP-007', 3, '2026-04-28 16:05:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Andre. He uploaded daily weights: 286, 286, 287, and 289 pounds. He noticed more ankle tightness after eating takeout soup twice. He denies chest pain, syncope, or resting shortness of breath. CPAP mask still leaks around the nose and he removes it after about three hours. He asks if the dietitian can review low sodium frozen meal options.'),
    ('AF-MVP-007', 4, '2026-04-30 12:00:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Heart failure coaching note. Andre keeps furosemide near the coffee maker and reports no missed morning doses this week. Food label review showed several meals above 900 mg sodium. He was able to identify lower sodium alternatives during coaching. Sleep equipment vendor was contacted about mask refit. Follow-up call planned after three more days of weights.'),
    ('AF-MVP-008', 3, '2026-04-29 09:40:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Nadia. She reports palpitations mostly after morning coffee and during presentations at work. She has been taking levothyroxine with a hair and nail supplement that contains biotin. Loose stools occur after restaurant meals when gluten exposure is uncertain. She denies fainting, severe abdominal pain, blood in stool, or weight loss.'),
    ('AF-MVP-008', 4, '2026-04-30 15:15:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Thyroid and diet coordination. Nadia agreed to pause biotin before future thyroid labs if clinician confirms timing. Dietitian referral was queued for gluten-free meal planning and cross contamination education. Anxiety coping worksheet sent through portal. She wants lab result explanations written in plain language because multiple abnormal thyroid markers caused worry.'),
    ('AF-MVP-009', 3, '2026-04-29 13:25:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Samuel. He reports right great toe pain improved from 7 of 10 to 3 of 10 after rest and hydration. He almost took ibuprofen from an old bottle but remembered the kidney warning from the nurse call. He denies fever, spreading redness, decreased urine, or shortness of breath. He asks for a renal diet grocery list that includes affordable foods.'),
    ('AF-MVP-009', 4, '2026-04-30 10:55:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Kidney care coordination. Samuel lives alone and receives grocery help from his nephew every other Saturday. He has difficulty reading small medication labels and requested large print instructions. Nephrology visit is scheduled for 2026-05-08. Medication reconciliation found an old naproxen bottle at home; patient agreed to discard it and call before using over the counter pain medicines.'),
    ('AF-MVP-010', 3, '2026-04-23 18:30:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Leah. She reports missed lunch bolus insulin on two exam days because she left supplies in her dorm room. Continuous glucose readings were often above 240 after cafeteria meals. She denies vomiting, abdominal pain, or large ketones. She asks for help building a small diabetes kit that can stay in her backpack and gluten-free snack ideas.'),
    ('AF-MVP-010', 4, '2026-04-29 16:10:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Diabetes education note. Leah created a backpack checklist with meter, rapid insulin, pen needles, glucose tabs, and gluten-free snack. She prefers app reminders instead of texts. School schedule includes long lab sessions on Tuesday and Thursday, which coincide with missed mealtime dosing. She agreed to upload glucose data Sunday night before the next educator review.'),
    ('AF-MVP-011', 3, '2026-04-23 12:45:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Jamal. He reports pain flare after cold weather and standing at work, now back to baseline. Hydration was low during a double shift. He denies fever, chest pain, new shortness of breath, weakness, or priapism. He asks for a work note explaining need for water access and brief rest periods during pain flares.'),
    ('AF-MVP-011', 4, '2026-04-29 11:25:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Sickle cell support note. Jamal tracks pain triggers in a phone note and identified cold exposure, dehydration, and missed meals. Hydroxyurea refill picked up 2026-04-24. He has a spacer for asthma inhaler but keeps it at home, not work. Nurse reviewed urgent symptoms requiring same day evaluation and sent hydration planning worksheet.'),
    ('AF-MVP-012', 3, '2026-04-22 09:05:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Owen. He walked eight blocks without chest discomfort but had burning epigastric pain after a late spicy dinner. Symptoms improved with sitting upright. He denies exertional chest pressure, diaphoresis, jaw pain, or shortness of breath. He asks whether taking pantoprazole before breakfast instead of after coffee would help reflux control.'),
    ('AF-MVP-012', 4, '2026-04-28 14:35:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Cardiac risk coaching note. Owen keeps a walking log and averages 35 minutes most days. He understands emergency precautions for chest pain. Medication review found rosuvastatin taken at bedtime consistently. Reflux triggers include late meals, coffee before breakfast, and peppermint candies. Education sent on separating reflux symptoms from exertional warning symptoms.'),
    ('AF-MVP-013', 3, '2026-04-22 15:50:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Aisha. She reports hand stiffness lasting 70 to 90 minutes on rainy mornings and swelling around the second and third MCP joints. She missed methotrexate last week while traveling. She denies fever, cough, mouth sores, jaundice, or severe abdominal pain. She asks if lab monitoring can be scheduled early morning before work.'),
    ('AF-MVP-013', 4, '2026-04-30 09:45:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Rheumatology monitoring note. Aisha keeps methotrexate in a weekly organizer but travel disrupted routine. She uses a phone calendar reminder and requested backup reminder from spouse. Infection precautions reviewed because she works in a school. Lab appointment moved to 7:30 AM. She understands to report fever, mouth ulcers, or worsening fatigue.'),
    ('AF-MVP-014', 3, '2026-04-21 16:20:00', 'LOINC:34109-9', 'Caregiver Message',
     'AgentForge MVP seed note: Portal message from Victor daughter. She reports Victor paid the same utility bill twice and forgot whether he took evening medication. No wandering, stove incident, or fall occurred. He resists using the pill organizer because he says it makes him feel dependent. Daughter asks for social work resources and a simple medication checklist that Victor can mark himself.'),
    ('AF-MVP-014', 4, '2026-04-29 13:10:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Geriatric care coordination. Victor and daughter agreed to place the pill organizer in a kitchen drawer rather than on the counter. Constipation diary shows bowel movements every three to four days with low fluid intake. Daughter requested advance care planning forms by mail. Safety review documented no firearms in home and daughter checks in every evening by phone.'),
    ('AF-MVP-015', 3, '2026-04-22 10:50:00', 'LOINC:34109-9', 'Patient Message',
     'AgentForge MVP seed note: Portal message from Grace. She reports left arm swelling increases after gardening and improves overnight with elevation. Neuropathy feels like burning in both feet after long walks. She denies new breast lump, skin redness, fever, new back pain, or acute weakness. She asks if physical therapy can teach sleeve fitting and safe upper body exercises.'),
    ('AF-MVP-015', 4, '2026-04-30 11:05:00', 'LOINC:34746-8', 'Care Management Note',
     'AgentForge MVP seed note: Survivorship navigation note. Grace has compression sleeve but needs replacement because elasticity is reduced. Physical therapy referral was resent with lymphedema focus. She tracks neuropathy symptoms in a notebook and reports gabapentin helps sleep but causes morning grogginess. Oncology survivorship summary was requested for the next primary care visit.');

CREATE TEMPORARY TABLE af_demo_note_rows AS
SELECT
    c.*,
    pd.pid,
    ROW_NUMBER() OVER (ORDER BY c.pubpid, c.note_seq) AS seed_row
FROM af_demo_note_content c
INNER JOIN patient_data pd ON pd.pubpid = c.pubpid;

CREATE TEMPORARY TABLE af_demo_note_assigned AS
SELECT
    r.*,
    encounter_base.value + r.seed_row AS encounter_id,
    form_base.value + r.seed_row AS form_id
FROM af_demo_note_rows r
CROSS JOIN (SELECT COALESCE(MAX(encounter), 0) AS value FROM form_encounter) encounter_base
CROSS JOIN (SELECT COALESCE(MAX(form_id), 0) AS value FROM form_clinical_notes) form_base;

INSERT INTO form_encounter (
    uuid, date, reason, facility, facility_id, pid, encounter, onset_date, sensitivity,
    billing_note, pc_catid, provider_id, supervisor_id, billing_facility, external_id,
    class_code, encounter_type_code, encounter_type_description, referring_provider_id,
    date_end, ordering_provider_id
)
SELECT
    UNHEX(REPLACE(UUID(), '-', '')),
    note_datetime,
    CONCAT('AgentForge MVP seed note encounter: ', pubpid, '-', LPAD(note_seq, 2, '0')),
    'Your Clinic Name Here',
    3,
    pid,
    encounter_id,
    note_datetime,
    'normal',
    'AgentForge MVP synthetic clinical note encounter',
    5,
    1,
    0,
    3,
    CONCAT(pubpid, '-NOTE-', LPAD(note_seq, 2, '0')),
    'AMB',
    'AMB',
    'Ambulatory clinical note seed encounter',
    0,
    DATE_ADD(note_datetime, INTERVAL 20 MINUTE),
    1
FROM af_demo_note_assigned;

INSERT INTO forms (
    date, encounter, form_name, form_id, pid, user, groupname, authorized,
    deleted, formdir, therapy_group_id, issue_id, provider_id
)
SELECT
    note_datetime,
    encounter_id,
    'AgentForge MVP Seed Clinical Note',
    form_id,
    pid,
    'admin',
    'Default',
    1,
    0,
    'clinical_notes',
    NULL,
    0,
    1
FROM af_demo_note_assigned;

INSERT INTO form_clinical_notes (
    form_id, uuid, date, pid, encounter, user, groupname, authorized, activity,
    code, codetext, description, external_id, clinical_notes_type,
    clinical_notes_category, note_related_to
)
SELECT
    form_id,
    UNHEX(REPLACE(UUID(), '-', '')),
    DATE(note_datetime),
    pid,
    encounter_id,
    'admin',
    'Default',
    1,
    1,
    code,
    codetext,
    description,
    CONCAT(pubpid, '-NOTE-', LPAD(note_seq, 2, '0')),
    NULL,
    NULL,
    NULL
FROM af_demo_note_assigned;

COMMIT;

SELECT
    pd.pubpid,
    pd.fname,
    pd.lname,
    COUNT(fcn.id) AS seeded_clinical_notes
FROM patient_data pd
LEFT JOIN form_clinical_notes fcn ON fcn.pid = pd.pid
    AND fcn.description LIKE 'AgentForge MVP seed note:%'
WHERE pd.pubpid IN (
    'AF-MVP-001', 'AF-MVP-002', 'AF-MVP-003', 'AF-MVP-004', 'AF-MVP-005',
    'AF-MVP-006', 'AF-MVP-007', 'AF-MVP-008', 'AF-MVP-009', 'AF-MVP-010',
    'AF-MVP-011', 'AF-MVP-012', 'AF-MVP-013', 'AF-MVP-014', 'AF-MVP-015'
)
GROUP BY pd.pubpid, pd.fname, pd.lname
ORDER BY pd.pubpid;
