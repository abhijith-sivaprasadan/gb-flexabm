import numpy as np
import pytest

from gb_flexabm.cli import default_config
from gb_flexabm.diagnostics import (
    dispatch_reduction,
    generation_share_mae_pp,
    price_metrics,
    relative_error,
    representative_days,
)
from gb_flexabm.research_metrics import (
    capacity_metrics,
    capacity_obligation_transfer,
    cfd_transfer,
    rolling_baselines,
    seed_convergence,
    sensitivity_screen,
)
from gb_flexabm.schema import Periods, synthetic_periods, system_from_config


def test_medoids_conserve_hours_retain_extremes_and_replay():
    system = system_from_config(default_config())
    periods = synthetic_periods(system, 168, annual_hours=168)
    selected = representative_days(periods, 4)
    assert sum(selected.counts) * 24 == 168
    assert all(n > 0 for n in selected.counts)
    assert set(selected.forced_extremes).issubset(selected.medoids)
    assert selected == representative_days(periods, 4)


def test_constant_duplicate_days_keep_nonempty_medoids():
    periods = Periods((50.0,) * 96, ((1.0,) * 96,), (1.0,) * 96, (1.0,) * 96, "test")
    result = representative_days(periods, 4)
    assert result.counts == (1, 1, 1, 1)


def test_reduction_rejects_repeated_blocks():
    periods = synthetic_periods(system_from_config(default_config()), 168)
    with pytest.raises(ValueError, match="unweighted"):
        representative_days(periods, 4)


def test_real_lp_reduction_reports_storage_error_without_validation_claim():
    system = system_from_config(default_config())
    periods = synthetic_periods(system, 72, annual_hours=72)
    report = dispatch_reduction(system, periods, system.capacity(2026), 3)
    assert report["weighted_hours"] == 72
    assert report["peak_demand_relative_error"] == 0
    assert report["metrics"]["demand_mwh"]["relative_error"] < 1e-12
    assert "storage_throughput_mwh" in report["metrics"]
    assert not report["empirical_validation"]


def test_signed_price_metrics_and_zero_denominators():
    assert price_metrics(np.array([-50, 0, 50]), np.array([-50, 0, 50]))["ks_distance"] == 0
    assert price_metrics(np.ones(3), np.zeros(3))["nmae"] is None
    assert price_metrics(np.ones(3), np.zeros(3))["ks_distance"] == 1
    assert relative_error(1, 0) is None and relative_error(0, 0) == 0
    assert generation_share_mae_pp(np.array([25, 75]), np.array([50, 50])) == 25


@pytest.mark.parametrize("bad", [np.array([np.nan]), np.array([])])
def test_metrics_reject_missing_data(bad):
    with pytest.raises(ValueError):
        price_metrics(bad, bad)


def test_capacity_metrics_known_values():
    result = capacity_metrics(np.array([[20, 80]]), np.array([[50, 50]]))
    assert result == pytest.approx(
        {"share_mae_pp": 30.0, "total_relative_error_max": 0.0, "wmape": 0.6}
    )


def test_sensitivity_exposes_budget_capped_zero_response():
    result = sensitivity_screen(np.array([[0], [1], [2]]), np.ones((3, 2)))
    assert not result["passed_linear_screen"] and result["response_rank"] == 0
    assert result["constant_targets"] == [0, 1]


def test_sensitivity_rejects_confounded_search():
    result = sensitivity_screen(
        np.array([[0, 0], [1, 1], [2, 2]]), np.array([[1, 2], [2, 4], [3, 6]])
    )
    assert result["design_rank"] == 1 and not result["passed_linear_screen"]


def test_seed_minimum_and_zero_effect_are_not_tuned_away():
    assert not seed_convergence(np.zeros(20))["passed"]
    assert seed_convergence(np.zeros(100))["passed"]
    assert not seed_convergence(np.arange(100))["passed"]


def test_rolling_trend_uses_only_prior_years_and_perfect_baseline_is_not_beaten():
    history = np.array([[1], [2], [3], [4]], dtype=float)
    report = rolling_baselines(history, history.copy())
    assert report["persistence"]["relative_improvement"] == 1
    assert report["linear_trend"]["relative_improvement"] is None
    assert report["linear_trend"]["strict_win_fraction"] == 0
    history[-1] = 100
    report = rolling_baselines(history, history.copy())
    assert report["linear_trend"]["baseline_mae_mw"] == 48


def test_settlement_kernels_signed_and_not_double_derated():
    assert cfd_transfer(100, 50, 70) == -2000
    assert cfd_transfer(100, 50, -10) == 6000
    assert capacity_obligation_transfer(80, 20, 0.5) == 800000
    with pytest.raises(ValueError):
        capacity_obligation_transfer(80, 20, 2)
