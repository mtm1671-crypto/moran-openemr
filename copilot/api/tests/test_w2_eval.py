from pathlib import Path

import pytest

from app import w2_eval


def test_enforced_eval_requires_baseline_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def passing_results(cases: list[object]) -> list[w2_eval.EvalCaseResult]:
        return [
            w2_eval.EvalCaseResult(
                case_id=f"case-{index}",
                rubric={key: True for key in w2_eval.HARD_GATE_KEYS},
            )
            for index, _case in enumerate(cases)
        ]

    monkeypatch.setattr(
        w2_eval,
        "load_golden_cases",
        lambda _path: [object() for _index in range(w2_eval.MIN_ENFORCED_CASES)],
    )
    monkeypatch.setattr(w2_eval, "run_golden_cases", passing_results)

    with pytest.raises(w2_eval.EvalGateFailed, match="baseline is required"):
        w2_eval.main(
            [
                "--cases",
                str(tmp_path / "cases.jsonl"),
                "--baseline",
                str(tmp_path / "missing-baseline.json"),
                "--output",
                str(tmp_path / "latest-results.jsonl"),
                "--enforce",
            ]
        )
