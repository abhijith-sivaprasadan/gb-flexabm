"""Authored test tables are not historical study observations."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from gb_flexabm.calibration import TrainingView, fit_capacity_grid
from gb_flexabm.provenance import canonical_hash
from gb_flexabm.study import REQUIRED_ROLES, Protocol, StudyBundle, demand_audit


def protocol_record():
    return {
        "schema_version": 1,
        "status": "draft",
        "mode": "explanatory_backcast",
        "money_base_year": 2025,
        "splits": {"train": [2017, 2018], "validation": [2019], "holdout": [2020]},
        "prior_exposure": ["Authored offline test fixture, not actual observations"],
        "metrics": {"capacity_wmape": 0.15},
        "baselines": ["persistence"],
    }


@pytest.fixture
def bundle(tmp_path):
    protocol = Protocol.from_dict(protocol_record())
    frame = pd.DataFrame({"year": [2017], "technology": ["gas"], "capacity_mw": [100.0]})
    path = tmp_path / "fleet.csv"
    frame.to_csv(path, index=False)
    resource = {
        "role": "fleet",
        "year": 2017,
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_sha256": "a" * 64,
        "source_url": "https://example.org/authored-test-only",
        "licence": "MIT authored fixture",
        "boundary": "authored test, not GB data",
        "units": {"year": "year", "technology": "label", "capacity_mw": "MW"},
        "transform": "identity",
        "available_at_utc": "2026-08-31T00:00:00Z",
    }
    record = {"schema_version": 1, "protocol_sha256": protocol.identity, "resources": [resource]}
    return StudyBundle(tmp_path, record, protocol)


def test_protocol_is_immutable_and_splits_reject_overlap():
    source = protocol_record()
    p = Protocol.from_dict(source)
    source["splits"]["train"].append(2019)
    assert p.record["splits"]["train"] == [2017, 2018]
    with pytest.raises(ValueError, match="disjoint"):
        Protocol.from_dict(source)


@pytest.mark.parametrize(
    "phase,year", [("train", 2019), ("train", 2020), ("holdout", 2017), ("unknown", 2017)]
)
def test_guard_runs_before_file_read(bundle, monkeypatch, phase, year):
    def forbidden(*args, **kwargs):
        pytest.fail("Forbidden observation was opened")

    monkeypatch.setattr(type(bundle.root), "read_bytes", forbidden)
    with pytest.raises(ValueError):
        bundle.read("fleet", year, phase)


def test_draft_prevents_evaluation(bundle):
    with pytest.raises(ValueError, match="frozen"):
        bundle.read("fleet", 2019, "validation")
    with pytest.raises(ValueError, match="not authorised"):
        TrainingView(bundle).read("fleet", 2020)


def test_bundle_integrity_and_missing_inventory(bundle):
    assert bundle.read("fleet", 2017).capacity_mw.iloc[0] == 100
    assert not bundle.readiness()["metadata_complete"]
    assert len(bundle.readiness()["missing"]) == 17
    (bundle.root / "fleet.csv").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        bundle.read("fleet", 2017)


@pytest.mark.parametrize("filename", ["../secret.csv", "nested/../../secret.csv"])
def test_bundle_rejects_traversal(bundle, filename):
    record = bundle.record
    record["resources"][0]["file"] = filename
    changed = StudyBundle(bundle.root, record, bundle.protocol)
    with pytest.raises(ValueError, match="escapes"):
        changed.read("fleet", 2017)


def test_vintage_not_available_at_origin(bundle):
    protocol = protocol_record()
    protocol["mode"] = "forecast_origin"
    p = Protocol.from_dict(protocol)
    record = bundle.record
    record["protocol_sha256"] = p.identity
    changed = StudyBundle(bundle.root, record, p)
    with pytest.raises(ValueError, match="not available"):
        changed.read("fleet", 2017, origin="2018-01-01T00:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        changed.read("fleet", 2017, origin="2018-01-01")


def test_lock_identity_and_bundle_binding(bundle):
    record = protocol_record()
    record["status"] = "frozen"
    p = Protocol.from_dict(record)
    lock = {
        "protocol_sha256": p.identity,
        "bundle_sha256": "a" * 64,
        "trials_sha256": "b" * 64,
        "code_sha256": "c" * 64,
        "training_years": [2017, 2018],
        "parameters": {"weight": 0.5},
        "identifiability_passed": True,
    }
    lock["lock_sha256"] = canonical_hash(lock)
    p.authorise(2019, "validation", locked=lock)
    lock["parameters"]["weight"] = 1
    with pytest.raises(ValueError, match="checksum"):
        p.authorise(2019, "validation", locked=lock)


def test_table_cannot_hide_other_year_observations(bundle):
    path = bundle.root / "fleet.csv"
    path.write_text("year,technology,capacity_mw\n2020,gas,100\n")
    record = bundle.record
    record["resources"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    changed = StudyBundle(bundle.root, record, bundle.protocol)
    with pytest.raises(ValueError, match="outside"):
        changed.read("fleet", 2017)


def test_missing_training_demand_report_does_not_open_holdout(tmp_path):
    p = Protocol.from_dict(protocol_record())
    holdout = tmp_path / "2020" / "fake"
    holdout.mkdir(parents=True)
    (holdout / "manifest.json").write_text("PRIVATE CONTENT MUST NOT BE PARSED")
    result = demand_audit(p, tmp_path, tmp_path / "audit.json")
    assert not result["S2_complete"] and not result["all_training_demand_complete"]
    assert [r["year"] for r in result["years"]] == [2017, 2018]


def test_calibration_refuses_draft_or_changed_search(bundle, tmp_path):
    with pytest.raises(ValueError, match="Freeze"):
        fit_capacity_grid(
            bundle, [{"x": 1.0}], [1], ("gas",), lambda *args: np.ones((2, 1)), tmp_path / "search"
        )
    assert not (tmp_path / "search").exists()


def test_grid_records_failures_uses_common_seeds_and_does_not_issue_lock(bundle, tmp_path):
    p = protocol_record()
    candidates = [{"x": 1.0}, {"x": 2.0}, {"x": 3.0}]
    p.update(
        status="frozen",
        calibration={"candidates": candidates, "seeds": [11, 22], "technologies": ["gas"]},
    )
    protocol = Protocol.from_dict(p)
    resources = []
    for year in (2017, 2018):
        path = tmp_path / f"{year}.csv"
        path.write_text(f"year,technology,capacity_mw\n{year},gas,100\n")
        for role in REQUIRED_ROLES:
            resource = bundle.record["resources"][0]
            resource.update(
                role=role,
                year=year,
                file=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            resources.append(resource)
    full = StudyBundle(
        tmp_path,
        {"schema_version": 1, "protocol_sha256": protocol.identity, "resources": resources},
        protocol,
    )
    calls = []

    def predict(parameters, seed, view):
        calls.append((parameters["x"], seed, view.years))
        if parameters["x"] == 3:
            raise RuntimeError("Do not publish this arbitrary exception text")
        with pytest.raises(ValueError):
            view.read("fleet", 2020)
        return np.full((2, 1), 100 * parameters["x"])

    result = fit_capacity_grid(full, candidates, [11, 22], ("gas",), predict, tmp_path / "search")
    assert len(calls) == 6 and result["successful_candidates"] == 2
    assert result["best_candidate"]["parameters"] == {"x": 1.0}
    assert not result["parameter_lock_issued"]
    trials = [
        json.loads(row) for row in (tmp_path / "search/trials.jsonl").read_text().splitlines()
    ]
    assert len(trials) == 6 and [r["status"] for r in trials[-2:]] == ["failed", "failed"]
    assert "Do not publish" not in (tmp_path / "search/trials.jsonl").read_text()
