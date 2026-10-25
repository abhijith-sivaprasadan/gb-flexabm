import copy
import json
from pathlib import Path

import pytest

from gb_flexabm.product_coverage import compare_product_coverage

ROOT = Path(__file__).resolve().parents[1]


def records():
    return [
        json.loads((ROOT / path).read_text())
        for path in (
            "docs/reference/training-market-mid.json",
            "docs/reference/training-market-fuelhh.json",
            "studies/historical-v1/imrp-coverage-probe.json",
        )
    ]


def test_real_coverage_is_not_silently_repaired():
    report = compare_product_coverage(*records())
    assert report["decision"] == "NO_SUBSTITUTION"
    assert report["complete_original_market_years"] == 0
    assert report["complete_original_generation_years"] == 0
    assert [r["separate_hourly_native_rows"] for r in report["rows"]] == [
        0,
        0,
        0,
        4441,
        8760,
        8760,
    ]


def test_product_identity_swapping_fails():
    mid, fuel, alternate = records()
    modified = copy.deepcopy(alternate)
    modified["matches_original_target_semantics"] = True
    with pytest.raises(ValueError, match="cannot be treated"):
        compare_product_coverage(mid, fuel, modified)


def test_partial_inventory_fails():
    mid, fuel, alternate = records()
    modified = copy.deepcopy(alternate)
    del modified["years"]["2013"]
    with pytest.raises(ValueError, match="training-year inventory"):
        compare_product_coverage(mid, fuel, modified)
