"""Analytic frontier must agree with implementation on *authored* cases."""

from dataclasses import replace

import pytest

from gb_flexabm.agents import Investor
from gb_flexabm.investor_frontiers import investment_entry_frontier
from gb_flexabm.schema import Technology


def specimen():
    tech = Technology("wind", 1_000_000, 10_000, 5, 0, 25, 2, 500, 0.4, "wind")
    investor = Investor("a", "wind", 0.08, 0.4, 0.0, 0.0, 200_000_000, 25)
    return tech, investor


def test_frontier_exactly_matches_strict_npv_request_switch():
    tech, investor = specimen()
    edge = investment_entry_frontier(investor, tech, 15_000, decision_year=2026, last_year=2031)
    p = edge.payment_needed_gbp_per_kw_year
    assert p is not None and p > 0
    below, _ = investor.request(tech, 15_000, p - 1e-4)
    above, _ = investor.request(tech, 15_000, p + 1e-4)
    assert below == 0
    assert above > 0


def test_payments_cannot_overcome_zero_budget_or_past_horizon():
    tech, investor = specimen()
    zero = investment_entry_frontier(
        replace(investor, annual_budget_gbp=0),
        tech,
        15_000,
        decision_year=2026,
        last_year=2031,
    )
    assert zero.payment_cannot_change_build
    assert zero.payment_needed_gbp_per_kw_year is None
    terminal = investment_entry_frontier(investor, tech, 15_000, decision_year=2030, last_year=2031)
    assert not terminal.commission_within_horizon
    assert terminal.payment_needed_gbp_per_kw_year is None


def test_derating_zero_prevents_capacity_payment_response():
    tech, investor = specimen()
    result = investment_entry_frontier(
        investor, replace(tech, derating=0), 15_000, decision_year=2026, last_year=2031
    )
    assert result.payment_needed_gbp_per_kw_year is None


def test_bad_sources_and_mismatched_owner_rejected():
    tech, investor = specimen()
    with pytest.raises(ValueError, match="mismatch"):
        investment_entry_frontier(
            replace(investor, technology="gas"), tech, 15_000, decision_year=2026, last_year=2031
        )
