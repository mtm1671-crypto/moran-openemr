"""Evaluate deterministic Judge quality against labeled fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .judge_agent import JudgeAgent
from .models import AttackCase, ObservedResponse, RunBudget, Severity, Verdict


DEFAULT_JUDGE_CASE_ROOT = Path(__file__).resolve().parents[1] / "evals" / "week3" / "judge_cases"


def run_judge_eval(case_root: Path = DEFAULT_JUDGE_CASE_ROOT) -> dict[str, Any]:
    fixtures = _load_fixtures(case_root)
    false_positives = 0
    false_negatives = 0
    critical_or_high_false_negatives = 0
    inconclusive = 0
    results: list[dict[str, Any]] = []
    judge = JudgeAgent()
    for index, fixture in enumerate(fixtures, start=1):
        case = AttackCase.model_validate(fixture["case"])
        observed = ObservedResponse.model_validate(fixture["observed"])
        expected = Verdict(fixture["expected_verdict"])
        verdict = judge.evaluate(
            run_id=f"judge_eval_{index}",
            case=case,
            observed=observed,
            budget=RunBudget(),
        )
        if verdict.verdict == Verdict.INCONCLUSIVE:
            inconclusive += 1
        if expected == Verdict.PASS and verdict.verdict != Verdict.PASS:
            false_positives += 1
        if expected == Verdict.FAIL and verdict.verdict != Verdict.FAIL:
            false_negatives += 1
            if case.severity in {Severity.CRITICAL, Severity.HIGH}:
                critical_or_high_false_negatives += 1
        results.append(
            {
                "fixture": fixture["id"],
                "expected": expected,
                "actual": verdict.verdict,
                "reason_code": verdict.reason_code,
                "severity": case.severity,
            }
        )
    return {
        "total": len(fixtures),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "critical_or_high_false_negatives": critical_or_high_false_negatives,
        "inconclusive": inconclusive,
        "inconclusive_rate": inconclusive / max(len(fixtures), 1),
        "results": results,
    }


def _load_fixtures(case_root: Path) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for path in sorted(case_root.rglob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"judge fixture must be an object: {path}")
        fixtures.append(payload)
    if not fixtures:
        raise ValueError(f"no judge fixtures found under {case_root}")
    return fixtures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, default=DEFAULT_JUDGE_CASE_ROOT)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    summary = run_judge_eval(args.case_root)
    print(json.dumps(summary, indent=2, default=str))
    if args.enforce and summary["critical_or_high_false_negatives"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
