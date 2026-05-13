CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attack_cases (
    case_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    impact_domain TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attack_runs (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    target_mode TEXT NOT NULL,
    target_url TEXT NOT NULL,
    run_mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    stop_reason TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observed_responses (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_trace_events (
    trace_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS judge_verdicts (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    verdict TEXT NOT NULL,
    severity TEXT NOT NULL,
    impact_domain TEXT NOT NULL,
    requires_human_review INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vulnerability_reports (
    vulnerability_id TEXT PRIMARY KEY,
    source_run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    impact_domain TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resilience_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    risk_weighted_score REAL NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regression_cases (
    regression_id TEXT PRIMARY KEY,
    source_report_id TEXT,
    source_run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suite_summaries (
    summary_id TEXT PRIMARY KEY,
    suite TEXT NOT NULL,
    target_mode TEXT NOT NULL,
    run_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    active INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authorized_scopes (
    scope_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS site_scan_runs (
    scan_id TEXT PRIMARY KEY,
    target_url TEXT NOT NULL,
    client_id TEXT,
    project_id TEXT,
    scope_id TEXT,
    scan_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    finding_count INTEGER NOT NULL,
    highest_severity TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS site_scan_findings (
    finding_id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    check_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
