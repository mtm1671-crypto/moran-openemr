START TRANSACTION;

SET @pubpid := 'AF-MVP-001';
SET @patient_uuid := 'c3888c9f-432d-11f1-a700-7a0f44501ceb';
SET @existing_pid := (SELECT pid FROM patient_data WHERE pubpid = @pubpid LIMIT 1);
SET @pid := COALESCE(@existing_pid, (SELECT COALESCE(MAX(pid), 0) + 1 FROM patient_data));

DELETE presult FROM procedure_result presult
INNER JOIN procedure_report preport ON preport.procedure_report_id = presult.procedure_report_id
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE preport FROM procedure_report preport
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE poc FROM procedure_order_code poc
INNER JOIN procedure_order porder ON porder.procedure_order_id = poc.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE FROM procedure_order WHERE control_id LIKE CONCAT(@pubpid, '-%');

DELETE lm FROM lists_medication lm
INNER JOIN lists l ON l.id = lm.list_id
WHERE l.pid = @pid AND l.comments LIKE 'AgentForge MVP seed%';

DELETE FROM lists WHERE pid = @pid AND comments LIKE 'AgentForge MVP seed%';

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
) SELECT
    UNHEX(REPLACE(@patient_uuid, '-', '')), 'Ms.', 'English', '', 'Elena', 'Morrison', '',
    '1972-09-18', '415 Cedar Avenue', '60611', 'Chicago', 'IL', 'US', '', '',
    '312-555-0179', '', '', '312-555-0180', 'active', '', NOW(), 'Female', '', '',
    1, 'elena.morrison@example.invalid', '', '', 'white', 'not_hispanic_or_latino',
    '', '', '', '', '', '', @pubpid, @pid, '', '', '', '', 'YES', 'YES', 'YES',
    'YES', 'YES', 'NO', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
    '', '', NOW(), 'NO', '', '', '', '', '', 'YES', '', '', 'Cook', 1, 1
WHERE @existing_pid IS NULL;

UPDATE patient_data
SET fname = 'Elena',
    lname = 'Morrison',
    DOB = '1972-09-18',
    sex = 'Female',
    street = '415 Cedar Avenue',
    city = 'Chicago',
    state = 'IL',
    postal_code = '60611',
    phone_home = '312-555-0179',
    phone_cell = '312-555-0180',
    email = 'elena.morrison@example.invalid',
    providerID = 1,
    date = NOW(),
    updated_by = 1
WHERE pid = @pid;

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Type 2 diabetes mellitus', '2018-05-14', 1, 'ICD10:E11.9', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Essential hypertension', '2016-03-22', 1, 'ICD10:I10', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Stage 3a chronic kidney disease', '2024-11-04', 1, 'ICD10:N18.31', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', 'Metformin 1000 mg tablet', '2019-01-10', 1, '', 'AgentForge MVP seed: active medication', @pid, 'admin', 'Default', 'confirmed');
SET @metformin_list_id := LAST_INSERT_ID();

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
) VALUES (
    @metformin_list_id, 'Take 1 tablet by mouth twice daily with meals.',
    'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
);

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', 'Lisinopril 20 mg tablet', '2016-03-22', 1, '', 'AgentForge MVP seed: active medication', @pid, 'admin', 'Default', 'confirmed');
SET @lisinopril_list_id := LAST_INSERT_ID();

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
) VALUES (
    @lisinopril_list_id, 'Take 1 tablet by mouth once daily.',
    'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
);

INSERT INTO lists (
    uuid, date, type, title, begdate, activity, diagnosis, comments,
    pid, user, groupname, reaction, verification, severity_al
) VALUES (
    UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'allergy', 'Penicillin', '2006-08-02', 1, '',
    'AgentForge MVP seed: active allergy', @pid, 'admin', 'Default',
    'unassigned', 'confirmed', 'moderate'
);

