import json
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.security import assert_metadata_payload_is_phi_safe


def emit_telemetry_event(
    settings: Settings,
    *,
    event: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not settings.structured_logging_enabled:
        return
    safe_metadata = metadata or {}
    assert_metadata_payload_is_phi_safe(safe_metadata)
    payload = {
        "event": event,
        "service": "clinical-copilot-api",
        "environment": settings.app_env,
        "timestamp_unix_ms": int(datetime.now(tz=UTC).timestamp() * 1000),
        "metadata": safe_metadata,
    }
    print(json.dumps(payload, sort_keys=True))
