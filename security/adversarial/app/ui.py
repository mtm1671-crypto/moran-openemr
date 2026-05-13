"""FastAPI operator UI for Week 3 adversarial runs."""

from __future__ import annotations

from html import escape
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .config import Settings
from .export_run import build_run_export, render_run_markdown
from .models import RunMode
from .reporting import dashboard_summary
from .run_store import RunStore
from .run_week3_eval import run_suite
from .site_scanner import PassiveSiteScanner


def create_app() -> FastAPI:
    settings = Settings()
    store = RunStore(settings.sqlite_path, private_path=settings.private_sqlite_path)
    app = FastAPI(title="AgentForge Adversarial Platform", version="0.1.0")

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        ready, message = store.readiness()
        status_code = 200 if ready else 503
        return JSONResponse(
            {"ready": ready, "message": message, "sqlite_path": str(settings.sqlite_path)},
            status_code=status_code,
        )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        store.initialize()
        runs = store.latest_runs(limit=20)
        cases = store.cases()
        verdicts = store.verdicts()
        reports = store.reports()
        observations = store.observations()
        snapshots = store.snapshots()
        site_scans = store.site_scan_runs(limit=10)
        summary = dashboard_summary(
            cases=cases,
            runs=runs,
            verdicts=verdicts,
            reports=reports,
            observations=observations,
            snapshots=snapshots,
        )
        latest_verdicts = summary["latest_verdicts"]
        current_reports = summary["current_reports"]
        latest = runs[0] if runs else None
        recommendation = _recommendation(latest_verdicts)
        recommendation_class = _recommendation_class(recommendation)
        latest_target = escape(str(latest["target_url"])) if latest else escape(settings.target_url)
        return _page(
            "AgentForge Adversarial Risk Overview",
            f"""
            <header class="command-header">
              <a class="brand-lockup" href="/" aria-label="AgentForge Adversarial dashboard">
                <span class="brand-sigil" aria-hidden="true"></span>
                <span>
                  <strong>AgentForge</strong>
                  <small>Adversarial Control Plane</small>
                </span>
              </a>
              <div class="header-meta" aria-label="Operator status">
                <span>W3</span>
                <span>{escape(str(latest["target_mode"])) if latest else "standby"}</span>
                <span>synthetic</span>
              </div>
            </header>
            <section class="hero command-slab">
              <div class="hero-primary">
                <p class="eyebrow">Week 3 adversarial command // synthetic target</p>
                <h1 class="{recommendation_class}">{escape(recommendation)}</h1>
                <p class="hero-copy">A controlled black-box campaign surface for deployed clinical Co-Pilot risk, synthetic patient scope, and deterministic Judge evidence.</p>
                <dl class="target-list">
                  <div><dt>Target mode</dt><dd>{escape(str(latest["target_mode"])) if latest else "no runs yet"}</dd></div>
                  <div><dt>Target URL</dt><dd>{latest_target}</dd></div>
                </dl>
              </div>
              <aside class="readiness-stack" aria-label="Readiness counters">
                <dl class="metric-grid">
                  <div><dt>Runs</dt><dd>{len(runs)}</dd></div>
                  <div><dt>Latest Verdicts</dt><dd>{len(latest_verdicts)}</dd></div>
                  <div><dt>Current Reports</dt><dd>{len(current_reports)}</dd></div>
                </dl>
                <div class="system-line">
                  <span>SQLite /data</span>
                  <span>OAuth synthetic clinician</span>
                  <span>Report-only default</span>
                </div>
              </aside>
            </section>
            <section class="command-strip" aria-label="Campaign controls">
              <div class="strip-copy">
                <span class="section-code">CTRL-03</span>
                <strong>Campaign control</strong>
              </div>
              <form method="post" action="/runs/smoke" data-run-suite="smoke">
                <button type="submit" data-loading-label="Running Smoke">
                  <span class="button-label">Run Smoke</span>
                  <span class="button-spinner" aria-hidden="true"></span>
                </button>
              </form>
              <form method="post" action="/runs/seed" data-run-suite="seed">
                <button class="button-primary" type="submit" data-loading-label="Running Seed Suite">
                  <span class="button-label">Run Seed Suite</span>
                  <span class="button-spinner" aria-hidden="true"></span>
                </button>
              </form>
              <button type="button" data-toggle-density>Toggle Density</button>
              <div class="run-status" data-run-status role="status" aria-live="assertive" hidden>
                <span class="run-status-pulse" aria-hidden="true"></span>
                <strong>Campaign running</strong>
                <span data-run-status-copy>The dashboard will open the newest run when the suite finishes.</span>
              </div>
            </section>
            <section class="command-strip" aria-label="Authorized site scan controls">
              <div class="strip-copy">
                <span class="section-code">SCAN-05</span>
                <strong>Authorized site scan</strong>
              </div>
              <form class="site-scan-form" method="post" action="/site-scans/passive" data-run-suite="site-scan">
                <label for="site-target-url">Allowlisted URL</label>
                <input id="site-target-url" name="target_url" type="url" placeholder="https://example.your-domain.com" required>
                <button type="submit" data-loading-label="Scanning Site">
                  <span class="button-label">Run Passive Scan</span>
                  <span class="button-spinner" aria-hidden="true"></span>
                </button>
              </form>
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">POSTURE-00</span>
                <h2>Risk Posture</h2>
              </div>
              {_posture_panel(summary)}
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">MATRIX-01</span>
                <h2>Coverage</h2>
              </div>
              {_coverage_table(cases, verdicts, runs)}
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">RUNLOG-02</span>
                <h2>Latest Runs</h2>
              </div>
              <div class="table-tools">
                <label for="run-filter">Filter runs</label>
                <input id="run-filter" type="search" placeholder="run id, status, export..." data-filter-target="#runs-table">
                <span data-count-visible="#runs-table"></span>
              </div>
              {_runs_table(runs, _verdict_by_run_id(verdicts))}
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">SITE-06</span>
                <h2>Site Scans</h2>
              </div>
              {_site_scans_table(site_scans)}
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">REPORT-04</span>
                <h2>Findings</h2>
              </div>
              {_reports_table(current_reports)}
            </section>
            """,
        )

    @app.post("/runs/{suite}")
    def start_run(suite: str) -> Response:
        if suite not in {"smoke", "seed", "regression"}:
            return HTMLResponse(_page("Invalid suite", "<h1>Invalid suite</h1>"), status_code=400)
        try:
            settings.validate_ready_for_run()
            run_ids = run_suite(
                settings=settings,
                suite=suite,
                run_mode=RunMode.REPORT_ONLY,
            )
        except Exception as exc:
            return HTMLResponse(
                _page(
                    "Run failed",
                    f"""
                    <h1>Run failed</h1>
                    <p>{escape(type(exc).__name__)}: {escape(str(exc))}</p>
                    <p><a href="/">Back to dashboard</a></p>
                    """,
                ),
                status_code=502,
            )
        if not run_ids:
            return RedirectResponse("/", status_code=303)
        return RedirectResponse(f"/runs/{run_ids[-1]}", status_code=303)

    @app.post("/site-scans/passive")
    async def start_passive_site_scan(request: Request) -> Response:
        body = (await request.body()).decode()
        params = parse_qs(body)
        target_url = params.get("target_url", [""])[0].strip()
        if not target_url:
            return HTMLResponse(_page("Invalid target", "<h1>Invalid target</h1>"), status_code=400)
        try:
            settings.validate_target_allowed(target_url)
            store.initialize()
            scan, findings = PassiveSiteScanner(settings).scan(target_url)
            store.save_site_scan_run(scan)
            store.save_site_scan_findings(findings)
        except Exception as exc:
            return HTMLResponse(
                _page(
                    "Site scan failed",
                    f"""
                    <h1>Site scan failed</h1>
                    <p>{escape(type(exc).__name__)}: {escape(str(exc))}</p>
                    <p><a href="/">Risk overview</a></p>
                    """,
                ),
                status_code=502,
            )
        return RedirectResponse(f"/site-scans/{scan.scan_id}", status_code=303)

    @app.get("/site-scans/{scan_id}", response_class=HTMLResponse)
    def site_scan_detail(scan_id: str) -> Response:
        store.initialize()
        scans = [scan for scan in store.site_scan_runs(limit=500) if scan["scan_id"] == scan_id]
        if not scans:
            return HTMLResponse(
                _page(
                    "Site scan not found",
                    f"<h1>Site scan not found</h1><p>{escape(scan_id)}</p><p><a href=\"/\">Risk overview</a></p>",
                ),
                status_code=404,
            )
        findings = store.site_scan_findings(scan_id)
        return HTMLResponse(
            _page(
                f"Site Scan {scan_id}",
                f"""
            <header class="command-header">
              <a class="brand-lockup" href="/">
                <span class="brand-sigil" aria-hidden="true"></span>
                <span>
                  <strong>AgentForge</strong>
                  <small>Passive Site Scan</small>
                </span>
              </a>
              <a class="header-link" href="/">Risk overview</a>
            </header>
            <section class="hero compact command-slab">
              <div>
                <p class="eyebrow">Authorized passive scan // allowlisted target</p>
                <h1>Site Scan {escape(scan_id)}</h1>
              </div>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">SUMMARY</span><h2>Scan Summary</h2></div>
              <pre>{escape(str(scans[0]))}</pre>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">FINDINGS</span><h2>Findings</h2></div>
              {_site_findings_table(findings)}
            </section>
            """,
            )
        )

    @app.get("/runs/{run_id}.json")
    def run_json(run_id: str) -> Response:
        store.initialize()
        try:
            payload = build_run_export(run_id, store)
        except ValueError:
            return JSONResponse({"detail": "run not found"}, status_code=404)
        return JSONResponse(payload)

    @app.get("/runs/{run_id}.md")
    def run_markdown(run_id: str) -> Response:
        store.initialize()
        try:
            payload = build_run_export(run_id, store)
        except ValueError:
            return HTMLResponse(_page("Run not found", f"<h1>Run not found</h1><p>{escape(run_id)}</p>"), status_code=404)
        return Response(render_run_markdown(payload), media_type="text/markdown; charset=utf-8")

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(run_id: str) -> Response:
        store.initialize()
        runs = [run for run in store.latest_runs(limit=500) if run["run_id"] == run_id]
        if not runs:
            return HTMLResponse(
                _page(
                    "Run not found",
                    f"<h1>Run not found</h1><p>{escape(run_id)}</p><p><a href=\"/\">Risk overview</a></p>",
                ),
                status_code=404,
            )
        observations = store.observations(run_id)
        verdicts = [verdict for verdict in store.verdicts() if verdict["run_id"] == run_id]
        reports = [report for report in store.reports() if report["source_run_id"] == run_id]
        traces = store.trace_events(run_id)
        return HTMLResponse(
            _page(
                f"Run {run_id}",
                f"""
            <header class="command-header">
              <a class="brand-lockup" href="/">
                <span class="brand-sigil" aria-hidden="true"></span>
                <span>
                  <strong>AgentForge</strong>
                  <small>Run Evidence</small>
                </span>
              </a>
              <a class="header-link" href="/">Risk overview</a>
            </header>
            <section class="hero compact command-slab">
              <div>
                <p class="eyebrow">Evidence packet // Black-box trace</p>
                <h1>Run {escape(run_id)}</h1>
              </div>
              <nav class="export-nav" aria-label="Run exports">
                <a href="/runs/{escape(run_id)}.json">JSON export</a>
                <a href="/runs/{escape(run_id)}.md">Markdown export</a>
              </nav>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">SUMMARY</span><h2>Run Summary</h2></div>
              <pre>{escape(str(runs[0]))}</pre>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">OBSERVE</span><h2>Black-Box Observations</h2></div>
              {_observations_detail(observations)}
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">JUDGE</span><h2>Verdicts</h2></div>
              <pre>{escape(str(verdicts))}</pre>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">REPORT</span><h2>Reports</h2></div>
              <pre>{escape(str(reports))}</pre>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">TRACE</span><h2>Trace</h2></div>
              <pre>{escape(str(traces))}</pre>
            </section>
            """,
            )
        )

    return app


