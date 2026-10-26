"""MX01 investor-only levers must retain exact physical common-model inputs."""

import copy

import pytest

from gb_flexabm.investor_mechanisms import CASES, SEEDS, configuration, physical_contract_hash


def test_all_mx01_levers_leave_model_and_planner_unchanged():
    assert len(CASES) == 5
    assert SEEDS == tuple(range(401, 413))
    base = configuration("baseline")
    for name in CASES:
        cfg = configuration(name)
        assert cfg["technologies"] == base["technologies"]
        assert cfg["assets"] == base["assets"]
        assert cfg["storage"] == base["storage"]
        assert cfg["years"] == base["years"]
        assert cfg["capacity_price_gbp_per_kw_year"] == 75
        assert physical_contract_hash(cfg) == physical_contract_hash(base)


def test_factors_are_single_lever_and_preset():
    base = configuration("baseline")
    reduced = configuration("budget_20pct")
    zero = configuration("budget_zero")
    hurdle = configuration("high_hurdle")
    noise = configuration("zero_expectation_noise")
    for index, investor in enumerate(base["investors"]):
        assert reduced["investors"][index]["annual_budget_gbp"] == pytest.approx(
            investor["annual_budget_gbp"] * 0.2
        )
        assert zero["investors"][index]["annual_budget_gbp"] == 0
        assert hurdle["investors"][index]["hurdle_rate"] == pytest.approx(
            investor["hurdle_rate"] + 0.15
        )
        assert noise["investors"][index]["forecast_noise_fraction"] == 0
    with pytest.raises(ValueError, match="registered"):
        configuration("optimised_best_case")


def test_mutation_does_not_leak_across_runs():
    base = configuration("baseline")
    changed = configuration("budget_20pct")
    changed["assets"].clear()
    changed["investors"].clear()
    assert configuration("baseline") == base
    assert configuration("budget_20pct") != changed
