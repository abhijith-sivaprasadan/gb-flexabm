"""Cross-variant, complete-evidence audit of registered MX01 synthetic experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gb_flexabm.investor_mechanisms import CASES, SEEDS, physical_contract_hash
from gb_flexabm.policy_identification import examine_policy_identification
from gb_flexabm.provenance import canonical_hash, verify_run


def audit_case(path: Path, case: str) -> dict:
    """Refuse partial case archives and orphaned report files."""
    source = verify_run(path)
    ident = json.loads((path / "identification.json").read_text(encoding="utf-8"))
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    if ident["case"] != case or config["assumption_source"] != (
        f"REGISTERED_SYNTHETIC_MX01:{case}. Not sourced/calibrated GB investor data."
    ):
        raise ValueError("Study case identity does not match configuration")
    if ident["physical_contract_sha256"] != physical_contract_hash(config):
        raise ValueError("Common physical model changed or misreported")
    if source["config_sha256"] != ident["case_config_sha256"]:
        raise ValueError("Case config hash mismatch")
    if ident["seeds"] != list(SEEDS) or source["random_seeds"] != list(SEEDS):
        raise ValueError("Incomplete or unexpected 12-seed study")
    reread = examine_policy_identification(path)
    if reread != ident["audit"]:
        raise ValueError("Policy identification summary differs from original raw CSV")
    data = pd.read_csv(path / "summary.csv")
    annual = pd.read_csv(path / "annual.csv")
    decisions = pd.read_csv(path / "decisions.csv")
    energy = data[data.design == "energy_only"]
    paid = data[data.design == "stylised_capacity_payment"]
    if len(energy) != len(SEEDS) or len(paid) != len(SEEDS):
        raise ValueError("Incomplete design and seed coverage")
    policy_cost = paid.set_index("seed").resource_npv_gbp - energy.set_index("seed").resource_npv_gbp
    if not np.isfinite(policy_cost).all():
        raise ValueError("Nonfinite policy comparison")
    prior = annual.loc[annual.design == "energy_only"]
    built = decisions.loc[decisions.design == "energy_only"]
    return {
        "case": case,
        "experiment_status": ident["experiment"],
        "n_matched_seeds": len(SEEDS),
        "npv_resource_gbp_mean": float(energy.resource_npv_gbp.mean()),
        "planner_npv_gbp_mean": float(energy.planner_npv_gbp.mean()),
        "planner_gap_gbp_mean": float(energy.resource_gap_gbp.mean()),
        "six_year_unserved_mwh_mean_per_seed": float(prior.unserved_mwh.sum() / len(SEEDS)),
        "total_accepted_mw_mean_per_seed": float(built.accepted_mw.sum() / len(SEEDS)),
        "payment_resource_npv_difference_mean_gbp": float(policy_cost.mean()),
        "payment_resource_npv_difference_max_abs_gbp": float(abs(policy_cost).max()),
        "seeds_zero_payment_response": int((abs(policy_cost) <= 0.01).sum()),
        "paid_transfer_gbp_mean_per_seed": ident["audit"][
            "mean_annual_horizon_capacity_transfer_paid_gbp_per_seed"
        ],
        "config_sha256": source["config_sha256"],
        "source_manifest_id": source["run_id"],
        "identification_sha256": canonical_hash(ident),
    }


def compare_cases(paths: dict[str, Path]) -> dict:
    if set(paths) != set(CASES):
        raise ValueError("Exactly all five preregistered cases required")
    records = [audit_case(paths[name], name) for name in CASES]
    hashes = {json.loads((paths[r["case"]] / "identification.json").read_text())[
        "physical_contract_sha256"
    ] for r in records}
    if len(hashes) != 1:
        raise ValueError("Modelled physical system differs across investor cases")
    if any(row["n_matched_seeds"] != 12 for row in records):
        raise ValueError("Incomplete random seed coverage")
    baseline = records[0]
    for row in records:
        row["resource_cost_difference_vs_baseline_gbp"] = (
            row["npv_resource_gbp_mean"] - baseline["npv_resource_gbp_mean"]
        )
        row["accepted_build_difference_vs_baseline_mw_per_seed"] = (
            row["total_accepted_mw_mean_per_seed"]
            - baseline["total_accepted_mw_mean_per_seed"]
        )
    return {
        "status": "FULL_REGISTERED_SYNTHETIC_MX01_CROSSCASE_AUDIT",
        "all_60_pairs_zero_resource_response_to_1penny": all(
            row["seeds_zero_payment_response"] == 12 for row in records
        ),
        "registered_before_experiment": True,
        "original_data_calibration": False,
        "units": "Cost: illustrative GBP discounted to synthetic 2026 base; build MW",
        "rows": records,
        "interpretation": (
            "No sensitivity to the stylised payment in 60 synthetic seed pairs. "
            "Strong response to assumed budgets; no empirical GB market inference."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Do not overwrite scientific comparison")
    # Actions download-artifact flattens each stored case into its own directory
    # under --root, named for the artifact. No opportunistic directory search.
    paths = {name: args.root / f"mx01-{name}-raw" for name in CASES}
    result = compare_cases(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
