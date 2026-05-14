"""Application workflow for authorized site scans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .config import Settings
from .models import ScanJob, ScanJobStatus, SiteScanFinding, SiteScanMode, SiteScanRun, utc_now
from .ports import SiteScanner
from .run_store import RunStore
from .scope_registry import resolve_scope_for_scan
from .site_scanner import PassiveSiteScanner


@dataclass(frozen=True)
class SiteScanWorkflowResult:
    job: ScanJob
    scan: SiteScanRun
    findings: list[SiteScanFinding]


class SiteScanWorkflowError(RuntimeError):
    def __init__(self, message: str, job: ScanJob | None = None) -> None:
        super().__init__(message)
        self.job = job


class SiteScanWorkflow:
    """Own the scan job lifecycle around a bounded scanner implementation."""

    def __init__(
        self,
        *,
        settings: Settings,
        store: RunStore,
        scanner_factory: Callable[[Settings], SiteScanner] = PassiveSiteScanner,
    ) -> None:
        self.settings = settings
        self.store = store
        self.scanner_factory = scanner_factory

    def run(
        self,
        *,
        target_url: str,
        authorization_note: str = "Operator attests this target is owned or explicitly authorized.",
        mode: SiteScanMode = SiteScanMode.PASSIVE_HTTP,
        scope_id: str | None = None,
        on_job_queued: Callable[[ScanJob], None] | None = None,
        on_scan_completed: Callable[[ScanJob, SiteScanRun], None] | None = None,
    ) -> SiteScanWorkflowResult:
        job: ScanJob | None = None
        try:
            self.store.initialize()
            scope = resolve_scope_for_scan(
                store=self.store,
                settings=self.settings,
                scope_id=scope_id,
                target_url=target_url,
                mode=mode,
            )
            job = ScanJob(
                scope_id=scope.scope_id,
                client_id=scope.client_id,
                project_id=scope.project_id,
                target_url=target_url,
                scan_mode=mode,
                status=ScanJobStatus.QUEUED,
                metadata={"authorization_note": authorization_note},
            )
            self.store.save_scan_job(job)
            if on_job_queued is not None:
                on_job_queued(job)
            job = job.model_copy(update={"status": ScanJobStatus.RUNNING, "started_at": utc_now()})
            self.store.save_scan_job(job)

            scan, findings = self.scanner_factory(self.settings).scan(
                target_url=target_url,
                authorization_note=authorization_note,
                mode=mode,
                scope=scope,
            )
            self.store.save_site_scan_run(scan)
            self.store.save_site_scan_findings(findings)
            job = job.model_copy(
                update={
                    "status": ScanJobStatus.COMPLETED,
                    "completed_at": utc_now(),
                    "scan_id": scan.scan_id,
                }
            )
            self.store.save_scan_job(job)
            if on_scan_completed is not None:
                on_scan_completed(job, scan)
            return SiteScanWorkflowResult(job=job, scan=scan, findings=findings)
        except Exception as exc:
            if job is not None:
                job = job.model_copy(
                    update={
                        "status": ScanJobStatus.FAILED,
                        "completed_at": utc_now(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                self.store.save_scan_job(job)
            raise SiteScanWorkflowError(f"{type(exc).__name__}: {exc}", job) from exc
