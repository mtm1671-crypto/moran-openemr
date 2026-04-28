param(
    [string]$MysqlContainer = "development-easy-mysql-1",
    [string]$MysqlUser = "root",
    [string]$MysqlPassword = "root",
    [string]$Database = "openemr"
)

$ErrorActionPreference = "Stop"

$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Docker\Docker\resources;C:\Program Files\Docker\cli-plugins;' + $env:Path

$sql = @'
START TRANSACTION;

SET @pubpid := 'AF-MVP-001';
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
    UNHEX(REPLACE(UUID(), '-', '')), 'Ms.', 'English', '', 'Elena', 'Morrison', '',
    '1972-09-18', '415 Cedar Avenue', '60611', 'Chicago', 'IL', 'US', '', '',
    '312-555-0179', '', '', '312-555-0180', 'active', '', NOW(), 'Female', '', '',
    1, 'elena.morrison@example.invalid', '', '', 'white', 'not_hispanic_or_latino',
    '', '', '', '', '', '', @pubpid, @pid, '', '', '', '', 'YES', 'YES', 'YES',
    'YES', 'YES', 'NO', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
    '', '', NOW(), 'NO', '', '', '', '', '', 'YES', '', '', 'Cook', 1, 1
WHERE @existing_pid IS NULL;

UPDATE patient_data
SET fname = 'Elena', lname = 'Morrison', DOB = '1972-09-18', sex = 'Female',
    street = '415 Cedar Avenue', city = 'Chicago', state = 'IL', postal_code = '60611',
    phone_cell = '312-555-0180', email = 'elena.morrison@example.invalid',
    providerID = 1, updated_by = 1
WHERE pid = @pid;

INSERT INTO lists (uuid, date, type, title, begdate, activity, diagnosis, comments, pid, user, groupname, verification)
VALUES
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Type 2 diabetes mellitus', '2018-05-14', 1, 'ICD10:E11.9', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Essential hypertension', '2016-03-22', 1, 'ICD10:I10', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed'),
    (UNHEX(REPLACE(UUID(), '-', '')), NOW(), 'medical_problem', 'Stage 3a chronic kidney disease', '2024-11-04', 1, 'ICD10:N18.31', 'AgentForge MVP seed: active problem', @pid, 'admin', 'Default', 'confirmed');

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

COMMIT;

SELECT
    @pid AS pid,
    LOWER(CONCAT(SUBSTR(HEX(uuid),1,8),'-',SUBSTR(HEX(uuid),9,4),'-',SUBSTR(HEX(uuid),13,4),'-',SUBSTR(HEX(uuid),17,4),'-',SUBSTR(HEX(uuid),21))) AS patient_uuid,
    pubpid,
    fname,
    lname,
    DOB,
    sex
FROM patient_data
WHERE pid = @pid;
'@

$sql | docker exec -i $MysqlContainer mariadb "-u$MysqlUser" "-p$MysqlPassword" $Database
