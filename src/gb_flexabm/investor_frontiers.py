"""Analytic entry/reachability conditions implied by the *implemented* investor rule.

This is NOT a fitted behavioural mechanism and makes no assertion about actual
GB generators. Project requests are binary in profitability, then clipped by
a fixed exogenous investor budget and technology build ceilings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .agents import Investor, project_npv
from .schema import Technology


@dataclass(frozen=True)
class InvestmentEntryFrontier:
    payment_needed_gbp_per_kw_year: float | None
    payment_cannot_change_build: bool
    block_finance_feasible: bool
    commission_within_horizon: bool
    score_at_zero_payment_gbp_per_mw: float
    budget_limited_request_mw_if_positive: float


def investment_entry_frontier(
    investor: Investor,
    technology: Technology,
    expected_energy_margin_gbp_per_mw: float,
    *,
    decision_year: int,
    last_year: int,
) -> InvestmentEntryFrontier:
    """Exact algebra for current Investor.request, holding expectations fixed."""
    if investor.technology != technology.name:
        raise ValueError("Investor and technology mismatch")
    if not math.isfinite(expected_energy_margin_gbp_per_mw):
        raise ValueError("Expected energy margin must be finite")
    if type(decision_year) is not int or type(last_year) is not int:
        raise ValueError("Decision years must be integers")
    risk = (
        investor.risk_aversion
        * investor.forecast_noise_fraction
        * abs(expected_energy_margin_gbp_per_mw)
    )
    factor = sum(
        (1 + investor.hurdle_rate) ** -j
        for j in range(
            technology.construction_years,
            technology.construction_years + technology.lifetime_years,
        )
    )
    score0 = project_npv(
        technology,
        expected_energy_margin_gbp_per_mw - technology.fixed_cost_gbp_per_mw_year - risk,
        investor.hurdle_rate,
    )
    can_commission = decision_year + technology.construction_years <= last_year
    affordable = (
        technology.capex_gbp_per_mw > 0
        and investor.annual_budget_gbp >= technology.capex_gbp_per_mw * investor.project_size_mw
    )
    requests_if_positive = 0.0
    if affordable and can_commission:
        requests_if_positive = min(
            math.floor(
                investor.annual_budget_gbp
                / (technology.capex_gbp_per_mw * investor.project_size_mw)
            )
            * investor.project_size_mw,
            technology.max_build_mw_per_year,
        )
    payable = (
        technology.derating > 0
        and factor > 0
        and affordable
        and can_commission
        and requests_if_positive > 0
    )
    needed = None
    if payable:
        needed = max(
            0.0,
            (
                (investor.threshold_gbp_per_mw + technology.capex_gbp_per_mw) / factor
                - expected_energy_margin_gbp_per_mw
                + technology.fixed_cost_gbp_per_mw_year
                + risk
            )
            / (1000 * technology.derating),
        )
    return InvestmentEntryFrontier(
        payment_needed_gbp_per_kw_year=needed,
        payment_cannot_change_build=not payable or (
            score0 > investor.threshold_gbp_per_mw
        ),
        block_finance_feasible=bool(affordable),
        commission_within_horizon=can_commission,
        score_at_zero_payment_gbp_per_mw=score0,
        budget_limited_request_mw_if_positive=requests_if_positive,
    )
