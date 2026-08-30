from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gb_flexabm.agents import Investor, capacity_payment_gbp, project_npv, random_stream
from gb_flexabm.optimisation import dispatch, planner
from gb_flexabm.schema import Asset, Periods, Storage, System, Technology
from gb_flexabm.simulation import simulate


def simple_system(cost=50, capacity=100, storage=None):
    tech = Technology("gas", 1000, 0, cost, 0.4, 10, 1, 100, 0.9)
    return System(
        (tech,),
        (Asset("a", "owner", "gas", capacity, 2020, 2030),),
        storage or Storage(),
        6000,
        0.05,
    )


def periods(demand=(40.0,), availability=None, duration=1.0, occurrences=1.0):
    n = len(demand)
    return Periods(
        tuple(demand), availability or ((1.0,) * n,), (duration,) * n, (occurrences,) * n, "test"
    )


@given(
    load=st.floats(min_value=1, max_value=90, allow_nan=False),
    cost=st.floats(min_value=1, max_value=200, allow_nan=False),
    dt=st.sampled_from([0.5, 1.0, 2.0]),
    repeats=st.sampled_from([1.0, 52.0, 365.0]),
)
@settings(max_examples=15, deadline=None)
def test_known_optimum_dual_price_and_weights(load, cost, dt, repeats):
    system = simple_system(cost)
    result = dispatch(system, periods((load,), duration=dt, occurrences=repeats), np.array([100.0]))
    assert result.summary["variable_resource_cost_gbp"] == pytest.approx(load * cost * dt * repeats)
    assert result.hourly.price_gbp_per_mwh.iloc[0] == pytest.approx(cost)
    assert all(result.checks.values())


def test_scarcity_is_explicit_unserved_energy_not_probabilistic_lole():
    result = dispatch(simple_system(capacity=30), periods((50.0,), duration=0.5), np.array([30.0]))
    assert result.summary["unserved_mwh"] == pytest.approx(10)
    assert result.summary["scarcity_hours"] == pytest.approx(0.5)
    assert result.hourly.price_gbp_per_mwh.iloc[0] == pytest.approx(6000)


def test_zero_demand_and_no_involuntary_generation():
    result = dispatch(simple_system(), periods((0.0, 0.0)), np.array([100.0]))
    assert np.max(np.abs(result.generation_mw)) == 0
    assert result.summary["variable_resource_cost_gbp"] == 0


def test_lossless_storage_shift_and_occurrences_do_not_multiply_soc():
    system = simple_system(cost=1, storage=Storage(50, 100, 1, 1, 0))
    peaker = replace(system.technologies[0], name="peaker", variable_cost_gbp_per_mwh=100)
    system = replace(system, technologies=(system.technologies[0], peaker))
    p = Periods(
        (0.0, 50.0),
        ((1.0, 0.0), (1.0, 1.0)),
        (1.0, 1.0),
        (10.0, 10.0),
        "ten-repeated-two-hour-blocks",
    )
    result = dispatch(system, p, np.array([50.0, 50.0]))
    assert result.summary["variable_resource_cost_gbp"] == pytest.approx(500)
    assert result.hourly.charge_mw.iloc[0] == pytest.approx(50)
    assert result.hourly.discharge_mw.iloc[1] == pytest.approx(50)
    assert result.hourly.soc_end_mwh.iloc[-1] == pytest.approx(50)


def test_more_capacity_cannot_raise_dispatch_cost():
    s, p = simple_system(), periods((150.0,))
    assert (
        dispatch(s, p, np.array([100.0])).summary["variable_resource_cost_gbp"]
        <= dispatch(s, p, np.array([50.0])).summary["variable_resource_cost_gbp"]
    )


def test_voll_increase_does_not_increase_shedding():
    s, p = simple_system(), periods((150.0,))
    low = dispatch(replace(s, voll_gbp_per_mwh=20), p, np.array([100.0]))
    high = dispatch(s, p, np.array([100.0]))
    assert high.summary["unserved_mwh"] <= low.summary["unserved_mwh"]


def test_planner_builds_after_lag_and_recomputes_resource_objective():
    system = simple_system(capacity=0)
    plan = planner(
        system, {2026: periods((20.0,), occurrences=8760), 2027: periods((20.0,), occurrences=8760)}
    )
    assert plan.annual.capacity_gas_mw.iloc[0] == 0
    assert plan.annual.capacity_gas_mw.iloc[1] == pytest.approx(20)
    assert plan.builds.build_mw.iloc[-1] == 0
    assert plan.objective_gbp == pytest.approx(plan.independently_recomputed_gbp)


def test_relaxing_planner_build_limit_cannot_raise_optimum():
    system = simple_system(capacity=0)
    limited = replace(
        system, technologies=(replace(system.technologies[0], max_build_mw_per_year=5),)
    )
    p = {2026: periods((20.0,), occurrences=8760), 2027: periods((20.0,), occurrences=8760)}
    assert planner(system, p).objective_gbp <= planner(limited, p).objective_gbp


