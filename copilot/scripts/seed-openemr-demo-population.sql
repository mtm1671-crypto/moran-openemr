START TRANSACTION;

CREATE TEMPORARY TABLE af_extra_patients (
    pubpid VARCHAR(32) PRIMARY KEY,
    patient_uuid VARCHAR(36) NOT NULL,
    title VARCHAR(16) NOT NULL,
    fname VARCHAR(64) NOT NULL,
    lname VARCHAR(64) NOT NULL,
    dob DATE NOT NULL,
    sex VARCHAR(16) NOT NULL,
    street VARCHAR(128) NOT NULL,
    postal_code VARCHAR(16) NOT NULL,
    city VARCHAR(64) NOT NULL,
    state VARCHAR(16) NOT NULL,
    phone_home VARCHAR(32) NOT NULL,
    phone_cell VARCHAR(32) NOT NULL,
    email VARCHAR(128) NOT NULL,
    race VARCHAR(64) NOT NULL,
    ethnicity VARCHAR(64) NOT NULL
);

INSERT INTO af_extra_patients VALUES
    ('AF-MVP-004', '2d64b050-6d7e-4d91-8b4a-0efb77c30b01', 'Ms.', 'Rosa', 'Alvarez', '1967-07-11', 'Female', '118 North Ada Street', '60607', 'Chicago', 'IL', '312-555-0404', '312-555-0405', 'rosa.alvarez@example.invalid', 'white', 'hispanic_or_latino'),
    ('AF-MVP-005', 'd2d5ec76-09b4-4a24-9a08-8851cb9b3d05', 'Mr.', 'Daniel', 'Okafor', '1981-03-29', 'Male', '701 East 47th Street', '60653', 'Chicago', 'IL', '312-555-0504', '312-555-0505', 'daniel.okafor@example.invalid', 'black_or_african_american', 'not_hispanic_or_latino'),
    ('AF-MVP-006', 'a10c4b88-4ac7-447f-8cc1-284b3f0e2e06', 'Ms.', 'Mei', 'Tanaka', '1946-10-22', 'Female', '1550 West Devon Avenue', '60660', 'Chicago', 'IL', '312-555-0604', '312-555-0605', 'mei.tanaka@example.invalid', 'asian', 'not_hispanic_or_latino'),
    ('AF-MVP-007', '30a4ca9d-8c9f-4d59-a74d-2f44da5ea207', 'Mr.', 'Andre', 'Williams', '1975-01-16', 'Male', '820 South Wood Street', '60612', 'Chicago', 'IL', '312-555-0704', '312-555-0705', 'andre.williams@example.invalid', 'black_or_african_american', 'not_hispanic_or_latino'),
    ('AF-MVP-008', '1145e8ee-e970-4974-9fa1-59205ef2c908', 'Ms.', 'Nadia', 'Petrova', '1992-05-08', 'Female', '3419 North Clark Street', '60657', 'Chicago', 'IL', '312-555-0804', '312-555-0805', 'nadia.petrova@example.invalid', 'white', 'not_hispanic_or_latino'),
    ('AF-MVP-009', '9936516c-bbea-4ad2-8a97-4484612b8009', 'Mr.', 'Samuel', 'Brooks', '1962-11-30', 'Male', '6200 South University Avenue', '60637', 'Chicago', 'IL', '312-555-0904', '312-555-0905', 'samuel.brooks@example.invalid', 'black_or_african_american', 'not_hispanic_or_latino'),
    ('AF-MVP-010', 'e17872e0-3b75-46f8-a83d-5942b22da010', 'Ms.', 'Leah', 'Kim', '2004-06-12', 'Female', '4801 North Broadway', '60640', 'Chicago', 'IL', '312-555-1004', '312-555-1005', 'leah.kim@example.invalid', 'asian', 'not_hispanic_or_latino'),
    ('AF-MVP-011', '58b3d43d-b4f8-4dbb-acfd-4fd2044f8011', 'Mr.', 'Jamal', 'Price', '1989-09-04', 'Male', '1932 West 21st Place', '60608', 'Chicago', 'IL', '312-555-1104', '312-555-1105', 'jamal.price@example.invalid', 'black_or_african_american', 'not_hispanic_or_latino'),
    ('AF-MVP-012', '59615f4f-ae45-4358-8d48-127c755b8012', 'Mr.', 'Owen', 'Gallagher', '1952-04-19', 'Male', '111 West Adams Street', '60603', 'Chicago', 'IL', '312-555-1204', '312-555-1205', 'owen.gallagher@example.invalid', 'white', 'not_hispanic_or_latino'),
    ('AF-MVP-013', '75d707b6-c1f0-458a-856b-d40802d61013', 'Ms.', 'Aisha', 'Rahman', '1979-08-25', 'Female', '2635 West Devon Avenue', '60659', 'Chicago', 'IL', '312-555-1304', '312-555-1305', 'aisha.rahman@example.invalid', 'asian', 'not_hispanic_or_latino'),
    ('AF-MVP-014', '4b681bde-b22c-40d8-8308-5e0c33787014', 'Mr.', 'Victor', 'Nguyen', '1938-02-14', 'Male', '4420 North Sheridan Road', '60640', 'Chicago', 'IL', '312-555-1404', '312-555-1405', 'victor.nguyen@example.invalid', 'asian', 'not_hispanic_or_latino'),
    ('AF-MVP-015', '1fdb26a7-0152-4ed4-9c32-a9a9e9ad0015', 'Ms.', 'Grace', 'Bennett', '1969-12-09', 'Female', '5301 South Ellis Avenue', '60615', 'Chicago', 'IL', '312-555-1504', '312-555-1505', 'grace.bennett@example.invalid', 'white', 'not_hispanic_or_latino');

