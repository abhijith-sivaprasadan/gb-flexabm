"""Check the crosscase research gate cannot drop inconvenient trials."""

from pathlib import Path

import pytest

from scripts.summarize_investor_mechanisms import compare_cases


def test_all_five_cases_are_required():
    with pytest.raises(ValueError, match="five preregistered"):
        compare_cases({"baseline": Path("fake")})


def test_empty_inputs_fail_not_report_zero_effect(tmp_path):
    cases = ("baseline", "budget_20pct", "budget_zero", "high_hurdle", "zero_expectation_noise")
    with pytest.raises(FileNotFoundError):
        compare_cases({x: tmp_path / x for x in cases})