def _posture_panel(summary: dict[str, object]) -> str:
    snapshot = summary.get("latest_snapshot")
    cost = summary.get("cost_summary")
    untested = summary.get("untested_categories")
    inconclusive = summary.get("inconclusive_categories")
    score_html = "<strong>No resilience snapshot yet</strong><span>Run a suite to generate a directional score.</span>"
    if isinstance(snapshot, dict):
        score_html = (
            f"<strong>{escape(str(snapshot.get('risk_weighted_score', 'n/a')))} / 100</strong>"
            f"<span>{escape(str(snapshot.get('score_explanation', 'Directional risk signal.')))}</span>"
        )
    cost_html = ""
    if isinstance(cost, dict):
        cost_html = (
            f"<strong>{escape(str(cost.get('token_estimate', 0)))} est. tokens</strong>"
            f"<span>{escape(str(cost.get('request_count', 0)))} requests / "
            f"{escape(str(cost.get('latency_ms', 0)))} ms / "
            f"${float(cost.get('provider_cost_usd', 0.0)):.4f}</span>"
        )
    untested_count = len(untested) if isinstance(untested, list) else 0
    inconclusive_count = len(inconclusive) if isinstance(inconclusive, list) else 0
    return (
        "<div class=\"posture-grid\">"
        f"<div class=\"posture-card\"><span>Resilience</span>{score_html}</div>"
        f"<div class=\"posture-card\"><span>Cost</span>{cost_html}</div>"
        f"<div class=\"posture-card\"><span>Untested</span><strong>{untested_count}</strong>"
        "<small>Risk families with no latest verdict</small></div>"
        f"<div class=\"posture-card\"><span>Inconclusive</span><strong>{inconclusive_count}</strong>"
        "<small>Risk families needing review</small></div>"
        "</div>"
    )