CREATE TEMPORARY TABLE af_extra_patient_ids AS
SELECT
    p.pubpid,
    existing.pid AS existing_pid,
    COALESCE(existing.pid, max_pid.value + ROW_NUMBER() OVER (ORDER BY p.pubpid)) AS pid
FROM af_extra_patients p
LEFT JOIN patient_data existing ON existing.pubpid = p.pubpid
CROSS JOIN (SELECT COALESCE(MAX(pid), 0) AS value FROM patient_data) max_pid;

DELETE presult FROM procedure_result presult
INNER JOIN procedure_report preport ON preport.procedure_report_id = presult.procedure_report_id
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
INNER JOIN patient_data pd ON pd.pid = porder.patient_id
INNER JOIN af_extra_patients seed ON seed.pubpid = pd.pubpid
WHERE porder.control_id LIKE CONCAT(seed.pubpid, '-%');

DELETE preport FROM procedure_report preport
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
INNER JOIN patient_data pd ON pd.pid = porder.patient_id
INNER JOIN af_extra_patients seed ON seed.pubpid = pd.pubpid
WHERE porder.control_id LIKE CONCAT(seed.pubpid, '-%');

DELETE poc FROM procedure_order_code poc
INNER JOIN procedure_order porder ON porder.procedure_order_id = poc.procedure_order_id
INNER JOIN patient_data pd ON pd.pid = porder.patient_id
INNER JOIN af_extra_patients seed ON seed.pubpid = pd.pubpid
WHERE porder.control_id LIKE CONCAT(seed.pubpid, '-%');

DELETE porder FROM procedure_order porder
INNER JOIN patient_data pd ON pd.pid = porder.patient_id
INNER JOIN af_extra_patients seed ON seed.pubpid = pd.pubpid
WHERE porder.control_id LIKE CONCAT(seed.pubpid, '-%');

DELETE lm FROM lists_medication lm
INNER JOIN lists l ON l.id = lm.list_id
INNER JOIN patient_data pd ON pd.pid = l.pid
INNER JOIN af_extra_patients seed ON seed.pubpid = pd.pubpid
WHERE l.comments LIKE 'AgentForge MVP seed%';

DELETE l FROM lists l
INNER JOIN patient_data pd ON pd.pid = l.pid
INNER JOIN af_extra_patients seed ON seed.pubpid = pd.pubpid
WHERE l.comments LIKE 'AgentForge MVP seed%';

INSERT INTO patient_data (
    uuid, title, language, financial, fname, lname, mname, DOB, street, postal_code,
    city, state, country_code, drivers_license, ss, phone_home, phone_biz,
    phone_contact, phone_cell, status, contact_relationship, date, sex, referrer,
    referrerID, providerID, email, email_direct, ethnoracial, race, ethnicity,
    religion, interpreter, migrantseasonal, family_size, monthly_income, homeless,
    pubpid, pid, genericname1, genericval1, genericname2, genericval2, hipaa_mail,
    hipaa_voice, hipaa_notice, hipaa_message, hipaa_allowsms, hipaa_allowemail,
    squad, referral_source, usertext1, usertext2, usertext3, usertext4, usertext5,
    usertext6, usertext7, usertext8, userlist1, userlist2, userlist3, userlist4,
    userlist5, userlist6, userlist7, regdate, completed_ad, vfc, mothersname,
    allow_imm_reg_use, allow_imm_info_share, allow_health_info_ex, allow_patient_portal,
    deceased_reason, cmsportal_login, county, created_by, updated_by
)
SELECT
    UNHEX(REPLACE(p.patient_uuid, '-', '')), p.title, 'English', '', p.fname, p.lname, '',
    p.dob, p.street, p.postal_code, p.city, p.state, 'US', '', '',
    p.phone_home, '', '', p.phone_cell, 'active', '', NOW(), p.sex, '', '',
    1, p.email, '', '', p.race, p.ethnicity,
    '', '', '', '', '', '', p.pubpid, ids.pid, '', '', '', '', 'YES', 'YES', 'YES',
    'YES', 'YES', 'NO', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
    '', '', NOW(), 'NO', '', '', '', '', '', 'YES', '', '', 'Cook', 1, 1
