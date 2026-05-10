SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;

START TRANSACTION;

CREATE TEMPORARY TABLE af_profile_patients (
    pubpid VARCHAR(32) PRIMARY KEY,
    patient_uuid VARCHAR(36) NOT NULL,
    title VARCHAR(16) NOT NULL,
    fname VARCHAR(64) NOT NULL,
    lname VARCHAR(64) NOT NULL,
    mname VARCHAR(64) NOT NULL,
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

INSERT INTO af_profile_patients VALUES
    ('AF-W2-001', '0f5c8cf1-0a22-4b70-9e83-3275d67cd901', 'Ms.', 'Demo', 'Patient', '', '1975-04-12', 'Female', '415 Cedar Avenue', '60611', 'Chicago', 'IL', '312-555-0179', '312-555-0180', 'demo.patient@example.invalid', 'white', 'not_hispanic_or_latino'),
    ('AF-MVP-002', '5b8f4d2a-5e0a-4a7d-91f6-e507321f6d02', 'Ms.', 'Margaret', 'Chen', 'L', '1967-08-14', 'Female', '4421 Magnolia Ave, Apt 3B', '94705', 'Berkeley', 'CA', '510-555-0148', '510-555-0148', 'mchen.demo@example.test', 'asian', 'not_hispanic_or_latino'),
    ('AF-W2-002', '19d0e928-5953-474e-b8ee-0f50b731a662', 'Mr.', 'James', 'Whitaker', '', '1958-11-03', 'Male', '8816 SE Division St', '97266', 'Portland', 'OR', '503-555-0188', '503-555-0188', 'jwhitaker.demo@example.test', 'white', 'not_hispanic_or_latino'),
    ('AF-W2-003', '6c3ef6a6-7b81-4e4d-bb76-92f5dcf72103', 'Ms.', 'Sofia', 'Reyes', 'M', '1983-12-19', 'Female', '1124 South Lamar Blvd, Apt 218', '78704', 'Austin', 'TX', '512-555-0177', '512-555-0177', 'sreyes.demo@example.test', 'white', 'hispanic_or_latino'),
    ('AF-W2-004', '8b08c918-a991-41d8-82ce-6c0c98dbdb58', 'Mr.', 'Robert', 'Kowalski', 'J', '1971-06-08', 'Male', '2811 N Halsted St', '60614', 'Chicago', 'IL', '312-555-0142', '312-555-0142', 'rkowalski.demo@example.test', 'white', 'not_hispanic_or_latino');

CREATE TEMPORARY TABLE af_profile_patient_ids AS
SELECT
    p.pubpid,
    existing.pid AS existing_pid,
    COALESCE(existing.pid, max_pid.value + ROW_NUMBER() OVER (ORDER BY p.pubpid)) AS pid
FROM af_profile_patients p
LEFT JOIN patient_data existing ON existing.pubpid = p.pubpid
CROSS JOIN (SELECT COALESCE(MAX(pid), 0) AS value FROM patient_data) max_pid;

DELETE lm FROM lists_medication lm
INNER JOIN lists l ON l.id = lm.list_id
INNER JOIN patient_data pd ON pd.pid = l.pid
INNER JOIN af_profile_patients seed ON seed.pubpid = pd.pubpid
WHERE l.comments LIKE 'AgentForge profile seed%';

DELETE l FROM lists l
INNER JOIN patient_data pd ON pd.pid = l.pid
INNER JOIN af_profile_patients seed ON seed.pubpid = pd.pubpid
WHERE l.comments LIKE 'AgentForge profile seed%';

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
    UNHEX(REPLACE(p.patient_uuid, '-', '')), p.title, 'English', '', p.fname, p.lname, p.mname,
    p.dob, p.street, p.postal_code, p.city, p.state, 'US', '', '',
    p.phone_home, '', '', p.phone_cell, 'active', '', NOW(), p.sex, '', '',
    1, p.email, '', '', p.race, p.ethnicity,
    '', '', '', '', '', '', p.pubpid, ids.pid, '', '', '', '', 'YES', 'YES', 'YES',
    'YES', 'YES', 'NO', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
    '', '', NOW(), 'NO', '', '', '', '', '', 'YES', '', '', '', 1, 1
FROM af_profile_patients p
INNER JOIN af_profile_patient_ids ids ON ids.pubpid = p.pubpid
WHERE ids.existing_pid IS NULL;

UPDATE patient_data pd
INNER JOIN af_profile_patients p ON p.pubpid = pd.pubpid
SET pd.uuid = UNHEX(REPLACE(p.patient_uuid, '-', '')),
    pd.title = p.title,
    pd.fname = p.fname,
    pd.lname = p.lname,
    pd.mname = p.mname,
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

CREATE TEMPORARY TABLE af_profile_problems (
    pubpid VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    begdate DATE NOT NULL,
    diagnosis VARCHAR(64) NOT NULL
);

INSERT INTO af_profile_problems VALUES
    ('AF-W2-001', 'Type 2 diabetes mellitus', '2018-05-14', 'ICD10:E11.9'),
    ('AF-W2-001', 'Essential hypertension', '2016-03-22', 'ICD10:I10'),
    ('AF-MVP-002', 'Type 2 diabetes mellitus', '2020-03-16', 'ICD10:E11.9'),
    ('AF-MVP-002', 'Hyperlipidemia', '2022-02-09', 'ICD10:E78.5'),
    ('AF-W2-002', 'Atrial fibrillation', '2016-01-01', 'ICD10:I48.91'),
    ('AF-W2-002', 'Benign prostatic hyperplasia', '2019-01-01', 'ICD10:N40.0'),
    ('AF-W2-003', 'Type 2 diabetes mellitus', '2021-01-01', 'ICD10:E11.9'),
    ('AF-W2-003', 'Mild recurrent depression', '2022-01-01', 'ICD10:F33.0'),
    ('AF-W2-004', 'Hypertension', '2018-01-01', 'ICD10:I10'),
    ('AF-W2-004', 'Alcohol use disorder in remission', '2014-01-01', 'ICD10:F10.21');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
SELECT UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', pr.title, pr.begdate, 1, pr.diagnosis,
       'AgentForge profile seed: active problem', pd.pid, 'admin', 'Default', 'confirmed'
FROM af_profile_problems pr
INNER JOIN patient_data pd ON pd.pubpid = pr.pubpid;

CREATE TEMPORARY TABLE af_profile_meds (
    pubpid VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    begdate DATE NOT NULL,
    instructions VARCHAR(255) NOT NULL
);

INSERT INTO af_profile_meds VALUES
    ('AF-W2-001', 'Metformin 1000 mg tablet', '2019-01-10', 'Take 1 tablet by mouth twice daily with meals.'),
    ('AF-W2-001', 'Lisinopril 20 mg tablet', '2016-03-22', 'Take 1 tablet by mouth once daily.'),
    ('AF-MVP-002', 'Metformin 500 mg tablet', '2020-03-16', 'Take 1 tablet by mouth twice daily.'),
    ('AF-MVP-002', 'Atorvastatin 20 mg tablet', '2022-02-09', 'Take 1 tablet by mouth at bedtime.'),
    ('AF-W2-002', 'Apixaban 5 mg tablet', '2016-01-01', 'Take 1 tablet by mouth twice daily.'),
    ('AF-W2-002', 'Tamsulosin 0.4 mg capsule', '2019-01-01', 'Take 1 capsule by mouth once daily.'),
    ('AF-W2-003', 'Metformin 1000 mg tablet', '2021-01-01', 'Take 1 tablet by mouth twice daily.'),
    ('AF-W2-003', 'Sertraline 50 mg tablet', '2023-01-01', 'Take 1 tablet by mouth once daily.'),
    ('AF-W2-004', 'Lisinopril 20 mg tablet', '2019-01-01', 'Take 1 tablet by mouth once daily.'),
    ('AF-W2-004', 'Atorvastatin 40 mg tablet', '2020-01-01', 'Take 1 tablet by mouth at bedtime.');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
SELECT UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', m.title, m.begdate, 1, '',
       'AgentForge profile seed: active medication', pd.pid, 'admin', 'Default', 'confirmed'
FROM af_profile_meds m
INNER JOIN patient_data pd ON pd.pubpid = m.pubpid;

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
)
SELECT l.id, m.instructions, 'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
FROM af_profile_meds m
INNER JOIN patient_data pd ON pd.pubpid = m.pubpid
INNER JOIN lists l ON l.pid = pd.pid
    AND l.type = 'medication'
    AND l.title = m.title
    AND l.comments = 'AgentForge profile seed: active medication';

