"""Fixed synthetic policy-identification experiment, NOT historical calibration.

Run after committing docs/INVESTOR_MECHANISM_STUDY_MX01.md. Investor-only
levers keep the shared physical dispatch/planner contract unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .cli import default_config, run_demo
from .policy_identification import examine_policy_identification
from .provenance import canonical_hash

CASES = (
    "baseline",
    "budget_20pct",
    "budget_zero",
    "high_hurdle",
    "zero_expectation_noise",
)
SEEDS = tuple(range(401, 413))


def configuration(case: str) -> dict:
    """Never mutate the installed project fixture."""
    if case not in CASES:
        raise ValueError(f"Case is not among fixed registered variants: {case}")
    cfg = copy.deepcopy(default_config())
    investors = cfg["investors"]
    if case == "budget_20pct":
        for investor in investors:
            investor["annual_budget_gbp"] *= 0.2
    elif case == "budget_zero":
        for investor in investors:
            investor["annual_budget_gbp"] = 0
    elif case == "high_hurdle":
        for investor in investors:
            investor["hurdle_rate"] += 0.15
    elif case == "zero_expectation_noise":
        for investor in investors:
            investor["forecast_noise_fraction"] = 0
    cfg["assumption_source"] = (
        f"REGISTERED_SYNTHETIC_MX01:{case}. Not sourced/calibrated GB investor data."
    )
    return cfg


def physical_contract_hash(config: dict) -> str:
    # Investor-only interventions must never silently change dispatch,
    # planner, payment definition, technology CAPEX or physical chronology.
    return canonical_hash({k: v for k, v in config.items() if k not in {"investors", "assumption_source"}})


def run_case(case: str, output: Path) -> dict:
    config = configuration(case)
    if physical_contract_hash(config) != physical_contract_hash(configuration("baseline")):
        raise ValueError("An investor mechanism changed the common physical/planner model")
    run_demo(config, list(SEEDS), output)
    policy = examine_policy_identification(output)
    summary = pd.read_csv(output / "summary.csv")
    sa = summary[summary.design == "energy_only"].set_index("seed").sort_index()
    sb = summary[summary.design == "stylised_capacity_payment"].set_index("seed").sort_index()
    if list(sa.index) != list(SEEDS) or not sa.index.equals(sb.index):
        raise ValueError("Missing matched registered seeds")
    differences = (sb["resource_npv_gbp"] - sa["resource_npv_gbp"]).to_numpy()
    if not np.isfinite(differences).all():
        raise ValueError("Missing/invalid paired monetary differences")
    report = {
        "experiment": "REGISTERED_SYNTHETIC_INVESTOR_MX01",
        "case": case,
        "seeds": list(SEEDS),
        "physical_contract_sha256": physical_contract_hash(config),
        "case_config_sha256": canonical_hash(config),
        "n_complete_seed_pairs": len(differences),
        "paired_policy_resource_cost_differences_gbp": differences.tolist(),
        "mean_policy_resource_difference_gbp": float(differences.mean()),
        "median_policy_resource_difference_gbp": float(np.median(differences)),
        "q10_policy_resource_difference_gbp": float(np.quantile(differences, 0.10)),
        "q90_policy_resource_difference_gbp": float(np.quantile(differences, 0.90)),
        "count_seeds_no_effect_to_1penny": int((abs(differences) <= 0.01).sum()),
        "mean_planner_npv_gbp": float(sa["planner_npv_gbp"].mean()),
        "audit": policy,
        "historical_empirical_fit": False,
        "calibrated_policy_effect": False,
    }
    result_path = output / "identification.json"
    if result_path.exists():
        raise FileExistsError("Do not overwrite source identification output")
    result_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report