FROM af_extra_patients p
INNER JOIN af_extra_patient_ids ids ON ids.pubpid = p.pubpid
WHERE ids.existing_pid IS NULL;

UPDATE patient_data pd
INNER JOIN af_extra_patients p ON p.pubpid = pd.pubpid
SET pd.uuid = UNHEX(REPLACE(p.patient_uuid, '-', '')),
    pd.title = p.title,
    pd.fname = p.fname,
    pd.lname = p.lname,
    pd.DOB = p.dob,
    pd.sex = p.sex,
    pd.street = p.street,
    pd.city = p.city,
    pd.state = p.state,
    pd.postal_code = p.postal_code,
    pd.phone_home = p.phone_home,
    pd.phone_cell = p.phone_cell,
    pd.email = p.email,
    pd.race = p.race,
    pd.ethnicity = p.ethnicity,
    pd.providerID = 1,
    pd.date = NOW(),
    pd.updated_by = 1;

CREATE TEMPORARY TABLE af_extra_problems (
    pubpid VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    begdate DATE NOT NULL,
    diagnosis VARCHAR(64) NOT NULL
);

INSERT INTO af_extra_problems VALUES
    ('AF-MVP-004', 'Moderate persistent asthma', '2012-04-17', 'ICD10:J45.40'),
    ('AF-MVP-004', 'Type 2 diabetes mellitus', '2020-09-02', 'ICD10:E11.9'),
    ('AF-MVP-004', 'Mixed hyperlipidemia', '2019-06-11', 'ICD10:E78.2'),
    ('AF-MVP-005', 'Human immunodeficiency virus disease', '2016-01-20', 'ICD10:B20'),
    ('AF-MVP-005', 'Major depressive disorder', '2021-03-09', 'ICD10:F33.1'),
    ('AF-MVP-005', 'Vitamin D deficiency', '2025-12-18', 'ICD10:E55.9'),
    ('AF-MVP-006', 'Age-related osteoporosis', '2018-02-23', 'ICD10:M81.0'),
    ('AF-MVP-006', 'Primary osteoarthritis of both knees', '2015-07-30', 'ICD10:M17.0'),
    ('AF-MVP-006', 'Recurrent falls', '2025-08-12', 'ICD10:R29.6'),
    ('AF-MVP-007', 'Heart failure with reduced ejection fraction', '2022-10-10', 'ICD10:I50.2'),
    ('AF-MVP-007', 'Obstructive sleep apnea', '2020-05-04', 'ICD10:G47.33'),
    ('AF-MVP-007', 'Class 2 obesity', '2019-03-01', 'ICD10:E66.9'),
    ('AF-MVP-008', 'Hashimoto thyroiditis', '2014-02-12', 'ICD10:E06.3'),
    ('AF-MVP-008', 'Generalized anxiety disorder', '2021-11-18', 'ICD10:F41.1'),
    ('AF-MVP-008', 'Celiac disease', '2018-04-27', 'ICD10:K90.0'),
    ('AF-MVP-009', 'Stage 4 chronic kidney disease', '2023-09-01', 'ICD10:N18.4'),
    ('AF-MVP-009', 'Anemia of chronic disease', '2024-01-12', 'ICD10:D63.8'),
    ('AF-MVP-009', 'Gout', '2019-12-05', 'ICD10:M10.9'),
    ('AF-MVP-010', 'Type 1 diabetes mellitus', '2015-08-14', 'ICD10:E10.9'),
    ('AF-MVP-010', 'Celiac disease', '2019-10-09', 'ICD10:K90.0'),
    ('AF-MVP-010', 'Mild intermittent asthma', '2011-02-03', 'ICD10:J45.20'),
    ('AF-MVP-011', 'Sickle cell disease', '1990-01-15', 'ICD10:D57.1'),
    ('AF-MVP-011', 'Chronic pain syndrome', '2022-07-06', 'ICD10:G89.4'),
    ('AF-MVP-011', 'Mild persistent asthma', '2004-03-21', 'ICD10:J45.30'),
    ('AF-MVP-012', 'Coronary artery disease', '2018-09-19', 'ICD10:I25.10'),
    ('AF-MVP-012', 'Hyperlipidemia', '2016-05-02', 'ICD10:E78.5'),
    ('AF-MVP-012', 'Gastroesophageal reflux disease', '2019-01-28', 'ICD10:K21.9'),
    ('AF-MVP-013', 'Rheumatoid arthritis', '2013-11-06', 'ICD10:M06.9'),
    ('AF-MVP-013', 'Long term immunosuppressive therapy', '2014-01-15', 'ICD10:Z79.899'),
    ('AF-MVP-013', 'Prediabetes', '2025-02-20', 'ICD10:R73.03'),
    ('AF-MVP-014', 'Dementia without behavioral disturbance', '2024-04-03', 'ICD10:F03.90'),
    ('AF-MVP-014', 'Benign prostatic hyperplasia', '2017-09-12', 'ICD10:N40.0'),
    ('AF-MVP-014', 'Chronic constipation', '2021-08-23', 'ICD10:K59.09'),
    ('AF-MVP-015', 'History of breast cancer', '2018-02-05', 'ICD10:Z85.3'),
    ('AF-MVP-015', 'Lymphedema of arm', '2019-05-14', 'ICD10:I89.0'),
    ('AF-MVP-015', 'Peripheral neuropathy', '2020-10-30', 'ICD10:G62.9');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