INSERT INTO procedure_order (
    uuid, provider_id, patient_id, encounter_id, date_collected, date_ordered,
    order_priority, order_status, patient_instructions, activity, control_id,
    lab_id, specimen_type, specimen_location, date_transmitted, clinical_hx,
    procedure_order_type, order_intent, location_id
) VALUES (
    UNHEX(REPLACE(UUID(), '-', '')), 1, @pid, 0, '2026-04-24 08:15:00', '2026-04-24 08:00:00',
    'routine', 'complete', '', 1, CONCAT(@pubpid, '-LAB-20260424'), 0, 'blood', '',
    '2026-04-24 08:20:00', 'Diabetes follow-up labs', 'laboratory_test', 'order', 3
);
SET @order_id := LAST_INSERT_ID();

INSERT INTO procedure_order_code (procedure_order_id, procedure_order_seq, procedure_code, procedure_name, procedure_source, procedure_order_title, procedure_type)
VALUES (@order_id, 1, '24323-8', 'Comprehensive metabolic panel and A1c', '1', 'Diabetes follow-up laboratory panel', 'laboratory');

INSERT INTO procedure_report (uuid, procedure_order_id, procedure_order_seq, date_collected, date_report, source, specimen_num, report_status, review_status, report_notes)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), @order_id, 1, '2026-04-24 08:15:00', '2026-04-24 11:05:00', 0, 'AF-MVP-SPEC-001', 'final', 'reviewed', 'AgentForge MVP seed: recent lab report');
SET @report_id := LAST_INSERT_ID();

INSERT INTO procedure_result (uuid, procedure_report_id, result_data_type, result_code, result_text, date, facility, units, result, `range`, abnormal, comments, result_status)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '4548-4', 'Hemoglobin A1c/Hemoglobin.total in Blood', '2026-04-24 11:05:00', 'Your Clinic Name Here', '%', '8.6', '4.0-5.6', 'high', 'AgentForge MVP seed: above goal for demo context', 'final'),
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '2160-0', 'Creatinine [Mass/volume] in Serum or Plasma', '2026-04-24 11:05:00', 'Your Clinic Name Here', 'mg/dL', '1.28', '0.57-1.00', 'high', 'AgentForge MVP seed: mild elevation', 'final'),
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '33914-3', 'Glomerular filtration rate/1.73 sq M.predicted', '2026-04-24 11:05:00', 'Your Clinic Name Here', 'mL/min/1.73m2', '52', '>59', 'low', 'AgentForge MVP seed: below reference range', 'final');

SET @pubpid := 'AF-MVP-002';
SET @patient_uuid := '5b8f4d2a-5e0a-4a7d-91f6-e507321f6d02';
SET @existing_pid := (SELECT pid FROM patient_data WHERE pubpid = @pubpid LIMIT 1);
SET @pid := COALESCE(@existing_pid, (SELECT COALESCE(MAX(pid), 0) + 1 FROM patient_data));

DELETE presult FROM procedure_result presult
INNER JOIN procedure_report preport ON preport.procedure_report_id = presult.procedure_report_id
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE preport FROM procedure_report preport
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE poc FROM procedure_order_code poc
INNER JOIN procedure_order porder ON porder.procedure_order_id = poc.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE FROM procedure_order WHERE control_id LIKE CONCAT(@pubpid, '-%');

DELETE lm FROM lists_medication lm
INNER JOIN lists l ON l.id = lm.list_id
WHERE l.pid = @pid AND l.comments LIKE 'AgentForge MVP seed%';

DELETE FROM lists WHERE pid = @pid AND comments LIKE 'AgentForge MVP seed%';

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
) SELECT
    UNHEX(REPLACE(@patient_uuid, '-', '')), 'Ms.', 'English', '', 'Margaret', 'Chen', 'L',
    '1967-08-14', '4421 Magnolia Ave, Apt 3B', '94705', 'Berkeley', 'CA', 'US', '', '',
    '510-555-0148', '', '', '510-555-0148', 'active', '', NOW(), 'Female', '', '',
    1, 'mchen.demo@example.test', '', '', 'asian', 'not_hispanic_or_latino',
    '', '', '', '', '', '', @pubpid, @pid, '', '', '', '', 'YES', 'YES', 'YES',
    'YES', 'YES', 'NO', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
    '', '', NOW(), 'NO', '', '', '', '', '', 'YES', '', '', 'Cook', 1, 1
