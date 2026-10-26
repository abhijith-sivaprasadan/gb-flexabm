"""Policy effect vs accounting transfers: negative-controls on original evidence."""

from pathlib import Path

import pandas as pd
import pytest

from gb_flexabm.policy_identification import _paired, examine_policy_identification


REFERENCE = Path("docs/reference/experiment")


def test_reference_payment_changes_transfers_not_dispatch_or_builds():
    report = examine_policy_identification(REFERENCE)
    assert report["observed_policy_induced_physical_response"] is False
    assert report["sum_capacity_transfers_across_all_seeds_gbp"] > 0
    assert len(report["seeds"]) == 20
    assert report["investor_decision_diagnostics"]["positive_npv_score_rows"] == 600
    assert report["investor_decision_diagnostics"]["positive_npv_but_no_request_rows"] == 160
    assert report["historical_calibration_complete"] is False
    assert all(x <= 0.01 for x in report["max_abs_paired_resource_delta_gbp"].values())


def test_missing_pair_and_duplicate_pair_are_not_allowed():
    table = pd.DataFrame(
        {"seed": [1, 1], "design": ["energy_only", "stylised_capacity_payment"]}
    )
    a, b = _paired(table, ["seed"])
    assert a.index.equals(b.index)
    with pytest.raises(ValueError, match="Duplicated"):
        _paired(pd.concat([table, table.iloc[[0]]]), ["seed"])
    with pytest.raises(ValueError, match="Missing matched"):
        _paired(table.iloc[:1], ["seed"])
