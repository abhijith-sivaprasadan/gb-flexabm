"""Source-rule NPV reconstruction on the committed synthetic reference experiment."""

from pathlib import Path

import pandas as pd
import pytest

from gb_flexabm.investor_response_audit import audit_investor_response

REFERENCE = Path("docs/reference/experiment")


def test_reference_reconstructs_all_decisions_without_empirical_overclaim():
    report = audit_investor_response(REFERENCE)
    assert report["status"] == "VERIFIED_SYNTHETIC_INVESTOR_ENTRY_DIAGNOSTIC"
    assert report["matched_seed_year_investor_pairs"] == 20 * 6 * 5
    assert report["constant_expectation_pairs"] == report["matched_seed_year_investor_pairs"]
    counts = report["entry_cause_counts_on_common_expectations"]
    assert sum(counts.values()) == report["constant_expectation_pairs"]
    assert counts["already_profitable_without_payment"] > 0
    assert counts["cannot_commission_within_horizon"] > 0
    assert report["requested_mw_changed_pairs_with_common_expectations"] == 0
    assert report["historical_validation"] is False


@pytest.mark.parametrize(
    "column,value",
    [
        ("score_gbp_per_mw", -987654.0),
        ("requested_mw", 123.0),
        ("accepted_mw", 2000000.0),
    ],
)
def test_tampered_decision_evidence_is_rejected(tmp_path, column, value):
    from shutil import copytree

    copytree(REFERENCE, tmp_path / "run")
    decisions = tmp_path / "run" / "decisions.csv"
    frame = pd.read_csv(decisions)
    frame.loc[0, column] = value
    frame.to_csv(decisions, index=False)
    with pytest.raises(ValueError):
        audit_investor_response(tmp_path / "run")