SELECT UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', pr.title, pr.begdate, 1, pr.diagnosis,
       'AgentForge MVP seed: active problem', pd.pid, 'admin', 'Default', 'confirmed'
FROM af_extra_problems pr
INNER JOIN patient_data pd ON pd.pubpid = pr.pubpid;

CREATE TEMPORARY TABLE af_extra_meds (
    pubpid VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    begdate DATE NOT NULL,
    instructions VARCHAR(255) NOT NULL
);

INSERT INTO af_extra_meds VALUES
    ('AF-MVP-004', 'Atorvastatin 40 mg tablet', '2019-06-11', 'Take 1 tablet by mouth nightly.'),
    ('AF-MVP-004', 'Fluticasone-salmeterol 250-50 mcg inhaler', '2021-02-08', 'Inhale 1 puff twice daily.'),
    ('AF-MVP-005', 'Bictegravir-emtricitabine-tenofovir alafenamide 50-200-25 mg tablet', '2019-05-13', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-005', 'Sertraline 100 mg tablet', '2021-03-09', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-006', 'Alendronate 70 mg tablet', '2018-03-01', 'Take 1 tablet by mouth once weekly.'),
    ('AF-MVP-006', 'Calcium carbonate 600 mg-vitamin D3 800 unit tablet', '2018-03-01', 'Take 1 tablet by mouth twice daily.'),
    ('AF-MVP-007', 'Carvedilol 12.5 mg tablet', '2022-10-10', 'Take 1 tablet by mouth twice daily with meals.'),
    ('AF-MVP-007', 'Furosemide 40 mg tablet', '2022-10-10', 'Take 1 tablet by mouth every morning.'),
    ('AF-MVP-008', 'Levothyroxine 100 mcg tablet', '2014-02-12', 'Take 1 tablet by mouth every morning before breakfast.'),
    ('AF-MVP-008', 'Escitalopram 10 mg tablet', '2021-11-18', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-009', 'Allopurinol 100 mg tablet', '2020-01-05', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-009', 'Sodium bicarbonate 650 mg tablet', '2024-02-01', 'Take 1 tablet by mouth twice daily.'),
    ('AF-MVP-010', 'Insulin glargine 100 unit/mL injection', '2015-08-14', 'Inject 22 units subcutaneously every evening.'),
    ('AF-MVP-010', 'Insulin lispro 100 unit/mL injection', '2015-08-14', 'Use with meals per carbohydrate ratio.'),
    ('AF-MVP-011', 'Hydroxyurea 500 mg capsule', '2018-06-02', 'Take 2 capsules by mouth once daily.'),
    ('AF-MVP-011', 'Folic acid 1 mg tablet', '2010-01-12', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-012', 'Rosuvastatin 20 mg tablet', '2018-09-19', 'Take 1 tablet by mouth nightly.'),
    ('AF-MVP-012', 'Pantoprazole 40 mg tablet', '2019-01-28', 'Take 1 tablet by mouth every morning.'),
    ('AF-MVP-013', 'Methotrexate 2.5 mg tablet', '2014-01-15', 'Take 6 tablets by mouth once weekly.'),
    ('AF-MVP-013', 'Folic acid 1 mg tablet', '2014-01-15', 'Take 1 tablet by mouth once daily except methotrexate day.'),
    ('AF-MVP-014', 'Donepezil 10 mg tablet', '2024-04-03', 'Take 1 tablet by mouth nightly.'),
    ('AF-MVP-014', 'Tamsulosin 0.4 mg capsule', '2017-09-12', 'Take 1 capsule by mouth nightly.'),
    ('AF-MVP-015', 'Anastrozole 1 mg tablet', '2019-02-05', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-015', 'Gabapentin 300 mg capsule', '2020-10-30', 'Take 1 capsule by mouth three times daily.');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
SELECT UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', m.title, m.begdate, 1, '',
       'AgentForge MVP seed: active medication', pd.pid, 'admin', 'Default', 'confirmed'
FROM af_extra_meds m
INNER JOIN patient_data pd ON pd.pubpid = m.pubpid;

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
)
SELECT l.id, m.instructions, 'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
FROM af_extra_meds m
INNER JOIN patient_data pd ON pd.pubpid = m.pubpid
INNER JOIN lists l ON l.pid = pd.pid
    AND l.type = 'medication'
    AND l.title = m.title
    AND l.comments = 'AgentForge MVP seed: active medication';

CREATE TEMPORARY TABLE af_extra_allergies (
    pubpid VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    begdate DATE NOT NULL,
    severity VARCHAR(32) NOT NULL
);

INSERT INTO af_extra_allergies VALUES
    ('AF-MVP-004', 'Aspirin', '2004-04-01', 'moderate'),
    ('AF-MVP-005', 'Shellfish', '2010-06-18', 'moderate'),
    ('AF-MVP-006', 'Codeine', '1999-12-12', 'moderate'),
    ('AF-MVP-007', 'Iodinated contrast media', '2017-08-22', 'severe'),
    ('AF-MVP-008', 'Amoxicillin', '2008-09-06', 'moderate'),
    ('AF-MVP-009', 'Nonsteroidal anti-inflammatory drugs', '2015-11-11', 'moderate'),
    ('AF-MVP-010', 'Peanuts', '2006-03-14', 'severe'),
    ('AF-MVP-011', 'Morphine', '2012-07-20', 'moderate'),
    ('AF-MVP-012', 'Clopidogrel', '2018-09-21', 'moderate'),
    ('AF-MVP-013', 'Doxycycline', '2016-05-17', 'moderate'),
    ('AF-MVP-014', 'Ciprofloxacin', '2019-10-09', 'moderate'),
    ('AF-MVP-015', 'Paclitaxel', '2018-04-12', 'severe');

INSERT INTO lists (
    uuid, date, type, title, begdate, activity, diagnosis, comments,
    pid, user, groupname, reaction, verification, severity_al
)
SELECT UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'allergy', a.title, a.begdate, 1, '',
       'AgentForge MVP seed: active allergy', pd.pid, 'admin', 'Default',
       'unassigned', 'confirmed', a.severity
FROM af_extra_allergies a
INNER JOIN patient_data pd ON pd.pubpid = a.pubpid;

CREATE TEMPORARY TABLE af_extra_lab_panels (
    pubpid VARCHAR(32) PRIMARY KEY,
    collected DATETIME NOT NULL,
    reported DATETIME NOT NULL,
    clinical_hx VARCHAR(255) NOT NULL,
    procedure_code VARCHAR(32) NOT NULL,
    procedure_name VARCHAR(128) NOT NULL,
    order_title VARCHAR(128) NOT NULL,
    specimen_num VARCHAR(64) NOT NULL
);

INSERT INTO af_extra_lab_panels VALUES
    ('AF-MVP-004', '2026-04-21 08:05:00', '2026-04-21 11:25:00', 'Asthma and metabolic follow-up labs', '24323-8', 'Asthma and metabolic laboratory panel', 'Asthma and metabolic follow-up laboratory panel', 'AF-MVP-SPEC-004'),
    ('AF-MVP-005', '2026-04-22 09:15:00', '2026-04-22 12:10:00', 'HIV and mood follow-up labs', '81259-4', 'HIV monitoring laboratory panel', 'HIV monitoring laboratory panel', 'AF-MVP-SPEC-005'),
    ('AF-MVP-006', '2026-04-23 07:40:00', '2026-04-23 10:15:00', 'Falls and osteoporosis follow-up labs', '24323-8', 'Bone health laboratory panel', 'Bone health laboratory panel', 'AF-MVP-SPEC-006'),
    ('AF-MVP-007', '2026-04-24 08:45:00', '2026-04-24 12:05:00', 'Heart failure follow-up labs', '30934-4', 'Heart failure laboratory panel', 'Heart failure laboratory panel', 'AF-MVP-SPEC-007'),
    ('AF-MVP-008', '2026-04-25 08:25:00', '2026-04-25 11:55:00', 'Thyroid and celiac follow-up labs', '3051-0', 'Thyroid and celiac laboratory panel', 'Thyroid and celiac laboratory panel', 'AF-MVP-SPEC-008'),
    ('AF-MVP-009', '2026-04-26 07:35:00', '2026-04-26 10:50:00', 'Kidney disease follow-up labs', '24362-6', 'Kidney disease laboratory panel', 'Kidney disease laboratory panel', 'AF-MVP-SPEC-009'),
    ('AF-MVP-010', '2026-04-20 09:05:00', '2026-04-20 12:45:00', 'Type 1 diabetes follow-up labs', '24323-8', 'Diabetes laboratory panel', 'Type 1 diabetes laboratory panel', 'AF-MVP-SPEC-010'),
    ('AF-MVP-011', '2026-04-19 08:30:00', '2026-04-19 11:30:00', 'Sickle cell follow-up labs', '718-7', 'Sickle cell laboratory panel', 'Sickle cell laboratory panel', 'AF-MVP-SPEC-011'),
    ('AF-MVP-012', '2026-04-18 08:55:00', '2026-04-18 12:20:00', 'Coronary disease follow-up labs', '2085-9', 'Cardiac risk laboratory panel', 'Cardiac risk laboratory panel', 'AF-MVP-SPEC-012'),
    ('AF-MVP-013', '2026-04-17 09:10:00', '2026-04-17 12:40:00', 'Rheumatology monitoring labs', '1988-5', 'Inflammatory marker laboratory panel', 'Rheumatology monitoring laboratory panel', 'AF-MVP-SPEC-013'),
    ('AF-MVP-014', '2026-04-16 07:55:00', '2026-04-16 10:35:00', 'Geriatric safety follow-up labs', '2951-2', 'Geriatric safety laboratory panel', 'Geriatric safety laboratory panel', 'AF-MVP-SPEC-014'),
    ('AF-MVP-015', '2026-04-15 08:35:00', '2026-04-15 11:20:00', 'Oncology survivorship follow-up labs', '6768-6', 'Oncology survivorship laboratory panel', 'Oncology survivorship laboratory panel', 'AF-MVP-SPEC-015');

INSERT INTO procedure_order (
    uuid, provider_id, patient_id, encounter_id, date_collected, date_ordered,
    order_priority, order_status, patient_instructions, activity, control_id,
    lab_id, specimen_type, specimen_location, date_transmitted, clinical_hx,
    procedure_order_type, order_intent, location_id
)
SELECT
    UNHEX(REPLACE(UUID(), '-', '')), 1, pd.pid, 0, p.collected, DATE_SUB(p.collected, INTERVAL 15 MINUTE),
    'routine', 'complete', '', 1, CONCAT(p.pubpid, '-LAB-', DATE_FORMAT(p.collected, '%Y%m%d')),
    0, 'blood', '', DATE_ADD(p.collected, INTERVAL 5 MINUTE), p.clinical_hx,
    'laboratory_test', 'order', 3
FROM af_extra_lab_panels p
INNER JOIN patient_data pd ON pd.pubpid = p.pubpid;

INSERT INTO procedure_order_code (procedure_order_id, procedure_order_seq, procedure_code, procedure_name, procedure_source, procedure_order_title, procedure_type)
SELECT porder.procedure_order_id, 1, panel.procedure_code, panel.procedure_name, '1', panel.order_title, 'laboratory'
FROM af_extra_lab_panels panel
INNER JOIN procedure_order porder ON porder.control_id = CONCAT(panel.pubpid, '-LAB-', DATE_FORMAT(panel.collected, '%Y%m%d'));

INSERT INTO procedure_report (uuid, procedure_order_id, procedure_order_seq, date_collected, date_report, source, specimen_num, report_status, review_status, report_notes)
SELECT UNHEX(REPLACE(UUID(), '-', '')), porder.procedure_order_id, 1, panel.collected, panel.reported, 0,
       panel.specimen_num, 'final', 'reviewed', 'AgentForge MVP seed: expanded demo lab report'
FROM af_extra_lab_panels panel
INNER JOIN procedure_order porder ON porder.control_id = CONCAT(panel.pubpid, '-LAB-', DATE_FORMAT(panel.collected, '%Y%m%d'));

CREATE TEMPORARY TABLE af_extra_lab_results (
    pubpid VARCHAR(32) NOT NULL,
    result_code VARCHAR(32) NOT NULL,
    result_text VARCHAR(160) NOT NULL,
    units VARCHAR(32) NOT NULL,
    result_value VARCHAR(32) NOT NULL,
    ref_range VARCHAR(64) NOT NULL,
    abnormal VARCHAR(32) NOT NULL,
    comments VARCHAR(255) NOT NULL
);

INSERT INTO af_extra_lab_results VALUES
    ('AF-MVP-004', '13457-7', 'Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation', 'mg/dL', '162', '<100', 'high', 'AgentForge MVP seed: LDL above goal'),
    ('AF-MVP-004', '4548-4', 'Hemoglobin A1c/Hemoglobin.total in Blood', '%', '7.4', '4.0-5.6', 'high', 'AgentForge MVP seed: elevated A1c'),
    ('AF-MVP-004', '711-2', 'Eosinophils [#/volume] in Blood by Automated count', '10*3/uL', '0.6', '0.0-0.5', 'high', 'AgentForge MVP seed: mild eosinophilia'),
    ('AF-MVP-005', '20447-9', 'HIV 1 RNA [#/volume] in Serum or Plasma by NAA with probe detection', 'copies/mL', '20', '<20', '', 'AgentForge MVP seed: low-level viral load'),
    ('AF-MVP-005', '8123-2', 'CD4 cells [#/volume] in Blood', 'cells/uL', '640', '500-1500', '', 'AgentForge MVP seed: stable CD4 count'),
    ('AF-MVP-005', '62292-8', '25-Hydroxyvitamin D3 [Mass/volume] in Serum or Plasma', 'ng/mL', '18', '30-100', 'low', 'AgentForge MVP seed: vitamin D low'),
    ('AF-MVP-006', '17861-6', 'Calcium [Mass/volume] in Serum or Plasma', 'mg/dL', '9.1', '8.6-10.2', '', 'AgentForge MVP seed: calcium normal'),
    ('AF-MVP-006', '62292-8', '25-Hydroxyvitamin D3 [Mass/volume] in Serum or Plasma', 'ng/mL', '24', '30-100', 'low', 'AgentForge MVP seed: vitamin D insufficient'),
    ('AF-MVP-006', '718-7', 'Hemoglobin [Mass/volume] in Blood', 'g/dL', '11.2', '12.0-15.5', 'low', 'AgentForge MVP seed: mild anemia'),
    ('AF-MVP-007', '30934-4', 'Natriuretic peptide B [Mass/volume] in Serum or Plasma', 'pg/mL', '788', '<100', 'high', 'AgentForge MVP seed: BNP elevated'),
    ('AF-MVP-007', '2823-3', 'Potassium [Moles/volume] in Serum or Plasma', 'mmol/L', '3.3', '3.5-5.1', 'low', 'AgentForge MVP seed: potassium low'),
    ('AF-MVP-007', '2160-0', 'Creatinine [Mass/volume] in Serum or Plasma', 'mg/dL', '1.42', '0.74-1.35', 'high', 'AgentForge MVP seed: creatinine elevated'),
    ('AF-MVP-008', '3016-3', 'Thyrotropin [Units/volume] in Serum or Plasma', 'uIU/mL', '0.18', '0.4-4.0', 'low', 'AgentForge MVP seed: TSH low'),
    ('AF-MVP-008', '3024-7', 'Thyroxine (T4) free [Mass/volume] in Serum or Plasma', 'ng/dL', '1.8', '0.8-1.7', 'high', 'AgentForge MVP seed: free T4 high'),
    ('AF-MVP-008', '31017-7', 'Tissue transglutaminase IgA Ab [Units/volume] in Serum', 'U/mL', '36', '<15', 'high', 'AgentForge MVP seed: celiac marker elevated'),
    ('AF-MVP-009', '33914-3', 'Glomerular filtration rate/1.73 sq M.predicted', 'mL/min/1.73m2', '24', '>59', 'low', 'AgentForge MVP seed: eGFR low'),
    ('AF-MVP-009', '3084-1', 'Urate [Mass/volume] in Serum or Plasma', 'mg/dL', '9.2', '3.5-7.2', 'high', 'AgentForge MVP seed: uric acid high'),
    ('AF-MVP-009', '718-7', 'Hemoglobin [Mass/volume] in Blood', 'g/dL', '10.1', '13.5-17.5', 'low', 'AgentForge MVP seed: anemia of CKD'),
    ('AF-MVP-010', '4548-4', 'Hemoglobin A1c/Hemoglobin.total in Blood', '%', '9.1', '4.0-5.6', 'high', 'AgentForge MVP seed: A1c above goal'),
    ('AF-MVP-010', '2345-7', 'Glucose [Mass/volume] in Serum or Plasma', 'mg/dL', '268', '70-99', 'high', 'AgentForge MVP seed: hyperglycemia'),
    ('AF-MVP-010', '9318-7', 'Albumin/Creatinine [Mass Ratio] in Urine', 'mg/g', '42', '<30', 'high', 'AgentForge MVP seed: microalbuminuria'),
    ('AF-MVP-011', '718-7', 'Hemoglobin [Mass/volume] in Blood', 'g/dL', '8.4', '13.5-17.5', 'low', 'AgentForge MVP seed: chronic anemia'),
    ('AF-MVP-011', '17849-1', 'Reticulocytes/100 erythrocytes in Blood', '%', '6.8', '0.5-2.5', 'high', 'AgentForge MVP seed: reticulocytosis'),
    ('AF-MVP-011', '1975-2', 'Bilirubin.total [Mass/volume] in Serum or Plasma', 'mg/dL', '2.1', '0.1-1.2', 'high', 'AgentForge MVP seed: bilirubin elevated'),
    ('AF-MVP-012', '13457-7', 'Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation', 'mg/dL', '92', '<100', '', 'AgentForge MVP seed: LDL near goal'),
    ('AF-MVP-012', '30522-7', 'C reactive protein [Mass/volume] in Serum or Plasma by High sensitivity method', 'mg/L', '4.6', '<2.0', 'high', 'AgentForge MVP seed: hsCRP elevated'),
    ('AF-MVP-012', '6598-7', 'Troponin T.cardiac [Mass/volume] in Serum or Plasma', 'ng/mL', '<0.01', '<0.01', '', 'AgentForge MVP seed: troponin negative'),
    ('AF-MVP-013', '1988-5', 'C reactive protein [Mass/volume] in Serum or Plasma', 'mg/L', '18', '<8', 'high', 'AgentForge MVP seed: CRP elevated'),
    ('AF-MVP-013', '4537-7', 'Erythrocyte sedimentation rate by Westergren method', 'mm/hr', '42', '<20', 'high', 'AgentForge MVP seed: ESR elevated'),
    ('AF-MVP-013', '1742-6', 'Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma', 'U/L', '56', '7-45', 'high', 'AgentForge MVP seed: ALT mildly elevated'),
    ('AF-MVP-014', '2951-2', 'Sodium [Moles/volume] in Serum or Plasma', 'mmol/L', '130', '135-145', 'low', 'AgentForge MVP seed: hyponatremia'),
    ('AF-MVP-014', '2132-9', 'Cobalamin (Vitamin B12) [Mass/volume] in Serum or Plasma', 'pg/mL', '260', '200-900', '', 'AgentForge MVP seed: low-normal B12'),
    ('AF-MVP-014', '3016-3', 'Thyrotropin [Units/volume] in Serum or Plasma', 'uIU/mL', '3.2', '0.4-4.0', '', 'AgentForge MVP seed: TSH normal'),
    ('AF-MVP-015', '6875-9', 'Cancer Ag 15-3 [Units/volume] in Serum or Plasma', 'U/mL', '19', '<30', '', 'AgentForge MVP seed: tumor marker normal'),
    ('AF-MVP-015', '6768-6', 'Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma', 'U/L', '142', '44-121', 'high', 'AgentForge MVP seed: alkaline phosphatase elevated'),
    ('AF-MVP-015', '2132-9', 'Cobalamin (Vitamin B12) [Mass/volume] in Serum or Plasma', 'pg/mL', '188', '200-900', 'low', 'AgentForge MVP seed: B12 low');

INSERT INTO procedure_result (uuid, procedure_report_id, result_data_type, result_code, result_text, date, facility, units, result, `range`, abnormal, comments, result_status)
SELECT
    UNHEX(REPLACE(UUID(), '-', '')), preport.procedure_report_id, 'N', r.result_code, r.result_text,
    panel.reported, 'Your Clinic Name Here', r.units, r.result_value, r.ref_range, r.abnormal, r.comments, 'final'
FROM af_extra_lab_results r
INNER JOIN af_extra_lab_panels panel ON panel.pubpid = r.pubpid
INNER JOIN procedure_order porder ON porder.control_id = CONCAT(panel.pubpid, '-LAB-', DATE_FORMAT(panel.collected, '%Y%m%d'))
INNER JOIN procedure_report preport ON preport.procedure_order_id = porder.procedure_order_id;

COMMIT;

SELECT
    pd.pid AS pid,
    LOWER(CONCAT(SUBSTR(HEX(pd.uuid),1,8),'-',SUBSTR(HEX(pd.uuid),9,4),'-',SUBSTR(HEX(pd.uuid),13,4),'-',SUBSTR(HEX(pd.uuid),17,4),'-',SUBSTR(HEX(pd.uuid),21))) AS patient_uuid,
    pd.pubpid,
    pd.fname,
    pd.lname,
    pd.DOB,
    pd.sex,
    (SELECT COUNT(*) FROM lists WHERE pid = pd.pid AND type = 'medical_problem' AND comments LIKE 'AgentForge MVP seed%') AS seeded_problems,
    (SELECT COUNT(*) FROM lists WHERE pid = pd.pid AND type = 'medication' AND comments LIKE 'AgentForge MVP seed%') AS seeded_medications,
    (SELECT COUNT(*) FROM lists WHERE pid = pd.pid AND type = 'allergy' AND comments LIKE 'AgentForge MVP seed%') AS seeded_allergies,
    (
        SELECT COUNT(*)
        FROM procedure_result presult
        INNER JOIN procedure_report preport ON preport.procedure_report_id = presult.procedure_report_id
        INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
        WHERE porder.control_id LIKE CONCAT(pd.pubpid, '-%')
    ) AS seeded_lab_results
FROM patient_data pd
WHERE pd.pubpid IN (
    'AF-MVP-001', 'AF-MVP-002', 'AF-MVP-003', 'AF-MVP-004', 'AF-MVP-005',
    'AF-MVP-006', 'AF-MVP-007', 'AF-MVP-008', 'AF-MVP-009', 'AF-MVP-010',
    'AF-MVP-011', 'AF-MVP-012', 'AF-MVP-013', 'AF-MVP-014', 'AF-MVP-015'
)
ORDER BY pd.pubpid;
