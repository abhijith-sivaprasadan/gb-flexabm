"""Reconstruct investor entry decisions from hash-verified synthetic experiment files.

This is a mechanistic diagnostic of the current implementation, not an
empirical causal estimate of GB capacity-market policy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .agents import Investor
from .investor_frontiers import investment_entry_frontier
from .policy_identification import DESIGNS, _paired, examine_policy_identification
from .schema import system_from_config


def audit_investor_response(directory: Path) -> dict:
    """Check every saved request/NPV score against the source investor rule."""
    identified = examine_policy_identification(directory)
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    years = config["years"]
    techs = {tech.name: tech for tech in system_from_config(config).technologies}
    investors = {i.investor_id: i for i in (Investor(**entry) for entry in config["investors"])}
    frame = pd.read_csv(directory / "decisions.csv")
    energy, paid = _paired(frame, ["seed", "year", "investor"])
    matched = 0
    equal_expectations = 0
    already_eligible = 0
    budget_blocked = 0
    horizon_blocked = 0
    entry_crossed = 0
    payment_too_small = 0
    switched_requests = 0
    switched_accepted = 0
    limited_by_tech_cap = 0
    highest_expected_shift = 0.0
    price = config["capacity_price_gbp_per_kw_year"]

    for (key, row), (paired_key, control) in zip(energy.iterrows(), paid.iterrows(), strict=True):
        if not isinstance(key, tuple) or len(key) != 3 or key != paired_key:
            raise ValueError("Mismatched decision index")
        seed, year, investor_id = key
        if (
            (type(seed) is not int and not isinstance(seed, np.integer))
            or (type(year) is not int and not isinstance(year, np.integer))
            or year not in years
            or not isinstance(investor_id, str)
            or investor_id not in investors
        ):
            raise ValueError("Unknown decision seed/year/investor")
        investor = investors[investor_id]
        tech = techs[investor.technology]
        for design, record, payment in (
            (DESIGNS[0], row, 0.0),
            (DESIGNS[1], control, price),
        ):
            if record["technology"] != tech.name:
                raise ValueError("Decision technology does not match investor contract")
            if int(record["commission_year"]) != year + tech.construction_years:
                raise ValueError("Inconsistent project commissioning year")
            margin = float(record["expected_energy_margin_gbp_per_mw"])
            requested, score = investor.request(tech, margin, payment)
            if year + tech.construction_years > years[-1]:
                requested = 0.0
            if not np.isclose(score, record["score_gbp_per_mw"], rtol=1e-10, atol=0.01):
                raise ValueError(f"{design} NPV score disagrees with investor source rule")
            if not np.isclose(requested, record["requested_mw"], rtol=1e-10, atol=1e-7):
                raise ValueError(f"{design} requested investment disagrees with source rule")
            if (
                not np.isfinite(record["accepted_mw"])
                or record["accepted_mw"] < -1e-8
                or record["accepted_mw"] > requested + 1e-7
            ):
                raise ValueError("Accepted construction exceeds valid request")
        matched += 1
        a_margin = float(row["expected_energy_margin_gbp_per_mw"])
        b_margin = float(control["expected_energy_margin_gbp_per_mw"])
        shift = abs(a_margin - b_margin)
        highest_expected_shift = max(highest_expected_shift, shift)
        if shift <= max(1e-6, abs(a_margin) * 1e-9):
            equal_expectations += 1
        else:
            # Future price expectations may themselves respond to changed fleet.
            # Never reinterpret the paired outcome as an isolated NPV shift.
            continue
        frontier = investment_entry_frontier(
            investor, tech, a_margin, decision_year=int(year), last_year=years[-1]
        )
        if not frontier.commission_within_horizon:
            horizon_blocked += 1
        elif not frontier.block_finance_feasible:
            budget_blocked += 1
        elif frontier.score_at_zero_payment_gbp_per_mw > investor.threshold_gbp_per_mw:
            already_eligible += 1
        elif (
            frontier.payment_needed_gbp_per_kw_year is not None
            and price > frontier.payment_needed_gbp_per_kw_year + 1e-9
        ):
            entry_crossed += 1
        else:
            payment_too_small += 1
        if not np.isclose(row["requested_mw"], control["requested_mw"], atol=1e-7):
            switched_requests += 1
        if not np.isclose(row["accepted_mw"], control["accepted_mw"], atol=1e-7):
            switched_accepted += 1
        if float(row["requested_mw"]) > 0 and float(row["accepted_mw"]) + 1e-7 < float(
            row["requested_mw"]
        ):
            limited_by_tech_cap += 1
    if matched != len(energy):
        raise ValueError("Unmatched decision records")
    if switched_requests == 0 and identified["observed_policy_induced_physical_response"]:
        # A physical response could occur through changed expectations or
        # alternative accepted construction; do not claim a null mechanism.
        pass
    return {
        "status": "VERIFIED_SYNTHETIC_INVESTOR_ENTRY_DIAGNOSTIC",
        "source_run_id": identified["source_run_id"],
        "matched_seed_year_investor_pairs": matched,
        "constant_expectation_pairs": equal_expectations,
        "endogenous_expectation_shift_pairs": matched - equal_expectations,
        "max_abs_paired_expectation_shift_gbp_per_mw": highest_expected_shift,
        "entry_cause_counts_on_common_expectations": {
            "already_profitable_without_payment": already_eligible,
            "not_affordable_in_project_blocks": budget_blocked,
            "cannot_commission_within_horizon": horizon_blocked,
            "payment_crosses_npv_threshold": entry_crossed,
            "payment_below_npv_threshold_or_unreachable": payment_too_small,
        },
        "requested_mw_changed_pairs_with_common_expectations": switched_requests,
        "accepted_mw_changed_pairs_with_common_expectations": switched_accepted,
        "energy_only_build_requests_partially_rationed_rows": limited_by_tech_cap,
        "historical_validation": False,
        "interpretation": (
            "Reconstructed investor NPV and requested construction from the archived "
            "margins and current source rules; common-expectation frontier classification "
            "is not applied to pairs with changing expectations. Neither a GB forecast "
            "skill test nor a capacity-market treatment effect."
        ),
    }