def _observations_detail(observations: list[dict[str, object]]) -> str:
    if not observations:
        return "<p>No observations recorded.</p>"
    blocks: list[str] = []
    for index, observation in enumerate(observations, start=1):
        black_box = {
            "status_code": observation.get("status_code"),
            "text": observation.get("text"),
            "citations": observation.get("citations"),
            "tool_outcome": observation.get("tool_outcome"),
            "request_count": observation.get("request_count"),
            "latency_ms": observation.get("latency_ms"),
            "token_estimate": observation.get("token_estimate"),
            "provider_cost_usd": observation.get("provider_cost_usd"),
        }
        gray_box = observation.get("gray_box_metadata") or {}
        diagnostic = observation.get("black_box_metadata") or {}
        blocks.append(
            "<article class=\"evidence-block\">"
            f"<h3>Observation {index}</h3>"
            "<h4>Black-box verdict evidence</h4>"
            f"<pre>{escape(str(black_box))}</pre>"
            "<h4>Gray-box diagnostic metadata</h4>"
            f"<pre>{escape(str({'gray_box_metadata': gray_box, 'diagnostic_metadata': diagnostic}))}</pre>"
            "</article>"
        )
    return "".join(blocks)


def _recommendation(verdicts: list[dict[str, object]]) -> str:
    if not verdicts:
        return "Warn: no adversarial runs recorded yet"
    failures = [verdict for verdict in verdicts if verdict.get("verdict") == "fail"]
    critical = [verdict for verdict in failures if verdict.get("severity") == "Critical"]
    if critical:
        return f"Block: {len(critical)} critical finding(s) detected"
    if failures:
        return f"Warn: {len(failures)} non-critical finding(s) need review"
    inconclusive = [verdict for verdict in verdicts if verdict.get("verdict") == "inconclusive"]
    if inconclusive:
        return f"Warn: {len(inconclusive)} inconclusive case(s) need review"
    return "Pass: no blocking findings in synthetic target run"


def _recommendation_class(recommendation: str) -> str:
    if recommendation.startswith("Block:"):
        return "recommendation recommendation-block"
    if recommendation.startswith("Warn:"):
        return "recommendation recommendation-warn"
    return "recommendation recommendation-pass"