WHERE @existing_pid IS NULL;

UPDATE patient_data
SET fname = 'Margaret',
    lname = 'Chen',
    mname = 'L',
    DOB = '1967-08-14',
    sex = 'Female',
    street = '4421 Magnolia Ave, Apt 3B',
    city = 'Berkeley',
    state = 'CA',
    postal_code = '94705',
    phone_home = '510-555-0148',
    phone_cell = '510-555-0148',
    email = 'mchen.demo@example.test',
    providerID = 1,
    date = NOW(),
    updated_by = 1
WHERE pid = @pid;

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Type 2 diabetes mellitus', '2020-03-16', 1, 'ICD10:E11.9', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Essential hypertension', '2018-05-21', 1, 'ICD10:I10', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Hyperlipidemia', '2022-02-09', 1, 'ICD10:E78.5', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', 'Metformin 500 mg tablet', '2020-03-16', 1, '', 'AgentForge MVP seed: active medication', @pid, 'admin', 'Default', 'confirmed');
SET @metformin_list_id := LAST_INSERT_ID();

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
) VALUES (
    @metformin_list_id, 'Take 1 tablet by mouth twice daily.',
    'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
);

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', 'Atorvastatin 20 mg tablet', '2022-02-09', 1, '', 'AgentForge MVP seed: active medication', @pid, 'admin', 'Default', 'confirmed');
SET @atorvastatin_list_id := LAST_INSERT_ID();

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
) VALUES (
    @atorvastatin_list_id, 'Take 1 tablet by mouth at bedtime.',
    'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
);

INSERT INTO lists (
    uuid, date, type, title, begdate, activity, diagnosis, comments,
    pid, user, groupname, reaction, verification, severity_al
) VALUES (
    UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'allergy', 'Penicillin', '1999-06-01', 1, '',
    'AgentForge MVP seed: active allergy', @pid, 'admin', 'Default',
    'unassigned', 'confirmed', 'moderate'
);

INSERT INTO procedure_order (
    uuid, provider_id, patient_id, encounter_id, date_collected, date_ordered,
    order_priority, order_status, patient_instructions, activity, control_id,
    lab_id, specimen_type, specimen_location, date_transmitted, clinical_hx,
    procedure_order_type, order_intent, location_id
) VALUES (
    UNHEX(REPLACE(UUID(), '-', '')), 1, @pid, 0, '2026-04-22 07:42:00', '2026-04-22 07:30:00',
    'routine', 'complete', '', 1, CONCAT(@pubpid, '-LAB-20260423'), 0, 'blood', '',
    '2026-04-22 07:50:00', 'Hyperlipidemia, hypertension, and type 2 diabetes follow-up labs', 'laboratory_test', 'order', 3
);
SET @order_id := LAST_INSERT_ID();

INSERT INTO procedure_order_code (procedure_order_id, procedure_order_seq, procedure_code, procedure_name, procedure_source, procedure_order_title, procedure_type)
VALUES (@order_id, 1, '57698-3', 'Lipid panel with direct LDL', '1', 'Lipid and diabetes follow-up laboratory panel', 'laboratory');

INSERT INTO procedure_report (uuid, procedure_order_id, procedure_order_seq, date_collected, date_report, source, specimen_num, report_status, review_status, report_notes)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), @order_id, 1, '2026-04-22 07:42:00', '2026-04-23 09:05:00', 0, 'PDX-26041815', 'final', 'reviewed', 'AgentForge MVP seed: Margaret Chen lipid and diabetes lab report');
SET @report_id := LAST_INSERT_ID();

