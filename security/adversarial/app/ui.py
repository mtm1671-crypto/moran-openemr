"""FastAPI operator UI for Week 3 adversarial runs."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from html import escape
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .config import Settings
from .export_run import build_run_export, render_run_markdown
from .models import (
    AuditAction,
    AuditEvent,
    AuthorizedScope,
    Client,
    FindingStatus,
    Project,
    ReportStatus,
    RunMode,
    ScanJob,
    ScanJobStatus,
    SiteScanMode,
    utc_now,
)
from .reporting import dashboard_summary
from .run_store import RunStore
from .run_week3_eval import run_suite
from .scope_registry import ensure_default_scope, resolve_scope_for_scan
from .site_scanner import PassiveSiteScanner

OPERATOR_SESSION_COOKIE = "agentforge_operator_session"


def create_app() -> FastAPI:
    settings = Settings()
    store = RunStore(
        settings.sqlite_path,
        private_path=settings.private_sqlite_path,
        evidence_retention_days=settings.evidence_retention_days,
    )
    app = FastAPI(title="AgentForge Adversarial Platform", version="0.1.0")
    rate_buckets: dict[str, list[float]] = {}

    @app.middleware("http")
    async def apply_operator_rate_limit(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if _is_rate_limited(request, settings, rate_buckets):
            return JSONResponse({"detail": "operator rate limit exceeded"}, status_code=429)
        return await call_next(request)

    @app.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    @app.middleware("http")
    async def require_operator_auth(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if _is_public_path(request.url.path) or _is_operator_authenticated(request, settings):
            return await call_next(request)
        if request.method == "GET" and not request.url.path.endswith((".json", ".md")):
            return RedirectResponse("/login", status_code=303)
        return JSONResponse({"detail": "operator authentication required"}, status_code=401)

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        ready, message = store.readiness()
        status_code = 200 if ready else 503
        return JSONResponse(
            {"ready": ready, "message": message, "sqlite_path": str(settings.sqlite_path)},
            status_code=status_code,
        )

    @app.get("/login", response_class=HTMLResponse)
    def login_form() -> str:
        if not _operator_auth_enabled(settings):
            return _page(
                "Operator Auth Disabled",
                """
                <section class="hero compact command-slab">
                  <div>
                    <p class="eyebrow">Operator access</p>
                    <h1>Auth disabled</h1>
                    <p class="hero-copy">Set ADVERSARIAL_OPERATOR_TOKEN before exposing this service to clients.</p>
                  </div>
                </section>
                """,
            )
        return _page(
            "Operator Login",
            """
            <section class="hero compact command-slab">
              <div>
                <p class="eyebrow">Operator access // protected control plane</p>
                <h1>Operator Login</h1>
              </div>
            </section>
            <section class="command-strip" aria-label="Operator login">
              <form class="site-scan-form" method="post" action="/login">
                <label for="operator-token">Token</label>
                <input id="operator-token" name="operator_token" type="password" autocomplete="current-password" required>
                <button class="button-primary" type="submit">
                  <span class="button-label">Enter</span>
                </button>
              </form>
            </section>
            """,
        )

    @app.post("/login")
    async def login(request: Request) -> Response:
        body = (await request.body()).decode()
        params = parse_qs(body)
        submitted = params.get("operator_token", [""])[0]
        if not _token_matches(submitted, settings):
            _record_audit(
                store,
                request,
                AuditAction.LOGIN,
                "operator_session",
                "login",
                success=False,
            )
            return HTMLResponse(
                _page(
                    "Login failed",
                    """
                    <section class="hero compact command-slab">
                      <div>
                        <p class="eyebrow">Operator access</p>
                        <h1>Login failed</h1>
                        <p class="hero-copy">The supplied operator token was not accepted.</p>
                      </div>
                    </section>
                    """,
                ),
                status_code=401,
            )
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            OPERATOR_SESSION_COOKIE,
            _new_session_cookie(settings),
            max_age=settings.operator_session_ttl_seconds,
            httponly=True,
            secure=settings.operator_cookie_secure,
            samesite="strict",
        )
        _record_audit(store, request, AuditAction.LOGIN, "operator_session", "login")
        return response

    @app.post("/logout")
    async def logout(request: Request) -> Response:
        body = (await request.body()).decode()
        csrf_response = _csrf_failure_response(request, settings, parse_qs(body))
        if csrf_response:
            return csrf_response
        _record_audit(store, request, AuditAction.LOGOUT, "operator_session", "logout")
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(OPERATOR_SESSION_COOKIE)
        return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> str:
        store.initialize()
        ensure_default_scope(store, settings)
        runs = store.latest_runs(limit=20)
        cases = store.cases()
        verdicts = store.verdicts()
        reports = store.reports()
        observations = store.observations()
        snapshots = store.snapshots()
        site_scans = store.site_scan_runs(limit=10)
        scopes = store.authorized_scopes()
        clients = store.clients()
        projects = store.projects()
        scan_jobs = store.scan_jobs(limit=10)
        audit_events = store.audit_events(limit=12)
        csrf = _csrf_token_for_request(request, settings)
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
                {_csrf_input(csrf)}
                <button type="submit" data-loading-label="Running Smoke">
                  <span class="button-label">Run Smoke</span>
                  <span class="button-spinner" aria-hidden="true"></span>
                </button>
              </form>
              <form method="post" action="/runs/seed" data-run-suite="seed">
                {_csrf_input(csrf)}
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
                {_csrf_input(csrf)}
                <label for="site-scope-id">Scope</label>
                <select id="site-scope-id" name="scope_id" required>
                  {_scope_options(scopes)}
                </select>
                <label for="site-target-url">Allowlisted URL</label>
                <input id="site-target-url" name="target_url" type="url" placeholder="https://example.your-domain.com" required>
                <label for="site-scan-mode">Mode</label>
                <select id="site-scan-mode" name="scan_mode">
                  <option value="passive-http">Passive</option>
                  <option value="low-priv-authenticated">Low-Priv Auth</option>
                </select>
                <button type="submit" data-loading-label="Scanning Site">
                  <span class="button-label">Run Site Scan</span>
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
                <span class="section-code">CLIENT-01</span>
                <h2>Client Scopes</h2>
              </div>
              {_scope_admin_panel(clients, projects, scopes, csrf, settings)}
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
                <span class="section-code">QUEUE-07</span>
                <h2>Scan Jobs</h2>
              </div>
              {_scan_jobs_table(scan_jobs, csrf)}
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">REPORT-04</span>
                <h2>Findings</h2>
              </div>
              {_reports_table(current_reports, csrf)}
            </section>
            <section class="panel">
              <div class="section-heading">
                <span class="section-code">AUDIT-08</span>
                <h2>Audit Log</h2>
              </div>
              {_audit_table(audit_events)}
            </section>
            """,
        )

    @app.post("/runs/{suite}")
    async def start_run(suite: str, request: Request) -> Response:
        body = (await request.body()).decode()
        csrf_response = _csrf_failure_response(request, settings, parse_qs(body))
        if csrf_response:
            return csrf_response
        if suite not in {"smoke", "seed", "regression"}:
            return HTMLResponse(_page("Invalid suite", "<h1>Invalid suite</h1>"), status_code=400)
        try:
            settings.validate_ready_for_run()
            run_ids = run_suite(
                settings=settings,
                suite=suite,
                run_mode=RunMode.REPORT_ONLY,
            )
            _record_audit(
                store,
                request,
                AuditAction.RUN_SUITE,
                "suite",
                suite,
                metadata={"run_ids": run_ids},
            )
        except Exception as exc:
            _record_audit(
                store,
                request,
                AuditAction.RUN_SUITE,
                "suite",
                suite,
                success=False,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )
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
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        scope_id = params.get("scope_id", [""])[0].strip()
        target_url = params.get("target_url", [""])[0].strip()
        scan_mode_value = params.get("scan_mode", [SiteScanMode.PASSIVE_HTTP.value])[0].strip()
        if not target_url:
            return HTMLResponse(_page("Invalid target", "<h1>Invalid target</h1>"), status_code=400)
        job: ScanJob | None = None
        try:
            scan_mode = SiteScanMode(scan_mode_value)
            store.initialize()
            scope = resolve_scope_for_scan(
                store=store,
                settings=settings,
                scope_id=scope_id,
                target_url=target_url,
                mode=scan_mode,
            )
            job = ScanJob(
                scope_id=scope.scope_id,
                client_id=scope.client_id,
                project_id=scope.project_id,
                target_url=target_url,
                scan_mode=scan_mode,
                status=ScanJobStatus.QUEUED,
                metadata={"authorization_note": scope.authorization_note},
            )
            store.save_scan_job(job)
            _record_audit(
                store,
                request,
                AuditAction.QUEUE_SITE_SCAN,
                "scan_job",
                job.job_id,
                metadata={"scope_id": scope.scope_id, "target_url": target_url},
            )
            job = job.model_copy(update={"status": ScanJobStatus.RUNNING, "started_at": utc_now()})
            store.save_scan_job(job)
            scan, findings = PassiveSiteScanner(settings).scan(
                target_url,
                mode=scan_mode,
                scope=scope,
            )
            store.save_site_scan_run(scan)
            store.save_site_scan_findings(findings)
            job = job.model_copy(
                update={
                    "status": ScanJobStatus.COMPLETED,
                    "completed_at": utc_now(),
                    "scan_id": scan.scan_id,
                }
            )
            store.save_scan_job(job)
            _record_audit(
                store,
                request,
                AuditAction.COMPLETE_SITE_SCAN,
                "site_scan",
                scan.scan_id,
                metadata={"job_id": job.job_id, "finding_count": scan.finding_count},
            )
        except Exception as exc:
            if job is not None:
                failed_job = job.model_copy(
                    update={
                        "status": ScanJobStatus.FAILED,
                        "completed_at": utc_now(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                store.save_scan_job(failed_job)
            _record_audit(
                store,
                request,
                AuditAction.QUEUE_SITE_SCAN,
                "site_scan",
                target_url or "unknown",
                success=False,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )
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
    def site_scan_detail(scan_id: str, request: Request) -> Response:
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
        csrf = _csrf_token_for_request(request, settings)
        return HTMLResponse(
            _page(
                f"Site Scan {scan_id}",
                f"""
            <header class="command-header">
              <a class="brand-lockup" href="/">
                <span class="brand-sigil" aria-hidden="true"></span>
                <span>
                  <strong>AgentForge</strong>
                  <small>Authorized Site Scan</small>
                </span>
              </a>
              <a class="header-link" href="/">Risk overview</a>
            </header>
            <section class="hero compact command-slab">
              <div>
                <p class="eyebrow">Authorized site scan // scoped target</p>
                <h1>Site Scan {escape(scan_id)}</h1>
              </div>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">SUMMARY</span><h2>Scan Summary</h2></div>
              <pre>{escape(str(scans[0]))}</pre>
            </section>
            <section class="panel">
              <div class="section-heading"><span class="section-code">FINDINGS</span><h2>Findings</h2></div>
              {_site_findings_table(findings, csrf)}
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

    @app.post("/clients")
    async def create_client(request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        name = params.get("name", [""])[0].strip()
        if not name:
            return HTMLResponse(_page("Invalid client", "<h1>Client name required</h1>"), status_code=400)
        client = Client(name=name)
        store.initialize()
        ensure_default_scope(store, settings)
        store.save_client(client)
        _record_audit(store, request, AuditAction.CREATE_CLIENT, "client", client.client_id)
        return RedirectResponse("/", status_code=303)

    @app.post("/projects")
    async def create_project(request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        client_id = params.get("client_id", [""])[0].strip()
        name = params.get("name", [""])[0].strip()
        if not client_id or not name:
            return HTMLResponse(
                _page("Invalid project", "<h1>Client and project name required</h1>"),
                status_code=400,
            )
        store.initialize()
        ensure_default_scope(store, settings)
        if client_id not in {str(client.get("client_id")) for client in store.clients()}:
            return HTMLResponse(_page("Invalid project", "<h1>Client not found</h1>"), status_code=400)
        project = Project(client_id=client_id, name=name)
        store.save_project(project)
        _record_audit(
            store,
            request,
            AuditAction.CREATE_PROJECT,
            "project",
            project.project_id,
            metadata={"client_id": client_id},
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/scopes")
    async def create_scope(request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        project_id = params.get("project_id", [""])[0].strip()
        store.initialize()
        ensure_default_scope(store, settings)
        projects = store.projects()
        project = next((item for item in projects if item.get("project_id") == project_id), None)
        if project is None:
            return HTMLResponse(_page("Invalid scope", "<h1>Project required</h1>"), status_code=400)
        allowed_hosts = _split_form_list(params.get("allowed_hosts", [""])[0])
        unknown_hosts = [host for host in allowed_hosts if host not in set(settings.allowed_hosts)]
        if unknown_hosts:
            message = f"<h1>Host must be in ADVERSARIAL_ALLOWED_HOSTS</h1><p>{escape(', '.join(unknown_hosts))}</p>"
            return HTMLResponse(_page("Invalid scope", message), status_code=400)
        try:
            allowed_modes = [
                SiteScanMode(value)
                for value in params.get("allowed_scan_modes", [SiteScanMode.PASSIVE_HTTP.value])
            ]
            expires_at = _parse_optional_datetime(params.get("authorization_expires_at", [""])[0])
            scope = AuthorizedScope(
                client_id=str(project["client_id"]),
                project_id=project_id,
                name=params.get("name", [""])[0].strip() or "Authorized client scope",
                allowed_hosts=allowed_hosts,
                allowed_scan_modes=allowed_modes,
                excluded_paths=_split_form_list(params.get("excluded_paths", [""])[0]),
                max_urls=int(params.get("max_urls", ["12"])[0] or "12"),
                authorization_note=params.get("authorization_note", [""])[0].strip()
                or "Operator attests this scope is explicitly authorized.",
                authorization_expires_at=expires_at,
                operator_contact=params.get("operator_contact", [""])[0].strip() or None,
                rules_of_engagement_ref=params.get("rules_of_engagement_ref", [""])[0].strip() or None,
            )
        except ValueError as exc:
            return HTMLResponse(
                _page("Invalid scope", f"<h1>Invalid scope</h1><p>{escape(str(exc))}</p>"),
                status_code=400,
            )
        store.save_authorized_scope(scope)
        _record_audit(
            store,
            request,
            AuditAction.CREATE_SCOPE,
            "authorized_scope",
            scope.scope_id,
            metadata={"allowed_hosts": allowed_hosts, "project_id": project_id},
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/scopes/{scope_id}/deactivate")
    async def deactivate_scope(scope_id: str, request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        store.initialize()
        try:
            store.deactivate_scope(scope_id)
        except ValueError:
            return HTMLResponse(_page("Scope not found", "<h1>Scope not found</h1>"), status_code=404)
        _record_audit(store, request, AuditAction.DEACTIVATE_SCOPE, "authorized_scope", scope_id)
        return RedirectResponse("/", status_code=303)

    @app.post("/reports/{vulnerability_id}/status")
    async def update_report_status(vulnerability_id: str, request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        try:
            store.initialize()
            status = ReportStatus(params.get("status", [ReportStatus.NEEDS_HUMAN_REVIEW.value])[0])
            updated = store.update_report_status(
                vulnerability_id,
                status,
                params.get("status_note", [""])[0].strip(),
            )
        except ValueError as exc:
            return HTMLResponse(_page("Report update failed", f"<h1>{escape(str(exc))}</h1>"), status_code=400)
        _record_audit(
            store,
            request,
            AuditAction.UPDATE_REPORT_STATUS,
            "vulnerability_report",
            vulnerability_id,
            metadata={"status": updated.status},
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/site-findings/{finding_id}/status")
    async def update_finding_status(finding_id: str, request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        try:
            store.initialize()
            status = FindingStatus(params.get("status", [FindingStatus.NEEDS_REVIEW.value])[0])
            updated = store.update_site_scan_finding_status(
                finding_id,
                status,
                params.get("status_note", [""])[0].strip(),
                params.get("retest_scan_id", [""])[0].strip() or None,
            )
        except ValueError as exc:
            return HTMLResponse(_page("Finding update failed", f"<h1>{escape(str(exc))}</h1>"), status_code=400)
        _record_audit(
            store,
            request,
            AuditAction.UPDATE_FINDING_STATUS,
            "site_scan_finding",
            finding_id,
            metadata={"status": updated.status},
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/scan-jobs/{job_id}/cancel")
    async def cancel_scan_job(job_id: str, request: Request) -> Response:
        params = parse_qs((await request.body()).decode())
        csrf_response = _csrf_failure_response(request, settings, params)
        if csrf_response:
            return csrf_response
        try:
            store.initialize()
            updated = store.cancel_scan_job(job_id)
        except ValueError:
            return HTMLResponse(_page("Scan job not found", "<h1>Scan job not found</h1>"), status_code=404)
        _record_audit(
            store,
            request,
            AuditAction.CANCEL_SCAN_JOB,
            "scan_job",
            job_id,
            metadata={"status": updated.status},
        )
        return RedirectResponse("/", status_code=303)

    @app.get("/client-reports/{scope_id}.json")
    def client_report_json(scope_id: str) -> Response:
        store.initialize()
        try:
            return JSONResponse(_client_report_payload(scope_id, store))
        except ValueError:
            return JSONResponse({"detail": "scope not found"}, status_code=404)

    @app.get("/client-reports/{scope_id}.md")
    def client_report_markdown(scope_id: str) -> Response:
        store.initialize()
        try:
            payload = _client_report_payload(scope_id, store)
        except ValueError:
            return HTMLResponse(_page("Scope not found", "<h1>Scope not found</h1>"), status_code=404)
        return Response(_render_client_report_markdown(payload), media_type="text/markdown; charset=utf-8")

    @app.get("/trust/rules-of-engagement.md")
    def rules_of_engagement() -> Response:
        return Response(_rules_of_engagement_template(), media_type="text/markdown; charset=utf-8")

    @app.get("/trust/security-summary.md")
    def security_summary() -> Response:
        return Response(_security_summary(settings), media_type="text/markdown; charset=utf-8")

    return app


def _is_public_path(path: str) -> bool:
    return path in {"/readyz", "/login"} or path.startswith("/login?")


def _is_rate_limited(
    request: Request,
    settings: Settings,
    rate_buckets: dict[str, list[float]],
) -> bool:
    if request.url.path == "/readyz":
        return False
    now = time.time()
    window = settings.operator_rate_limit_window_seconds
    key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
    bucket = [timestamp for timestamp in rate_buckets.get(key, []) if now - timestamp < window]
    bucket.append(now)
    rate_buckets[key] = bucket
    return len(bucket) > settings.operator_rate_limit_max_requests


def _operator_auth_enabled(settings: Settings) -> bool:
    return settings.operator_token is not None


def _token_matches(submitted: str, settings: Settings) -> bool:
    if settings.operator_token is None:
        return True
    expected = settings.operator_token.get_secret_value()
    return secrets.compare_digest(submitted, expected)


def _is_operator_authenticated(request: Request, settings: Settings) -> bool:
    if not _operator_auth_enabled(settings):
        return True
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and _token_matches(token, settings):
        return True
    session = request.cookies.get(OPERATOR_SESSION_COOKIE)
    return bool(session and _valid_session_cookie(session, settings))


def _is_bearer_authenticated(request: Request, settings: Settings) -> bool:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    return scheme.lower() == "bearer" and _token_matches(token, settings)


def _session_secret(settings: Settings) -> str:
    if settings.operator_session_secret is not None:
        return settings.operator_session_secret.get_secret_value()
    if settings.operator_token is not None:
        return settings.operator_token.get_secret_value()
    return "local-dev-operator-session"


def _new_session_cookie(settings: Settings) -> str:
    issued_at = str(int(time.time()))
    signature = _session_signature(issued_at, settings)
    return f"v1:{issued_at}:{signature}"


def _valid_session_cookie(cookie: str, settings: Settings) -> bool:
    version, separator, rest = cookie.partition(":")
    if version != "v1" or not separator:
        return False
    issued_at, separator, signature = rest.partition(":")
    if not separator or not issued_at.isdigit():
        return False
    age = int(time.time()) - int(issued_at)
    if age < 0 or age > settings.operator_session_ttl_seconds:
        return False
    expected = _session_signature(issued_at, settings)
    return secrets.compare_digest(signature, expected)


def _session_signature(issued_at: str, settings: Settings) -> str:
    digest = hmac.new(
        _session_secret(settings).encode("utf-8"),
        issued_at.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def _csrf_token_for_request(request: Request, settings: Settings) -> str:
    session = request.cookies.get(OPERATOR_SESSION_COOKIE)
    if not _operator_auth_enabled(settings) or not session:
        return ""
    return hmac.new(
        _session_secret(settings).encode("utf-8"),
        f"csrf:{session}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _csrf_input(token: str) -> str:
    if not token:
        return ""
    return f'<input type="hidden" name="_csrf_token" value="{escape(token)}">'


def _csrf_failure_response(
    request: Request,
    settings: Settings,
    params: dict[str, list[str]],
) -> HTMLResponse | None:
    if not _operator_auth_enabled(settings) or _is_bearer_authenticated(request, settings):
        return None
    expected = _csrf_token_for_request(request, settings)
    submitted = params.get("_csrf_token", [""])[0]
    if expected and secrets.compare_digest(submitted, expected):
        return None
    return HTMLResponse(_page("Invalid request", "<h1>Invalid request token</h1>"), status_code=403)


def _record_audit(
    store: RunStore,
    request: Request,
    action: AuditAction,
    target_type: str,
    target_id: str,
    success: bool = True,
    metadata: dict[str, object] | None = None,
) -> None:
    try:
        store.save_audit_event(
            AuditEvent(
                action=action,
                target_type=target_type,
                target_id=target_id,
                success=success,
                ip_address_hash=_hash_ip(request.client.host if request.client else None),
                user_agent=request.headers.get("user-agent"),
                metadata=metadata or {},
            )
        )
    except Exception:
        return


def _hash_ip(ip_address: str | None) -> str | None:
    if not ip_address:
        return None
    return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()[:16]


def _split_form_list(value: str) -> list[str]:
    parts = value.replace("\n", ",").split(",")
    return [part.strip() for part in parts if part.strip()]


def _parse_optional_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


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


def _reports_table(reports: list[dict[str, object]], csrf: str = "") -> str:
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
        f"<td>{_report_status_form(report, csrf)}</td>"
        "</tr>"
        for report in reports
    )
    return (
        "<table><caption class=\"sr-only\">Current vulnerability report drafts</caption>"
        "<thead><tr><th scope=\"col\">Report</th><th scope=\"col\">Severity / Impact</th>"
        "<th scope=\"col\">Status</th><th scope=\"col\">Workflow</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _report_status_form(report: dict[str, object], csrf: str) -> str:
    report_id = escape(str(report["vulnerability_id"]))
    options = _enum_options(ReportStatus, str(report.get("status", "")))
    return (
        f"<form class=\"inline-form\" method=\"post\" action=\"/reports/{report_id}/status\">"
        f"{_csrf_input(csrf)}"
        "<label class=\"sr-only\" for=\"report-status\">Status</label>"
        f"<select id=\"report-status-{report_id}\" name=\"status\">{options}</select>"
        "<input name=\"status_note\" type=\"text\" placeholder=\"note\">"
        "<button type=\"submit\">Update</button>"
        "</form>"
    )


def _scope_admin_panel(
    clients: list[dict[str, object]],
    projects: list[dict[str, object]],
    scopes: list[dict[str, object]],
    csrf: str,
    settings: Settings,
) -> str:
    return (
        "<div class=\"admin-grid\">"
        "<div class=\"admin-card\"><h3>Client</h3>"
        f"<form class=\"stack-form\" method=\"post\" action=\"/clients\">{_csrf_input(csrf)}"
        "<label for=\"client-name\">Name</label><input id=\"client-name\" name=\"name\" required>"
        "<button type=\"submit\">Create Client</button></form></div>"
        "<div class=\"admin-card\"><h3>Project</h3>"
        f"<form class=\"stack-form\" method=\"post\" action=\"/projects\">{_csrf_input(csrf)}"
        "<label for=\"project-client\">Client</label>"
        f"<select id=\"project-client\" name=\"client_id\" required>{_client_options(clients)}</select>"
        "<label for=\"project-name\">Name</label><input id=\"project-name\" name=\"name\" required>"
        "<button type=\"submit\">Create Project</button></form></div>"
        "<div class=\"admin-card wide\"><h3>Authorized Scope</h3>"
        f"<form class=\"stack-form\" method=\"post\" action=\"/scopes\">{_csrf_input(csrf)}"
        "<label for=\"scope-project\">Project</label>"
        f"<select id=\"scope-project\" name=\"project_id\" required>{_project_options(projects)}</select>"
        "<label for=\"scope-name\">Scope name</label><input id=\"scope-name\" name=\"name\" required>"
        "<label for=\"scope-hosts\">Allowed hosts</label>"
        f"<textarea id=\"scope-hosts\" name=\"allowed_hosts\" required>{escape(', '.join(settings.allowed_hosts))}</textarea>"
        "<label for=\"scope-modes\">Scan modes</label>"
        "<select id=\"scope-modes\" name=\"allowed_scan_modes\" multiple>"
        "<option value=\"passive-http\" selected>Passive HTTP</option>"
        "<option value=\"low-priv-authenticated\">Low-Priv Authenticated</option>"
        "</select>"
        "<label for=\"scope-excluded\">Excluded paths</label>"
        "<textarea id=\"scope-excluded\" name=\"excluded_paths\" placeholder=\"/admin/private, /billing\"></textarea>"
        "<label for=\"scope-max-urls\">Max URLs</label>"
        "<input id=\"scope-max-urls\" name=\"max_urls\" type=\"number\" min=\"1\" max=\"50\" value=\"12\">"
        "<label for=\"scope-note\">Authorization note</label>"
        "<textarea id=\"scope-note\" name=\"authorization_note\" required></textarea>"
        "<label for=\"scope-contact\">Operator contact</label>"
        "<input id=\"scope-contact\" name=\"operator_contact\" type=\"email\">"
        "<label for=\"scope-roe\">Rules of engagement ref</label>"
        "<input id=\"scope-roe\" name=\"rules_of_engagement_ref\" placeholder=\"ticket, contract, or doc ref\">"
        "<label for=\"scope-expiry\">Authorization expiry</label>"
        "<input id=\"scope-expiry\" name=\"authorization_expires_at\" type=\"datetime-local\">"
        "<button type=\"submit\">Create Scope</button></form></div>"
        "</div>"
        f"{_scopes_table(scopes, csrf)}"
        "<nav class=\"export-nav trust-links\" aria-label=\"Trust package\">"
        "<a href=\"/trust/security-summary.md\">Security summary</a>"
        "<a href=\"/trust/rules-of-engagement.md\">Rules of engagement</a>"
        "</nav>"
    )


def _client_options(clients: list[dict[str, object]]) -> str:
    if not clients:
        return '<option value="">No clients</option>'
    return "\n".join(
        f"<option value=\"{escape(str(client['client_id']))}\">{escape(str(client['name']))}</option>"
        for client in clients
    )


def _project_options(projects: list[dict[str, object]]) -> str:
    if not projects:
        return '<option value="">No projects</option>'
    return "\n".join(
        f"<option value=\"{escape(str(project['project_id']))}\">{escape(str(project['name']))}</option>"
        for project in projects
    )


def _scopes_table(scopes: list[dict[str, object]], csrf: str) -> str:
    if not scopes:
        return "<p>No authorized scopes yet.</p>"
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(scope['name']))}<br><span class=\"muted-line\">{escape(str(scope['scope_id']))}</span></td>"
        f"<td>{escape(', '.join(_object_list(scope.get('allowed_hosts'))))}</td>"
        f"<td>{escape(', '.join(_object_list(scope.get('allowed_scan_modes'))))}</td>"
        f"<td>{escape(str(scope.get('authorization_expires_at') or 'no expiry'))}</td>"
        f"<td class=\"export-cell\"><a href=\"/client-reports/{escape(str(scope['scope_id']))}.json\">JSON</a>"
        f"<a href=\"/client-reports/{escape(str(scope['scope_id']))}.md\">MD</a></td>"
        f"<td>{_scope_deactivate_form(scope, csrf)}</td>"
        "</tr>"
        for scope in scopes
    )
    return (
        "<table><caption class=\"sr-only\">Authorized client scopes</caption>"
        "<thead><tr><th scope=\"col\">Scope</th><th scope=\"col\">Hosts</th>"
        "<th scope=\"col\">Modes</th><th scope=\"col\">Expiry</th>"
        "<th scope=\"col\">Report</th><th scope=\"col\">Action</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _scope_deactivate_form(scope: dict[str, object], csrf: str) -> str:
    if not bool(scope.get("active", True)):
        return _status_badge("inactive")
    scope_id = escape(str(scope["scope_id"]))
    return (
        f"<form class=\"inline-form\" method=\"post\" action=\"/scopes/{scope_id}/deactivate\">"
        f"{_csrf_input(csrf)}"
        "<button type=\"submit\">Deactivate</button>"
        "</form>"
    )


def _object_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _scope_options(scopes: list[dict[str, object]]) -> str:
    if not scopes:
        return '<option value="">No authorized scopes</option>'
    return "\n".join(
        f"<option value=\"{escape(str(scope['scope_id']))}\">"
        f"{escape(str(scope['name']))}</option>"
        for scope in scopes
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
        f"<td>{escape(str(scan.get('scope_id') or 'legacy'))}</td>"
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
        "<th scope=\"col\">Scope</th><th scope=\"col\">Mode</th><th scope=\"col\">Status</th>"
        "<th scope=\"col\">Highest</th><th scope=\"col\">Findings</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _scan_jobs_table(jobs: list[dict[str, object]], csrf: str) -> str:
    if not jobs:
        return (
            "<div class=\"empty-state\">"
            "<strong>No scan jobs queued yet.</strong>"
            "<span>Site scans will appear here with lifecycle status and cancellation state.</span>"
            "</div>"
        )
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(job['job_id']))}<br><span class=\"muted-line\">{escape(str(job['scope_id']))}</span></td>"
        f"<td>{escape(str(job['target_url']))}</td>"
        f"<td>{escape(str(job['scan_mode']))}</td>"
        f"<td>{_status_badge(job['status'])}</td>"
        f"<td>{escape(str(job.get('scan_id') or 'pending'))}</td>"
        f"<td>{_scan_job_cancel_form(job, csrf)}</td>"
        "</tr>"
        for job in jobs
    )
    return (
        "<table><caption class=\"sr-only\">Scan job queue</caption>"
        "<thead><tr><th scope=\"col\">Job</th><th scope=\"col\">Target</th>"
        "<th scope=\"col\">Mode</th><th scope=\"col\">Status</th>"
        "<th scope=\"col\">Scan</th><th scope=\"col\">Action</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _scan_job_cancel_form(job: dict[str, object], csrf: str) -> str:
    if str(job.get("status")) not in {ScanJobStatus.QUEUED.value, ScanJobStatus.RUNNING.value}:
        return "<span class=\"muted-line\">closed</span>"
    job_id = escape(str(job["job_id"]))
    return (
        f"<form class=\"inline-form\" method=\"post\" action=\"/scan-jobs/{job_id}/cancel\">"
        f"{_csrf_input(csrf)}"
        "<button type=\"submit\">Cancel</button>"
        "</form>"
    )


def _site_findings_table(findings: list[dict[str, object]], csrf: str = "") -> str:
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
        f"<td>{_status_badge(finding.get('status', 'open'))}</td>"
        f"<td>{escape(str(finding['remediation']))}</td>"
        f"<td>{_finding_status_form(finding, csrf)}</td>"
        "</tr>"
        for finding in findings
    )
    return (
        "<table><caption class=\"sr-only\">Passive site scan findings</caption>"
        "<thead><tr><th scope=\"col\">Severity</th><th scope=\"col\">Finding</th>"
        "<th scope=\"col\">Evidence</th><th scope=\"col\">Status</th>"
        "<th scope=\"col\">Remediation</th><th scope=\"col\">Workflow</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _finding_status_form(finding: dict[str, object], csrf: str) -> str:
    finding_id = escape(str(finding["finding_id"]))
    options = _enum_options(FindingStatus, str(finding.get("status", "")))
    return (
        f"<form class=\"inline-form\" method=\"post\" action=\"/site-findings/{finding_id}/status\">"
        f"{_csrf_input(csrf)}"
        "<label class=\"sr-only\" for=\"finding-status\">Finding status</label>"
        f"<select id=\"finding-status-{finding_id}\" name=\"status\">{options}</select>"
        "<input name=\"status_note\" type=\"text\" placeholder=\"note\">"
        "<input name=\"retest_scan_id\" type=\"text\" placeholder=\"retest scan id\">"
        "<button type=\"submit\">Update</button>"
        "</form>"
    )


def _audit_table(events: list[dict[str, object]]) -> str:
    if not events:
        return "<p>No audit events recorded yet.</p>"
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(event['created_at']))}</td>"
        f"<td>{escape(str(event['action']))}</td>"
        f"<td>{escape(str(event['target_type']))}<br><span class=\"muted-line\">{escape(str(event['target_id']))}</span></td>"
        f"<td>{_status_badge('success' if event.get('success', True) else 'failed')}</td>"
        "</tr>"
        for event in events
    )
    return (
        "<table><caption class=\"sr-only\">Operator audit log</caption>"
        "<thead><tr><th scope=\"col\">Time</th><th scope=\"col\">Action</th>"
        "<th scope=\"col\">Target</th><th scope=\"col\">Result</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _client_report_payload(scope_id: str, store: RunStore) -> dict[str, object]:
    scope = store.authorized_scope(scope_id)
    if scope is None:
        raise ValueError(f"scope not found: {scope_id}")
    scans = [scan for scan in store.site_scan_runs(limit=500) if scan.get("scope_id") == scope_id]
    findings = [
        finding
        for scan in scans
        for finding in store.site_scan_findings(str(scan["scan_id"]))
    ]
    open_findings = [
        finding
        for finding in findings
        if str(finding.get("status", FindingStatus.OPEN.value))
        not in {FindingStatus.FIXED.value, FindingStatus.FALSE_POSITIVE.value}
    ]
    return {
        "scope": scope.model_dump(mode="json"),
        "scans": scans,
        "findings": findings,
        "open_findings": open_findings,
        "generated_at": utc_now().isoformat(),
        "report_type": "client_security_summary",
    }


def _render_client_report_markdown(payload: dict[str, object]) -> str:
    scope = payload["scope"]
    if not isinstance(scope, dict):
        raise ValueError("scope payload must be an object")
    scans = payload.get("scans", [])
    findings = payload.get("findings", [])
    open_findings = payload.get("open_findings", [])
    lines = [
        f"# Client Security Summary: {scope.get('name')}",
        "",
        f"- Scope ID: `{scope.get('scope_id')}`",
        f"- Client ID: `{scope.get('client_id')}`",
        f"- Project ID: `{scope.get('project_id')}`",
        f"- Authorized hosts: `{', '.join(str(host) for host in scope.get('allowed_hosts', []))}`",
        f"- Allowed scan modes: `{', '.join(str(mode) for mode in scope.get('allowed_scan_modes', []))}`",
        f"- Generated: `{payload.get('generated_at')}`",
        "",
        "## Executive Summary",
        "",
        f"- Scans completed: `{len(scans) if isinstance(scans, list) else 0}`",
        f"- Total findings: `{len(findings) if isinstance(findings, list) else 0}`",
        f"- Open findings: `{len(open_findings) if isinstance(open_findings, list) else 0}`",
        "- Sensitive reproduction details remain in the private findings vault.",
        "",
        "## Findings",
        "",
    ]
    if isinstance(findings, list) and findings:
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.append(
                f"- `{finding.get('severity')}` `{finding.get('status')}` "
                f"{finding.get('title')} (`{finding.get('check_id')}`)"
            )
    else:
        lines.append("- No findings recorded for this scope.")
    lines.extend(
        [
            "",
            "## Authorization",
            "",
            f"- Authorization note: {scope.get('authorization_note')}",
            f"- Authorization expires: `{scope.get('authorization_expires_at') or 'not set'}`",
            f"- Rules of engagement reference: `{scope.get('rules_of_engagement_ref') or 'not set'}`",
            "",
        ]
    )
    return "\n".join(lines)


def _rules_of_engagement_template() -> str:
    return """# Rules Of Engagement Template

- Client/project:
- Authorized hosts:
- Explicitly excluded paths:
- Approved scan modes:
- Approved testing window:
- Low-privileged test account owner:
- Emergency stop contact:
- Evidence retention period:
- Written authorization reference:

Only run scans against hosts and modes listed in an active authorized scope.
"""


def _security_summary(settings: Settings) -> str:
    return f"""# AgentForge Adversarial Security Summary

- Operator dashboard and exports are token-gated when `ADVERSARIAL_OPERATOR_TOKEN` is set.
- Browser form actions use signed-session CSRF tokens.
- Operator requests are rate limited per path and client.
- Public SQLite storage keeps redacted summaries; reproduction details are stored in `{settings.private_sqlite_path}`.
- Site scans require an active client/project/scope record and the target host must also be in `ADVERSARIAL_ALLOWED_HOSTS`.
- Evidence retention default: `{settings.evidence_retention_days}` days.
- Active exploitation, brute force, credential attacks, and destructive testing are outside the implemented scan profiles.
"""


def _enum_options(enum_type: type[StrEnum], selected: str) -> str:
    options: list[str] = []
    for value in enum_type:
        selected_attr = " selected" if str(value.value) == selected else ""
        options.append(
            f"<option value=\"{escape(str(value.value))}\"{selected_attr}>"
            f"{escape(str(value.value))}</option>"
        )
    return "\n".join(options)


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
    input[type="url"],
    input[type="text"],
    input[type="email"],
    input[type="number"],
    input[type="datetime-local"],
    input[type="password"],
    textarea,
    select {
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

    textarea {
      min-height: 84px;
      resize: vertical;
    }

    select { min-width: 190px; }

    .admin-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }

    .admin-card {
      min-width: 0;
      padding: 14px;
      border: 1px solid var(--steel);
      border-left: 3px solid var(--red);
      border-radius: 6px;
      background: rgba(6, 6, 7, .70);
    }

    .admin-card.wide { grid-column: 1 / -1; }
    .admin-card h3 { margin: 0 0 10px; text-transform: uppercase; }

    .stack-form,
    .inline-form {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .stack-form {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      align-items: start;
    }

    .stack-form label,
    .inline-form label {
      color: var(--muted);
      font-family: var(--font-data);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }

    .stack-form button { justify-self: start; }
    .inline-form input,
    .inline-form select { min-width: 150px; }
    .trust-links { margin-top: 12px; justify-content: flex-start; }

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
      .admin-grid,
      .stack-form { grid-template-columns: 1fr; }
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
