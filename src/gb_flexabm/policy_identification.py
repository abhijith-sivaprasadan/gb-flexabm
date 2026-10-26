"""Reconstruct what the synthetic capacity-payment experiment actually identifies.

Never equate monetary transfers with physical resource-cost improvements.
Every comparison must be a keyed, paired seed (and year/investor) match from
a hash-verified local run. The outputs are accounting/decision diagnostics,
not calibrated GB policy effects.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .provenance import verify_run

DESIGNS = ("energy_only", "stylised_capacity_payment")
PHYSICAL_COLUMNS = (
    "variable_resource_cost_gbp",
    "unserved_mwh",
    "emissions_t",
    "renewable_curtailment_mwh",
    "demand_mwh",
)


def _paired(frame: pd.DataFrame, keys: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {*keys, "design"}
    if not required.issubset(frame):
        raise ValueError(f"Missing paired identification keys: {sorted(required - set(frame))}")
    if set(frame.design) != set(DESIGNS):
        raise ValueError("Exactly two known synthetic payment designs required")
    if frame.duplicated([*keys, "design"]).any():
        raise ValueError("Duplicated seed/decision identifiers")
    a = frame.loc[frame.design == DESIGNS[0]].set_index(keys).sort_index()
    b = frame.loc[frame.design == DESIGNS[1]].set_index(keys).sort_index()
    if not a.index.equals(b.index) or a.empty:
        raise ValueError("Missing matched seed/year/investor rows")
    return a, b


def _max_abs_delta(a: pd.DataFrame, b: pd.DataFrame, cols: list[str]) -> dict[str, float]:
    if not set(cols).issubset(a) or not set(cols).issubset(b):
        raise ValueError("Paired numerical metric missing")
    left, right = a[cols].astype(float), b[cols].astype(float)
    if not np.isfinite(left.to_numpy()).all() or not np.isfinite(right.to_numpy()).all():
        raise ValueError("Nonfinite paired evidence")
    return {c: float(np.max(np.abs(right[c] - left[c]))) for c in cols}


def examine_policy_identification(directory: Path) -> dict:
    manifest = verify_run(directory)
    if manifest["kind"] != "paired_abm_planner":
        raise ValueError("Expected verified paired experimental run, not external GB data")
    annual = pd.read_csv(directory / "annual.csv")
    decisions = pd.read_csv(directory / "decisions.csv")
    summary = pd.read_csv(directory / "summary.csv")
    settlements = pd.read_csv(directory / "settlements.csv")
    sa, sb = _paired(summary, ["seed"])
    da, db = _paired(decisions, ["seed", "year", "investor"])
    aa, ab = _paired(annual, ["seed", "year"])
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    paid = float(config["capacity_price_gbp_per_kw_year"])
    if not np.isfinite(paid) or paid <= 0:
        raise ValueError("Positive stylised payment level required for identification")

    investments = _max_abs_delta(da, db, ["requested_mw", "accepted_mw"])
    physical_fields = [
        *PHYSICAL_COLUMNS,
        *[c for c in aa if c.startswith("capacity_") and c.endswith("_mw")],
    ]
    physical = _max_abs_delta(aa, ab, physical_fields)
    resource = _max_abs_delta(sa, sb, ["resource_npv_gbp", "resource_gap_gbp"])
    for c in ("year", "seed", "design", "capacity_payment_gbp"):
        if c not in settlements:
            raise ValueError(f"Missing settlement field: {c}")
    transfers = settlements.groupby(["seed", "design"])["capacity_payment_gbp"].sum()
    year_transfers = annual.groupby(["seed", "design"])["capacity_payment_gbp"].sum()
    if not transfers.index.equals(year_transfers.index) or not np.allclose(
        transfers.to_numpy(), year_transfers.to_numpy(), rtol=1e-10, atol=0.01
    ):
        raise ValueError("Annual transfer costs disagree with asset settlements")
    by_seed = year_transfers.unstack("design").reindex(sa.index)
    if not np.allclose(by_seed[DESIGNS[0]], 0, atol=0.01):
        raise ValueError("Energy-only counterfactual has capacity transfer")
    mean_paid = float(by_seed[DESIGNS[1]].mean())

    positive = da["score_gbp_per_mw"].astype(float) > 0
    request = da["requested_mw"].astype(float)
    accepted = da["accepted_mw"].astype(float)
    if not np.isfinite(da["score_gbp_per_mw"]).all() or (request < 0).any():
        raise ValueError("Invalid investor decision evidence")
    labels = {
        "positive_npv_score_rows": int(positive.sum()),
        "positive_npv_and_requested_build_rows": int((positive & (request > 0)).sum()),
        "positive_npv_but_no_request_rows": int((positive & (request == 0)).sum()),
        "requested_mw_total_all_seeds": float(request.sum()),
        "accepted_mw_total_all_seeds": float(accepted.sum()),
    }
    all_response_null = (
        all(x <= 1e-5 for x in investments.values())
        and all(x <= 1e-4 for x in physical.values())
        and all(x <= 0.01 for x in resource.values())
    )
    return {
        "status": "AUDITED_SYNTHETIC_POLICY_IDENTIFICATION",
        "source_run_id": manifest["run_id"],
        "config_sha256": manifest["config_sha256"],
        "seeds": sa.index.tolist(),
        "n_matched_seed_year_investor_rows": len(da),
        "market_payment_gbp_per_kw_year": paid,
        "resource_npv_mean_energy_only_gbp": float(sa["resource_npv_gbp"].mean()),
        "planner_gap_mean_energy_only_gbp": float(sa["resource_gap_gbp"].mean()),
        "mean_annual_horizon_capacity_transfer_paid_gbp_per_seed": mean_paid,
        "sum_capacity_transfers_across_all_seeds_gbp": float(by_seed[DESIGNS[1]].sum()),
        "max_abs_paired_requested_accepted_delta_mw": investments,
        "max_abs_paired_physical_delta": physical,
        "max_abs_paired_resource_delta_gbp": resource,
        "observed_policy_induced_physical_response": not all_response_null,
        "investor_decision_diagnostics": labels,
        "interpretation": (
            "A model-internal paired diagnostic, not GB Capacity Market impact. "
            "A null response is consistent with investment request saturation/terminal "
            "eligibility under these stylised assumptions. No causal claim for GB."
        ),
        "historical_calibration_complete": False,
    }