INSERT INTO procedure_result (uuid, procedure_report_id, result_data_type, result_code, result_text, date, facility, units, result, `range`, abnormal, comments, result_status)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '4548-4', 'Hemoglobin A1c/Hemoglobin.total in Blood', '2026-04-23 09:05:00', 'Pacific Diagnostics Lab', '%', '7.6', '4.0-5.6', 'high', 'AgentForge MVP seed: diabetes follow-up context for Margaret Chen', 'final'),
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '13457-7', 'Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation', '2026-04-23 09:05:00', 'Pacific Diagnostics Lab', 'mg/dL', '142', '<100', 'high', 'AgentForge MVP seed: baseline LDL before scanned panel review', 'final'),
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '2160-0', 'Creatinine [Mass/volume] in Serum or Plasma', '2026-04-23 09:05:00', 'Pacific Diagnostics Lab', 'mg/dL', '0.91', '0.57-1.00', '', 'AgentForge MVP seed: renal function context for diabetes follow-up', 'final');

SET @pubpid := 'AF-MVP-003';
SET @patient_uuid := 'f0d8bb04-8d8f-4e66-8f59-ecf2d8d98f34';
SET @existing_pid := (SELECT pid FROM patient_data WHERE pubpid = @pubpid LIMIT 1);
SET @pid := COALESCE(@existing_pid, (SELECT COALESCE(MAX(pid), 0) + 1 FROM patient_data));

DELETE presult FROM procedure_result presult
INNER JOIN procedure_report preport ON preport.procedure_report_id = presult.procedure_report_id
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE preport FROM procedure_report preport
INNER JOIN procedure_order porder ON porder.procedure_order_id = preport.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE poc FROM procedure_order_code poc
INNER JOIN procedure_order porder ON porder.procedure_order_id = poc.procedure_order_id
WHERE porder.control_id LIKE CONCAT(@pubpid, '-%');

DELETE FROM procedure_order WHERE control_id LIKE CONCAT(@pubpid, '-%');

DELETE lm FROM lists_medication lm
INNER JOIN lists l ON l.id = lm.list_id
WHERE l.pid = @pid AND l.comments LIKE 'AgentForge MVP seed%';

DELETE FROM lists WHERE pid = @pid AND comments LIKE 'AgentForge MVP seed%';

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
) SELECT
    UNHEX(REPLACE(@patient_uuid, '-', '')), 'Ms.', 'English', '', 'Priya', 'Shah', '',
    '1988-12-03', '901 South Wabash Avenue', '60605', 'Chicago', 'IL', 'US', '', '',
    '312-555-0304', '', '', '312-555-0305', 'active', '', NOW(), 'Female', '', '',
    1, 'priya.shah@example.invalid', '', '', 'asian', 'not_hispanic_or_latino',
    '', '', '', '', '', '', @pubpid, @pid, '', '', '', '', 'YES', 'YES', 'YES',
    'YES', 'YES', 'NO', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
    '', '', NOW(), 'NO', '', '', '', '', '', 'YES', '', '', 'Cook', 1, 1
WHERE @existing_pid IS NULL;

UPDATE patient_data
SET fname = 'Priya',
    lname = 'Shah',
    DOB = '1988-12-03',
    sex = 'Female',
    street = '901 South Wabash Avenue',
    city = 'Chicago',
    state = 'IL',
    postal_code = '60605',
    phone_home = '312-555-0304',
    phone_cell = '312-555-0305',
    email = 'priya.shah@example.invalid',
    providerID = 1,
    date = NOW(),
    updated_by = 1
WHERE pid = @pid;

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Iron deficiency anemia', '2025-10-28', 1, 'ICD10:D50.9', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Hypothyroidism', '2017-08-09', 1, 'ICD10:E03.9', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Migraine without aura', '2020-01-17', 1, 'ICD10:G43.009', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed');

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', 'Ferrous sulfate 325 mg tablet', '2025-11-02', 1, '', 'AgentForge MVP seed: active medication', @pid, 'admin', 'Default', 'confirmed');
SET @ferrous_list_id := LAST_INSERT_ID();

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
) VALUES (
    @ferrous_list_id, 'Take 1 tablet by mouth once daily with food.',
    'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
);

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medication', 'Levothyroxine 75 mcg tablet', '2017-08-09', 1, '', 'AgentForge MVP seed: active medication', @pid, 'admin', 'Default', 'confirmed');
SET @levothyroxine_list_id := LAST_INSERT_ID();