@given(
    capacity=st.floats(min_value=0, max_value=10000),
    derating=st.floats(min_value=0, max_value=1),
    price=st.floats(min_value=0, max_value=200),
)
def test_capacity_payment_mw_to_kw_units(capacity, derating, price):
    assert capacity_payment_gbp(capacity, derating, price) == pytest.approx(
        1000 * capacity * derating * price
    )


def test_npv_known_annuity_and_construction_delay():
    tech = simple_system().technologies[0]
    assert project_npv(tech, 100, 0) == pytest.approx(0)
    assert project_npv(replace(tech, construction_years=3), 100, 0.1) < project_npv(tech, 100, 0.1)


def test_named_random_stream_isolation():
    first = random_stream(4, "investor", "a").normal(size=10)
    random_stream(4, "unrelated").normal(size=1000)
    assert np.array_equal(first, random_stream(4, "investor", "a").normal(size=10))


def test_simulation_repeats_and_is_agent_order_invariant():
    s = simple_system(capacity=0)
    p = {y: periods((50.0,), occurrences=8760) for y in range(2026, 2029)}
    a = Investor("a", "gas", 0.1, 0.5, 0.1, 0.1, 50000, 10)
    b = replace(a, investor_id="b")
    first = simulate(s, p, (a, b), 42)
    repeat = simulate(s, p, (b, a), 42)
    pd.testing.assert_frame_equal(first.decisions, repeat.decisions)
    pd.testing.assert_frame_equal(
        first.annual.drop(columns="solve_seconds"), repeat.annual.drop(columns="solve_seconds")
    )
    assert all(first.checks.values())
    assert planner(s, p).objective_gbp <= first.resource_npv_gbp + 0.01
    assert first.annual.capacity_gas_mw.iloc[0] == 0


def test_asset_retirement_and_commission_years():
    a = Asset("a", "o", "gas", 10, 2027, 2030, 2026)
    assert not a.active(2026) and a.active(2027) and not a.active(2030)


@pytest.mark.parametrize("capacity", [[-1.0], [float("nan")], [1.0, 2.0]])
def test_invalid_capacity_fails(capacity):
    with pytest.raises(ValueError):
        dispatch(simple_system(), periods(), np.array(capacity))


@pytest.mark.parametrize("bad", [float("nan"), -1.0, float("inf")])
def test_invalid_demand_fails(bad):
    with pytest.raises(ValueError):
        periods((bad,))


def test_nonuniform_storage_block_weights_rejected():
    with pytest.raises(ValueError, match="uniform"):
        Periods((1.0, 1.0), ((1.0, 1.0),), (1.0, 1.0), (1.0, 2.0), "bad")


def test_nonoptimal_solver_result_is_never_loaded(monkeypatch):
    from types import SimpleNamespace

    from pyomo.opt import TerminationCondition

    from gb_flexabm import optimisation

    fake = SimpleNamespace(
        solve=lambda *args, **kwargs: SimpleNamespace(
            solver=SimpleNamespace(termination_condition=TerminationCondition.infeasible)
        )
    )
    monkeypatch.setattr(optimisation.pyo, "SolverFactory", lambda *args: fake)
    with pytest.raises(RuntimeError, match="No optimal solution"):
        dispatch(simple_system(), periods(), np.array([100.0]))


def test_requests_respect_budget_and_simultaneous_build_cap():
    s = simple_system(capacity=0)
    p = {y: periods((150.0,), occurrences=8760) for y in range(2026, 2029)}
    a = Investor("a", "gas", 0.05, 1, 0, 0, 80000, 10)
    b = replace(a, investor_id="b")
    result = simulate(s, p, (a, b), 11, 75)
    assert (result.decisions.requested_mw * 1000 <= 80000).all()
    assert (result.decisions.groupby("year").accepted_mw.sum() <= 100).all()
    first = result.decisions[result.decisions.year == 2026]
    assert first.accepted_mw.tolist() == [50, 50]


def test_capacity_payment_can_cross_an_investment_threshold():
    tech = simple_system().technologies[0]
    investor = Investor("threshold", "gas", 0.05, 1, 0, 0, 10000, 10)
    no_payment, negative_score = investor.request(tech, 0, 0)
    payment, positive_score = investor.request(tech, 0, 1)
    assert negative_score == -tech.capex_gbp_per_mw
    assert no_payment == 0
    assert positive_score > 0 and payment == 10


@pytest.mark.parametrize("year", [2026.5, True, float("nan")])
def test_asset_year_must_be_integer(year):
    with pytest.raises(ValueError, match="integer year"):
        Asset("a", "o", "gas", 10, year, 2030)
