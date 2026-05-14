"""Client/project/scope helpers for authorized site scanning."""

from __future__ import annotations

from .config import Settings
from .models import AuthorizedScope, Client, Project, SiteScanMode
from .run_store import RunStore

DEFAULT_CLIENT_ID = "client_agentforge_demo"
DEFAULT_PROJECT_ID = "project_agentforge_security"
DEFAULT_SCOPE_ID = "scope_agentforge_demo"


def default_scope_bundle(settings: Settings) -> tuple[Client, Project, AuthorizedScope]:
    client = Client(client_id=DEFAULT_CLIENT_ID, name="AgentForge Demo")
    project = Project(
        project_id=DEFAULT_PROJECT_ID,
        client_id=client.client_id,
        name="Authorized Demo Targets",
    )
    scope = AuthorizedScope(
        scope_id=DEFAULT_SCOPE_ID,
        client_id=client.client_id,
        project_id=project.project_id,
        name="Default allowlisted demo scope",
        allowed_hosts=settings.allowed_hosts,
        allowed_scan_modes=[
            SiteScanMode.PASSIVE_HTTP,
            SiteScanMode.B2B_BASELINE,
            SiteScanMode.LOW_PRIV_AUTHENTICATED,
        ],
        excluded_paths=[],
        max_urls=settings.site_scan_max_urls,
        authorization_note="Default scope seeded from ADVERSARIAL_ALLOWED_HOSTS.",
    )
    return client, project, scope


def ensure_default_scope(store: RunStore, settings: Settings) -> AuthorizedScope:
    client, project, scope = default_scope_bundle(settings)
    store.save_client(client)
    store.save_project(project)
    store.save_authorized_scope(scope)
    return scope


def resolve_scope_for_scan(
    *,
    store: RunStore,
    settings: Settings,
    scope_id: str | None,
    target_url: str,
    mode: SiteScanMode,
) -> AuthorizedScope:
    ensure_default_scope(store, settings)
    resolved_scope_id = scope_id or DEFAULT_SCOPE_ID
    scope = store.authorized_scope(resolved_scope_id)
    if scope is None:
        raise ValueError(f"authorized scope not found: {resolved_scope_id}")
    scope.assert_allows(target_url, mode)
    return scope