INSERT INTO lists_medication (
    list_id, drug_dosage_instructions, usage_category, usage_category_title,
    request_intent, request_intent_title, prescription_id, is_primary_record,
    reporting_source_record_id
) VALUES (
    @levothyroxine_list_id, 'Take 1 tablet by mouth every morning before breakfast.',
    'community', 'Home/Community', 'plan', 'Plan', NULL, 1, 1
);

INSERT INTO lists (
    uuid, date, type, title, begdate, activity, diagnosis, comments,
    pid, user, groupname, reaction, verification, severity_al
) VALUES (
    UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'allergy', 'Latex', '2013-05-20', 1, '',
    'AgentForge MVP seed: active allergy', @pid, 'admin', 'Default',
    'unassigned', 'confirmed', 'mild'
);

INSERT INTO procedure_order (
    uuid, provider_id, patient_id, encounter_id, date_collected, date_ordered,
    order_priority, order_status, patient_instructions, activity, control_id,
    lab_id, specimen_type, specimen_location, date_transmitted, clinical_hx,
    procedure_order_type, order_intent, location_id
) VALUES (
    UNHEX(REPLACE(UUID(), '-', '')), 1, @pid, 0, '2026-04-26 07:50:00', '2026-04-26 07:45:00',
    'routine', 'complete', '', 1, CONCAT(@pubpid, '-LAB-20260426'), 0, 'blood', '',
    '2026-04-26 07:55:00', 'Anemia and thyroid follow-up labs', 'laboratory_test', 'order', 3
);
SET @order_id := LAST_INSERT_ID();

INSERT INTO procedure_order_code (procedure_order_id, procedure_order_seq, procedure_code, procedure_name, procedure_source, procedure_order_title, procedure_type)
VALUES (@order_id, 1, '718-7', 'Anemia and thyroid laboratory panel', '1', 'Anemia and thyroid follow-up laboratory panel', 'laboratory');

INSERT INTO procedure_report (uuid, procedure_order_id, procedure_order_seq, date_collected, date_report, source, specimen_num, report_status, review_status, report_notes)
VALUES (UNHEX(REPLACE(UUID(), '-', '')), @order_id, 1, '2026-04-26 07:50:00', '2026-04-26 10:40:00', 0, 'AF-MVP-SPEC-003', 'final', 'reviewed', 'AgentForge MVP seed: anemia and thyroid lab report');
SET @report_id := LAST_INSERT_ID();

INSERT INTO procedure_result (uuid, procedure_report_id, result_data_type, result_code, result_text, date, facility, units, result, `range`, abnormal, comments, result_status)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '718-7', 'Hemoglobin [Mass/volume] in Blood', '2026-04-26 10:40:00', 'Your Clinic Name Here', 'g/dL', '9.8', '12.0-15.5', 'low', 'AgentForge MVP seed: anemia demo context', 'final'),
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '2276-4', 'Ferritin [Mass/volume] in Serum or Plasma', '2026-04-26 10:40:00', 'Your Clinic Name Here', 'ng/mL', '8', '13-150', 'low', 'AgentForge MVP seed: iron stores low', 'final'),
    (UNHEX(REPLACE(UUID(), '-', '')), @report_id, 'N', '3016-3', 'Thyrotropin [Units/volume] in Serum or Plasma', '2026-04-26 10:40:00', 'Your Clinic Name Here', 'uIU/mL', '5.8', '0.4-4.0', 'high', 'AgentForge MVP seed: mildly elevated TSH', 'final');

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
WHERE pd.pubpid IN ('AF-MVP-001', 'AF-MVP-002', 'AF-MVP-003')
ORDER BY pd.pubpid;