def _verdict_by_run_id(verdicts: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for verdict in verdicts:
        run_id = str(verdict.get("run_id", ""))
        if run_id:
            latest[run_id] = verdict
    return latest


def _status_badge(value: object) -> str:
    text = escape(str(value))
    class_name = str(value).lower().replace("_", "-").replace(" ", "-")
    return f"<span class=\"status-badge status-{escape(class_name)}\">{text}</span>"


def _runs_table(
    runs: list[dict[str, object]],
    verdict_by_run_id: dict[str, dict[str, object]],
) -> str:
    if not runs:
        return "<p>No runs recorded yet.</p>"
    rows = "\n".join(
        f"<tr data-row data-filter-text=\"{escape(' '.join(str(value) for value in run.values()))}\">"
        f"<td><a class=\"run-link\" href=\"/runs/{escape(str(run['run_id']))}\">{escape(str(run['run_id']))}</a></td>"
        f"<td>{escape(str(run['case_id']))}</td>"
        f"<td>{escape(str(run['target_mode']))}</td>"
        f"<td>{escape(str(run['run_mode']))}</td>"
        f"<td>{_status_badge(verdict_by_run_id.get(str(run['run_id']), {}).get('verdict', 'pending'))}</td>"
        f"<td>{_status_badge(run['stop_reason'])}</td>"
        f"<td class=\"export-cell\"><a href=\"/runs/{escape(str(run['run_id']))}.json\">JSON</a><a href=\"/runs/{escape(str(run['run_id']))}.md\">MD</a></td>"
        "</tr>"
        for run in runs
    )
    return (
        "<table id=\"runs-table\"><caption class=\"sr-only\">Latest adversarial runs</caption>"
        "<thead><tr><th scope=\"col\">Run</th><th scope=\"col\">Case</th>"
        "<th scope=\"col\">Target</th><th scope=\"col\">Mode</th><th scope=\"col\">Verdict</th>"
        "<th scope=\"col\">Stop</th><th scope=\"col\">Export</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _coverage_table(
    cases: list[dict[str, object]],
    verdicts: list[dict[str, object]],
    runs: list[dict[str, object]],
) -> str:
    if not cases:
        return "<p>No attack cases loaded yet.</p>"
    case_category = {str(case["case_id"]): str(case["category"]) for case in cases}
    coverage: dict[str, dict[str, int]] = {}
    for case in cases:
        category = str(case["category"])
        coverage.setdefault(
            category,
            {"cases": 0, "tested": 0, "pass": 0, "fail": 0, "inconclusive": 0, "partial": 0},
        )
        coverage[category]["cases"] += 1
    latest_verdict_by_case = _latest_verdict_by_case(verdicts, runs)
    for case_id, verdict in latest_verdict_by_case.items():
        case_id = str(verdict.get("case_id", ""))
        verdict_category = case_category.get(case_id)
        if not verdict_category:
            continue
        coverage[verdict_category]["tested"] += 1
        verdict_name = str(verdict.get("verdict", ""))
        if verdict_name in coverage[verdict_category]:
            coverage[verdict_category][verdict_name] += 1
    rows = "\n".join(
        "<tr>"
        f"<td><span class=\"risk-family\">{escape(category)}</span></td>"
        f"<td>{_coverage_meter(counts['tested'], counts['cases'])}</td>"
        f"<td>{_status_count('pass', counts['pass'])}</td>"
        f"<td>{_status_count('fail', counts['fail'])}</td>"
        f"<td>{_status_count('inconclusive', counts['inconclusive'])}</td>"
        f"<td>{_status_count('partial', counts['partial'])}</td>"
        "</tr>"
        for category, counts in sorted(coverage.items())
    )
    return (
        "<table><caption class=\"sr-only\">Coverage by risk family</caption>"
        "<thead><tr><th scope=\"col\">Risk Family</th><th scope=\"col\">Cases Tested</th>"
        "<th scope=\"col\">Pass</th><th scope=\"col\">Fail</th>"
        "<th scope=\"col\">Inconclusive</th><th scope=\"col\">Partial</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _coverage_meter(tested: int, total: int) -> str:
    percent = 0 if total == 0 else int((tested / total) * 100)
    return (
        "<div class=\"coverage-meter\">"
        f"<span>{tested} / {total}</span>"
        f"<div aria-hidden=\"true\"><i style=\"width: {percent}%\"></i></div>"
        "</div>"
    )


def _status_count(name: str, count: int) -> str:
    return f"<span class=\"count-pill count-{escape(name)}\">{count}</span>"


def _latest_verdict_by_case(
    verdicts: list[dict[str, object]],
    runs: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    run_rank = {str(run["run_id"]): index for index, run in enumerate(runs)}
    latest: dict[str, dict[str, object]] = {}
    for verdict in sorted(verdicts, key=lambda item: run_rank.get(str(item.get("run_id", "")), 10_000)):
        case_id = str(verdict.get("case_id", ""))
        if case_id and case_id not in latest:
            latest[case_id] = verdict
    return latest


def _current_reports(
    reports: list[dict[str, object]],
    latest_verdicts: list[dict[str, object]],
) -> list[dict[str, object]]:
    failing_run_ids = {
        str(verdict["run_id"])
        for verdict in latest_verdicts
        if verdict.get("verdict") == "fail"
    }
    return [report for report in reports if str(report.get("source_run_id", "")) in failing_run_ids]


def _reports_table(reports: list[dict[str, object]]) -> str:
    if not reports:
        return (
            "<div class=\"empty-state\">"
            "<strong>No vulnerability report drafts yet.</strong>"
            "<span>Latest deterministic evidence is clean; confirmed reports stay empty until a deployed run proves otherwise.</span>"
            "</div>"
        )
    rows = "\n".join(
        "<tr>"
        f"<td><a class=\"run-link\" href=\"/runs/{escape(str(report['source_run_id']))}\">"
        f"{escape(str(report['vulnerability_id']))}</a></td>"
        f"<td>{escape(str(report['severity']))} / {escape(str(report['impact_domain']))}</td>"
        f"<td>{_status_badge(report['status'])}</td>"
        "</tr>"
        for report in reports
    )
    return (
        "<table><caption class=\"sr-only\">Current vulnerability report drafts</caption>"
        "<thead><tr><th scope=\"col\">Report</th><th scope=\"col\">Severity / Impact</th>"
        f"<th scope=\"col\">Status</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _site_scans_table(scans: list[dict[str, object]]) -> str:
    if not scans:
        return (
            "<div class=\"empty-state\">"
            "<strong>No authorized site scans recorded yet.</strong>"
            "<span>Add an owned or explicitly authorized host to the allowlist, then run a passive scan.</span>"
            "</div>"
        )
    rows = "\n".join(
        "<tr>"
        f"<td><a class=\"run-link\" href=\"/site-scans/{escape(str(scan['scan_id']))}\">"
        f"{escape(str(scan['scan_id']))}</a></td>"
        f"<td>{escape(str(scan['target_url']))}</td>"
        f"<td>{escape(str(scan['scan_mode']))}</td>"
        f"<td>{_status_badge(scan['status'])}</td>"
        f"<td>{_status_badge(scan['highest_severity'])}</td>"
        f"<td>{escape(str(scan['finding_count']))}</td>"
        "</tr>"
        for scan in scans
    )
    return (
        "<table><caption class=\"sr-only\">Latest authorized passive site scans</caption>"
        "<thead><tr><th scope=\"col\">Scan</th><th scope=\"col\">Target</th>"
        "<th scope=\"col\">Mode</th><th scope=\"col\">Status</th>"
        "<th scope=\"col\">Highest</th><th scope=\"col\">Findings</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _site_findings_table(findings: list[dict[str, object]]) -> str:
    if not findings:
        return (
            "<div class=\"empty-state\">"
            "<strong>No passive findings recorded.</strong>"
            "<span>The entry response passed the currently configured passive checks.</span>"
            "</div>"
        )
    rows = "\n".join(
        "<tr>"
        f"<td>{_status_badge(finding['severity'])}</td>"
        f"<td><strong>{escape(str(finding['title']))}</strong><br>"
        f"<span class=\"muted-line\">{escape(str(finding['check_id']))}</span></td>"
        f"<td>{escape(str(finding['evidence']))}</td>"
        f"<td>{escape(str(finding['remediation']))}</td>"
        "</tr>"
        for finding in findings
    )
    return (
        "<table><caption class=\"sr-only\">Passive site scan findings</caption>"
        "<thead><tr><th scope=\"col\">Severity</th><th scope=\"col\">Finding</th>"
        "<th scope=\"col\">Evidence</th><th scope=\"col\">Remediation</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
{_page_css()}
  </style>
</head>
<body>
  <div class="left-rail" aria-hidden="true"><span></span><span></span><span></span></div>
  <main>{body}</main>
  <script>{_page_script()}</script>
</body>
</html>"""


def _page_css() -> str:
    return """
    @import url("https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Share+Tech+Mono&display=swap");

    :root {
      color-scheme: dark;
      --void: #050506;
      --panel: rgba(16, 16, 19, .86);
      --panel-strong: rgba(25, 25, 30, .94);
      --steel: rgba(255, 255, 255, .12);
      --steel-2: rgba(255, 255, 255, .20);
      --blood: #6f0711;
      --red: #dc1128;
      --red-hot: #ff334a;
      --red-soft: #ff9aa7;
      --bone: #f3f1ee;
      --muted: #a7a2a2;
      --dim: #777277;
      --green: #39d98a;
      --amber: #f7c948;
      --cyan: #4dd4ff;
      --shadow: 0 20px 70px rgba(0, 0, 0, .45);
      --glow: 0 0 32px rgba(220, 17, 40, .18);
      --font-command: "Chakra Petch", "Bahnschrift", "Arial Narrow", "Segoe UI", sans-serif;
      --font-data: "Share Tech Mono", "Cascadia Mono", "Consolas", monospace;
    }

    * { box-sizing: border-box; }

    body {
      min-height: 100vh;
      margin: 0;
      color: var(--bone);
      background:
        radial-gradient(circle at 84% -18%, rgba(220, 17, 40, .28), transparent 360px),
        radial-gradient(circle at 8% 12%, rgba(111, 7, 17, .20), transparent 420px),
        linear-gradient(rgba(255,255,255,.028) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
        var(--void);
      background-size: auto, auto, 44px 44px, 44px 44px, auto;
      font-family: var(--font-command);
      letter-spacing: 0;
    }

    body.dense main { max-width: 1320px; }
    body.dense th,
    body.dense td { padding-top: 8px; padding-bottom: 8px; }
    body.dense .panel { padding-top: 18px; padding-bottom: 18px; }

    .left-rail {
      position: fixed;
      inset: 0 auto 0 0;
      width: 8px;
      background: linear-gradient(180deg, var(--red), rgba(220, 17, 40, .22), transparent 72%);
      z-index: 0;
    }

    .left-rail span {
      display: block;
      height: 96px;
      margin: 16px 3px;
      background: rgba(255,255,255,.45);
    }

    main {
      position: relative;
      z-index: 1;
      max-width: 1240px;
      margin: 0 auto;
      padding: 22px 30px 48px;
    }

    a { color: var(--red-soft); text-decoration: none; }
    a:hover { color: #fff; text-decoration: underline; }
    a:focus-visible,
    button:focus-visible,
    input:focus-visible { outline: 2px solid var(--red-hot); outline-offset: 3px; }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    .command-header {
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      align-items: stretch;
      justify-content: space-between;
      gap: 14px;
      min-height: 66px;
      border: 1px solid var(--steel);
      border-top: 2px solid var(--red);
      background:
        linear-gradient(90deg, rgba(111, 7, 17, .36), transparent 62%),
        rgba(7, 7, 8, .82);
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }

    .brand-lockup {
      display: inline-flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
      padding: 13px 18px;
      color: var(--bone);
    }

    .brand-lockup:hover { color: var(--bone); text-decoration: none; }
    .brand-lockup strong { display: block; font-size: 19px; text-transform: uppercase; }
    .brand-lockup small {
      display: block;
      color: var(--muted);
      font-family: var(--font-data);
      font-size: 11px;
      text-transform: uppercase;
    }

    .brand-sigil {
      width: 32px;
      height: 32px;
      border: 1px solid var(--red-hot);
      background:
        linear-gradient(135deg, transparent 0 37%, var(--red) 37% 52%, transparent 52%),
        radial-gradient(circle, rgba(255,255,255,.18), transparent 62%),
        #120407;
      box-shadow: inset 0 0 0 5px #050506;
      clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%);
      flex: 0 0 auto;
    }

    .header-meta {
      display: grid;
      grid-auto-flow: column;
      align-items: stretch;
      border-left: 1px solid var(--steel);
    }

    .header-meta span,
    .header-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 88px;
      padding: 0 14px;
      border-left: 1px solid var(--steel);
      border-right: 0;
      color: #ffd4da;
      background: rgba(255, 255, 255, .03);
      font-size: 12px;
      font-weight: 800;
      font-family: var(--font-data);
      text-transform: uppercase;
    }

    .header-link { min-height: 66px; }

    .command-slab {
      position: relative;
      border: 1px solid var(--steel);
      border-top: 2px solid rgba(220, 17, 40, .82);
      background:
        linear-gradient(135deg, rgba(220, 17, 40, .13), transparent 34%),
        linear-gradient(180deg, rgba(28, 28, 33, .96), rgba(9, 9, 11, .96));
      box-shadow: var(--shadow), var(--glow);
      overflow: hidden;
    }

    .command-slab::after {
      content: "";
      position: absolute;
      inset: 0;
      border-top: 1px solid rgba(255, 255, 255, .08);
      background: linear-gradient(120deg, transparent 0 74%, rgba(220, 17, 40, .10) 74% 100%);
      pointer-events: none;
    }

    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(340px, .85fr);
      gap: 26px;
      margin-top: 16px;
      padding: 30px;
    }

    .hero.compact {
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
    }

    .hero-primary { min-width: 0; }

    .eyebrow,
    .section-code {
      color: var(--red-soft);
      font-family: var(--font-data);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }

    h1 {
      max-width: 780px;
      margin: 0 0 14px;
      font-size: 50px;
      font-weight: 700;
      line-height: 1.03;
      text-transform: uppercase;
      text-wrap: balance;
    }

    h2 {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      text-transform: uppercase;
    }

    p { color: #d5d2cf; }
    .hero-copy { max-width: 720px; margin: 0 0 22px; color: #d5d2cf; line-height: 1.5; }

    .recommendation {
      padding: 8px 0 10px 16px;
      border-left: 5px solid var(--red);
      text-shadow: 0 0 22px rgba(220, 17, 40, .24);
    }

    .recommendation-pass { border-color: var(--green); }
    .recommendation-warn { border-color: var(--amber); }
    .recommendation-block { border-color: var(--red); }

    .target-list {
      display: grid;
      grid-template-columns: minmax(150px, .28fr) minmax(0, 1fr);
      gap: 1px;
      margin: 0;
      border: 1px solid var(--steel);
      background: rgba(255,255,255,.08);
    }

    .target-list div {
      min-width: 0;
      padding: 12px 14px;
      background: rgba(5, 5, 6, .64);
    }

    dt {
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
      font-family: var(--font-data);
      text-transform: uppercase;
    }

    dd {
      max-width: 100%;
      margin: 4px 0 0;
      overflow-wrap: anywhere;
      color: var(--bone);
      font-size: 15px;
      font-weight: 800;
      font-family: var(--font-data);
    }

    .readiness-stack { display: grid; align-content: start; gap: 12px; }

    .metric-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1px;
      margin: 0;
      border: 1px solid var(--steel);
      background: rgba(255,255,255,.08);
    }

    .metric-grid div {
      min-width: 0;
      padding: 17px;
      background:
        linear-gradient(90deg, rgba(220, 17, 40, .12), transparent 76%),
        rgba(5, 5, 6, .70);
    }

    .metric-grid dd { font-size: 34px; line-height: 1; }
    .metric-grid dd { font-family: var(--font-data); }

    .system-line {
      display: grid;
      gap: 1px;
      border: 1px solid var(--steel);
      background: rgba(255,255,255,.08);
    }

    .system-line span {
      padding: 9px 12px;
      background: rgba(7, 7, 8, .72);
      color: #cfcaca;
      font-family: var(--font-data);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .command-strip {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
      padding: 13px;
      border: 1px solid var(--steel);
      background: rgba(9, 9, 10, .72);
      box-shadow: 0 14px 46px rgba(0,0,0,.30);
      backdrop-filter: blur(14px);
    }

    .strip-copy {
      display: grid;
      min-width: 190px;
      margin-right: auto;
    }

    .site-scan-form {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      min-width: min(100%, 620px);
    }

    .site-scan-form label {
      color: var(--muted);
      font-family: var(--font-data);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }

    button {
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 9px;
      min-height: 40px;
      padding: 9px 14px;
      border: 1px solid var(--steel-2);
      border-left: 2px solid var(--red);
      border-radius: 4px;
      background:
        linear-gradient(135deg, rgba(220,17,40,.12), transparent 58%),
        rgba(18, 18, 21, .92);
      color: var(--bone);
      cursor: pointer;
      font-family: var(--font-command);
      font-size: 15px;
      font-weight: 900;
      text-transform: uppercase;
      transition: transform .16s ease, border-color .16s ease, background .16s ease;
    }

    button:hover { border-color: var(--red-hot); background-color: #1a0c10; transform: translateY(-1px); }
    button[disabled],
    button[aria-busy="true"] {
      border-color: rgba(255, 51, 74, .78);
      background:
        linear-gradient(90deg, rgba(220,17,40,.30), rgba(220,17,40,.06), rgba(220,17,40,.30)),
        rgba(18, 18, 21, .96);
      color: #ffd4da;
      cursor: wait;
      opacity: 1;
      transform: none;
    }

    .button-spinner {
      display: none;
      width: 13px;
      height: 13px;
      border: 2px solid rgba(255, 255, 255, .28);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin .72s linear infinite;
      flex: 0 0 auto;
    }

    button[aria-busy="true"] .button-spinner { display: inline-block; }
    .button-primary { background: linear-gradient(135deg, #b10d21, #620610); border-color: var(--red-hot); }

    .run-status {
      display: grid;
      grid-template-columns: auto auto minmax(180px, 1fr);
      align-items: center;
      gap: 10px;
      width: 100%;
      min-height: 46px;
      padding: 10px 12px;
      border: 1px solid rgba(255, 51, 74, .52);
      border-left: 3px solid var(--red-hot);
      background:
        linear-gradient(90deg, rgba(220, 17, 40, .18), transparent 72%),
        rgba(7, 7, 8, .86);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.04), 0 0 28px rgba(220,17,40,.14);
    }

    .run-status[hidden] { display: none; }

    .run-status strong {
      color: var(--bone);
      font-size: 13px;
      font-weight: 900;
      text-transform: uppercase;
    }

    .run-status span:last-child {
      color: #ffd4da;
      font-family: var(--font-data);
      font-size: 12px;
    }

    .run-status-pulse {
      width: 11px;
      height: 11px;
      border: 1px solid #fff;
      border-radius: 50%;
      background: var(--red-hot);
      box-shadow: 0 0 0 0 rgba(255, 51, 74, .76);
      animation: pulse 1.05s ease-out infinite;
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    @keyframes pulse {
      70% { box-shadow: 0 0 0 10px rgba(255, 51, 74, 0); }
      100% { box-shadow: 0 0 0 0 rgba(255, 51, 74, 0); }
    }

    .panel {
      margin-top: 16px;
      padding: 20px;
      border: 1px solid var(--steel);
      border-top: 2px solid rgba(220, 17, 40, .58);
      border-radius: 8px;
      background:
        linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.018)),
        rgba(8, 8, 10, .82);
      box-shadow: 0 18px 52px rgba(0,0,0,.32);
    }

    .posture-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }

    .posture-card {
      display: grid;
      gap: 5px;
      min-width: 0;
      padding: 14px;
      border: 1px solid var(--steel);
      border-left: 3px solid var(--red);
      border-radius: 6px;
      background: rgba(6, 6, 7, .74);
    }

    .posture-card > span,
    .posture-card small {
      color: var(--muted);
      font-family: var(--font-data);
      font-size: 11px;
      text-transform: uppercase;
    }

    .posture-card strong {
      color: var(--bone);
      font-family: var(--font-data);
      font-size: 21px;
    }

    .posture-card > span + span,
    .posture-card strong + span {
      color: #d5d2cf;
      font-family: var(--font-command);
      line-height: 1.35;
    }

    .section-heading {
      display: flex;
      align-items: end;
      gap: 12px;
      margin-bottom: 14px;
      padding-left: 10px;
      border-left: 3px solid var(--red);
    }

    .table-tools {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }

    .table-tools label {
      color: var(--muted);
      font-family: var(--font-data);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }

    input[type="search"],
    input[type="url"] {
      min-height: 38px;
      min-width: min(360px, 100%);
      padding: 8px 10px;
      border: 1px solid var(--steel-2);
      border-left: 2px solid var(--red);
      border-radius: 4px;
      background: rgba(7, 7, 8, .90);
      color: var(--bone);
      font-family: var(--font-data);
    }

    table {
      width: 100%;
      overflow: hidden;
      border-collapse: collapse;
      border: 1px solid var(--steel);
      border-radius: 6px;
      background: rgba(8, 8, 9, .92);
    }

    th, td {
      padding: 11px 14px;
      border-bottom: 1px solid rgba(255,255,255,.08);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }

    th {
      color: #ffd4da;
      font-family: var(--font-data);
      background: linear-gradient(180deg, rgba(70, 8, 16, .72), rgba(18, 8, 10, .92));
      font-size: 11px;
      text-transform: uppercase;
    }

    td { font-family: var(--font-data); }

    tr:last-child td { border-bottom: 0; }
    tbody tr:hover td { background: rgba(220, 17, 40, .075); }

    .run-link,
    .risk-family {
      color: #fff;
      font-weight: 900;
      text-transform: uppercase;
    }

    .export-cell {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .export-cell a,
    .export-nav a {
      padding: 7px 9px;
      border: 1px solid var(--steel-2);
      border-left: 2px solid var(--red);
      border-radius: 4px;
      background: rgba(13, 13, 16, .85);
      color: #ffd4da;
      font-family: var(--font-data);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }

    .export-nav { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }

    .status-badge,
    .count-pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 4px 8px;
      border: 1px solid var(--steel-2);
      border-radius: 999px;
      background: rgba(17, 17, 20, .88);
      color: #d9d6d2;
      font-family: var(--font-data);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .status-pass,
    .count-pass { border-color: rgba(57, 217, 138, .72); color: var(--green); }
    .status-fail,
    .count-fail,
    .status-critical-failure { border-color: var(--red-hot); color: #ff9aa7; }
    .status-inconclusive,
    .status-partial,
    .count-inconclusive,
    .count-partial { border-color: var(--amber); color: var(--amber); }
    .status-completed { border-color: rgba(77, 212, 255, .5); color: var(--cyan); }

    .coverage-meter {
      display: grid;
      grid-template-columns: 64px minmax(80px, 1fr);
      align-items: center;
      gap: 10px;
      min-width: 160px;
    }

    .coverage-meter span {
      color: var(--bone);
      font-weight: 900;
    }

    .coverage-meter div {
      height: 8px;
      border: 1px solid var(--steel-2);
      border-radius: 999px;
      background: #050506;
      overflow: hidden;
    }

    .coverage-meter i {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--red), var(--green));
    }

    .empty-state {
      display: grid;
      gap: 5px;
      padding: 16px;
      border: 1px solid var(--steel);
      border-left: 3px solid var(--red);
      border-radius: 6px;
      background: rgba(9, 9, 10, .74);
    }

    .empty-state strong { color: var(--bone); }
    .empty-state span { color: var(--muted); }
    .muted-line { color: var(--muted); font-size: 11px; }

    .evidence-block {
      display: grid;
      gap: 10px;
      margin-bottom: 16px;
    }

    .evidence-block h3,
    .evidence-block h4 {
      margin: 0;
      text-transform: uppercase;
    }

    .evidence-block h3 { font-size: 18px; }
    .evidence-block h4 {
      color: var(--muted);
      font-family: var(--font-data);
      font-size: 11px;
    }

    pre {
      overflow: auto;
      margin: 0;
      padding: 16px;
      border: 1px solid var(--steel);
      border-left: 3px solid var(--red);
      border-radius: 6px;
      background: rgba(6, 6, 7, .90);
      color: #e5e2de;
      font-family: var(--font-data);
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    [hidden] { display: none !important; }

    @media (max-width: 900px) {
      main { padding: 18px 18px 36px 28px; }
      .command-header { position: static; flex-direction: column; }
      .header-meta { grid-auto-flow: row; border-left: 0; }
      .header-meta span, .header-link { min-height: 36px; border-top: 1px solid var(--steel); }
      .hero,
      .hero.compact { grid-template-columns: 1fr; }
      .target-list { grid-template-columns: 1fr; }
      .posture-grid { grid-template-columns: 1fr; }
      h1 { font-size: 37px; }
      table { display: block; overflow-x: auto; }
      .export-nav { justify-content: flex-start; }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: .01ms !important;
      }
    }
    """


def _page_script() -> str:
    return """
    (() => {
      const densityKey = "agentforge-density";
      if (localStorage.getItem(densityKey) === "dense") {
        document.body.classList.add("dense");
      }

      const updateCount = (table) => {
        const counter = document.querySelector(`[data-count-visible="#${table.id}"]`);
        if (!counter) return;
        const rows = [...table.querySelectorAll("tbody tr")];
        const visible = rows.filter((row) => !row.hidden).length;
        counter.textContent = `${visible} visible`;
      };

      document.querySelectorAll("[data-filter-target]").forEach((input) => {
        const table = document.querySelector(input.dataset.filterTarget);
        if (!table) return;
        const applyFilter = () => {
          const query = input.value.trim().toLowerCase();
          table.querySelectorAll("tbody tr").forEach((row) => {
            const haystack = (row.dataset.filterText || row.textContent || "").toLowerCase();
            row.hidden = query.length > 0 && !haystack.includes(query);
          });
          updateCount(table);
        };
        input.addEventListener("input", applyFilter);
        applyFilter();
      });

      document.querySelectorAll("[data-toggle-density]").forEach((button) => {
        button.addEventListener("click", () => {
          document.body.classList.toggle("dense");
          localStorage.setItem(densityKey, document.body.classList.contains("dense") ? "dense" : "comfortable");
        });
      });

      document.querySelectorAll("form[data-run-suite]").forEach((form) => {
        form.addEventListener("submit", (event) => {
          if (form.dataset.submitting === "true") {
            event.preventDefault();
            return;
          }
          form.dataset.submitting = "true";
          const suite = form.dataset.runSuite || "selected";
          const status = document.querySelector("[data-run-status]");
          const statusCopy = document.querySelector("[data-run-status-copy]");
          const submitter = event.submitter || form.querySelector("button[type='submit']");
          document.querySelectorAll("form[data-run-suite] button[type='submit']").forEach((button) => {
            button.disabled = true;
          });
          if (submitter) {
            const label = submitter.querySelector(".button-label");
            submitter.setAttribute("aria-busy", "true");
            if (label) {
              label.textContent = submitter.dataset.loadingLabel || "Running Suite";
            }
          }
          if (status) {
            status.hidden = false;
          }
          if (statusCopy) {
            statusCopy.textContent = `${suite.toUpperCase()} suite is executing against the deployed target. This can take several seconds.`;
          }
          document.body.classList.add("suite-running");
        });
      });
    })();
    """
