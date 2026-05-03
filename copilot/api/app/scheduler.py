import asyncio
import json
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.jobs import run_nightly_maintenance


def seconds_until_next_hour(now: datetime, hour_utc: int) -> float:
    current = now.astimezone(UTC)
    next_run = current.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if next_run <= current:
        next_run += timedelta(days=1)
    return (next_run - current).total_seconds()


async def nightly_maintenance_loop(settings: Settings) -> None:
    while True:
        await asyncio.sleep(seconds_until_next_hour(datetime.now(tz=UTC), settings.nightly_maintenance_hour_utc))
        try:
            result = await run_nightly_maintenance(settings)
            print(json.dumps({"event": "nightly_maintenance_complete", "result": result}, sort_keys=True))
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "event": "nightly_maintenance_failed",
                        "error": str(exc),
                        "ran_at": datetime.now(tz=UTC).isoformat(),
                    },
                    sort_keys=True,
                )
            )