CREATE TEMPORARY TABLE af_profile_allergies (
    pubpid VARCHAR(32) NOT NULL,
    title VARCHAR(128) NOT NULL,
    begdate DATE NOT NULL,
    reaction VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL
);

INSERT INTO af_profile_allergies VALUES
    ('AF-W2-001', 'Penicillin', '2006-08-02', 'hives', 'moderate'),
    ('AF-MVP-002', 'Penicillin', '1999-06-01', 'hives', 'moderate'),
    ('AF-W2-002', 'No known drug allergies', '2026-04-18', 'none documented', 'mild'),
    ('AF-W2-003', 'Ibuprofen', '2026-04-19', 'GI bleed', 'severe'),
    ('AF-W2-004', 'Codeine', '2026-04-15', 'nausea', 'mild');

INSERT INTO lists (
    uuid, date, type, title, begdate, activity, diagnosis, comments,
    pid, user, groupname, reaction, verification, severity_al
)
SELECT UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'allergy', a.title, a.begdate, 1, '',
       'AgentForge profile seed: active allergy', pd.pid, 'admin', 'Default',
       a.reaction, 'confirmed', a.severity
FROM af_profile_allergies a
INNER JOIN patient_data pd ON pd.pubpid = a.pubpid;

COMMIT;

SELECT
    pd.pid AS pid,
    LOWER(CONCAT(SUBSTR(HEX(pd.uuid),1,8),'-',SUBSTR(HEX(pd.uuid),9,4),'-',SUBSTR(HEX(pd.uuid),13,4),'-',SUBSTR(HEX(pd.uuid),17,4),'-',SUBSTR(HEX(pd.uuid),21))) AS patient_uuid,
    pd.pubpid,
    pd.fname,
    pd.lname,
    pd.DOB,
    pd.sex
FROM patient_data pd
WHERE pd.pubpid IN ('AF-W2-001', 'AF-MVP-002', 'AF-W2-002', 'AF-W2-003', 'AF-W2-004')
ORDER BY pd.pubpid;
