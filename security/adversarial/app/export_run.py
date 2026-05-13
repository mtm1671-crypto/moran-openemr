"""Export run evidence from SQLite to JSON and Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .run_store import RunStore


def build_run_export(run_id: str, store: RunStore) -> dict[str, Any]:
    runs = [run for run in store.latest_runs(limit=500) if run["run_id"] == run_id]
    if not runs:
        raise ValueError(f"run not found: {run_id}")
    observations = store.observations(run_id)
    verdicts = [verdict for verdict in store.verdicts() if verdict["run_id"] == run_id]
    reports = [report for report in store.reports() if report["source_run_id"] == run_id]
    traces = store.trace_events(run_id)
    snapshots = [snapshot for snapshot in store.snapshots() if snapshot["run_id"] == run_id]
    return {
        "run": runs[0],
        "observations": observations,
        "verdicts": verdicts,
        "reports": reports,
        "trace": traces,
        "resilience_snapshots": snapshots,
    }


def export_run(run_id: str, out_dir: Path, store: RunStore) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_run_export(run_id, store)
    json_path = out_dir / f"{run_id}.json"
    md_path = out_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_run_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_run_markdown(payload: dict[str, Any]) -> str:
    run = payload["run"]
    verdicts = payload["verdicts"]
    observations = payload["observations"]
    reports = payload["reports"]
    snapshots = payload.get("resilience_snapshots", [])
    traces = payload.get("trace", [])
    lines = [
        f"# Week 3 Adversarial Run {run['run_id']}",
        "",
        f"- Target: `{run['target_url']}`",
        f"- Mode: `{run['target_mode']}` / `{run['run_mode']}`",
        f"- Stop reason: `{run['stop_reason']}`",
        f"- Estimated cost: `${run['estimated_cost_usd']:.4f}`",
        f"- Synthetic principal: `{run.get('synthetic_principal') or 'not recorded'}`",
        "",
        "## Black-Box Observations",
        "",
    ]
    for observation in observations:
        text = str(observation.get("text", ""))
        preview = text[:500].replace("\n", " ")
        lines.append(
            f"- Status `{observation.get('status_code')}`; latency "
            f"`{observation.get('latency_ms')}ms`; evidence preview: {preview}"
        )
    lines.extend(["", "## Verdicts", ""])
    for verdict in verdicts:
        lines.append(
            f"- `{verdict['verdict']}` `{verdict['severity']} / {verdict['impact_domain']}` "
            f"{verdict['reason_code']}: {verdict['reason']}"
        )
    lines.extend(["", "## Reports", ""])
    for report in reports:
        lines.append(
            f"- `{report['status']}` `{report['severity']} / {report['impact_domain']}` "
            f"{report['vulnerability_id']}"
        )
    lines.extend(["", "## Resilience", ""])
    if snapshots:
        snapshot = snapshots[0]
        lines.append(
            f"- Score `{snapshot['risk_weighted_score']}`: {snapshot['score_explanation']}"
        )
    else:
        lines.append("- No resilience snapshot recorded for this run.")
    lines.extend(["", "## Trace", ""])
    for event in traces:
        lines.append(
            f"- `{event['agent_name']}` `{event['event_type']}`: {event['message']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", type=Path, default=Path("evals/week3/exports"))
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    settings = Settings()
    store = RunStore(args.db or settings.sqlite_path)
    json_path, md_path = export_run(args.run_id, args.out, store)
    print(f"exported {json_path}")
    print(f"exported {md_path}")


if __name__ == "__main__":
    main()
