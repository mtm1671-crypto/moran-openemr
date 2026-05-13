"""Load adversarial eval cases from JSON files."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import AttackCase


DEFAULT_CASE_ROOT = Path(__file__).resolve().parents[1] / "evals" / "week3" / "cases"


def load_cases(case_root: Path | None = None) -> list[AttackCase]:
    root = (case_root or _default_case_root()).resolve()
    if not root.exists():
        raise FileNotFoundError(f"case root does not exist: {root}")
    cases: list[AttackCase] = []
    for path in sorted(root.rglob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            cases.append(AttackCase.model_validate(json.load(handle)))
    if not cases:
        raise ValueError(f"no attack cases found under {root}")
    return cases


def load_cases_for_suite(suite: str, case_root: Path | None = None) -> list[AttackCase]:
    cases = load_cases(case_root)
    if suite == "seed":
        return cases
    if suite == "regression":
        return [case for case in cases if case.regression_candidate]
    if suite == "smoke":
        return cases[:1]
    raise ValueError(f"unknown suite: {suite}")


def _default_case_root() -> Path:
    configured = os.getenv("ADVERSARIAL_CASE_ROOT")
    if configured:
        return Path(configured)
    candidates = [
        DEFAULT_CASE_ROOT,
        Path.cwd() / "evals" / "week3" / "cases",
        Path(__file__).resolve().parents[2] / "evals" / "week3" / "cases",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DEFAULT_CASE_ROOT
