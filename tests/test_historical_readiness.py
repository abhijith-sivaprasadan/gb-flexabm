"""The committed snapshots must fail closed; tests never simulate observed fits."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from gb_flexabm.historical_readiness import audit_historical_readiness

ROOT = Path(__file__).resolve().parents[1]


def evidence():
    paths = (
        "studies/historical-v1/protocol.json",
        "docs/reference/training-demand-audit.json",
        "docs/reference/training-market-mid.json",
        "docs/reference/training-market-fuelhh.json",
        "docs/reference/public-inputs-inventory.json",
    )
    return [json.loads((ROOT / path).read_text(encoding="utf-8")) for path in paths]


def test_committed_empirical_admission_is_blocked():
    actual = audit_historical_readiness(*evidence())
    assert actual["status"] == "NOT_READY_FOR_HISTORICAL_CALIBRATION_OR_CLAIMS"
    assert actual["training_years"] == list(range(2013, 2019))
    assert actual["observed_demand_annual_completeness_count"] == 6
    assert actual["price_usable_years"] == 0
    assert actual["archived_audit_matches_current_protocol"] is False
    assert actual["generation_complete_years"] == 0
    assert "Study protocol is draft" in " | ".join(actual["blockers"])


def test_unsupported_price_replacement_is_rejected():
    p, d, price, gen, inventory = evidence()
    price = copy.deepcopy(price)
    price["dataset"] = "fuelhh"
    with pytest.raises(ValueError, match="roles are swapped"):
        audit_historical_readiness(p, d, price, gen, inventory)


def test_demand_completeness_fraud_is_rejected():
    p, d, price, gen, inventory = evidence()
    d = copy.deepcopy(d)
    d["years"][0]["observed_rows"] -= 1
    with pytest.raises(ValueError, match="Training demand summary contradicts"):
        audit_historical_readiness(p, d, price, gen, inventory)


def test_training_year_mismatch_is_rejected():
    p, d, price, gen, inventory = evidence()
    price = copy.deepcopy(price)
    price["years"].pop()
    with pytest.raises(ValueError, match="years do not match"):
        audit_historical_readiness(p, d, price, gen, inventory)


def test_protocol_digest_mismatch_is_rejected():
    p, d, price, gen, inventory = evidence()
    price = copy.deepcopy(price)
    price["protocol_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="different protocols"):
        audit_historical_readiness(p, d, price, gen, inventory)


def test_cannot_invent_model_ready_source_inventory():
    p, d, price, gen, inventory = evidence()
    inventory = copy.deepcopy(inventory)
    inventory["model_ready"] = True
    with pytest.raises(ValueError, match="not a verified model-ready bundle"):
        audit_historical_readiness(p, d, price, gen, inventory)
