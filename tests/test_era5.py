"""Live APIs are never used by these tests."""

import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from gb_flexabm.era5 import (
    AREA,
    VARIABLES,
    _netcdf_files,
    acquisition_plan,
    acquisition_status,
    fetch_entry,
    inspect_netcdf,
    validate_plan,
    verify_snapshot,
)
from gb_flexabm.provenance import canonical_hash
from gb_flexabm.study import Protocol


@pytest.fixture
def protocol():
    return Protocol.from_dict(
        {
            "schema_version": 1,
            "status": "draft",
            "mode": "explanatory_backcast",
            "money_base_year": 2025,
            "splits": {"train": [2016], "validation": [2017], "holdout": [2018]},
            "prior_exposure": ["Authored test fixture"],
            "metrics": {"example": 1},
            "baselines": ["persistence"],
        }
    )


def test_plan_is_monthly_training_only_and_leap_complete(protocol):
    plan = acquisition_plan(protocol)
    assert len(plan["requests"]) == 13
    february = plan["requests"][2]["request"]
    assert len(february["day"]) == 29 and len(february["time"]) == 24
    assert len(february["variable"]) == 12 and february["area"] == AREA
    assert plan["requests"][0]["request"]["variable"] == ["geopotential", "land_sea_mask"]
    assert all(r["request"]["year"] == ["2016"] for r in plan["requests"])
    validate_plan(plan, protocol)


def test_recomputed_hash_cannot_authorise_global_or_holdout_request(protocol):
    plan = acquisition_plan(protocol)
    plan["requests"][1]["request"]["year"] = ["2018"]
    plan["plan_sha256"] = canonical_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
    with pytest.raises(ValueError, match="bounded"):
        validate_plan(plan, protocol)


def test_empty_status_does_not_claim_completion_or_expose_paths(protocol, tmp_path):
    result = acquisition_status(acquisition_plan(protocol), protocol, tmp_path)
    assert result["verified_requests"] == 0 and result["planned_requests"] == 13
    assert not result["full_historical_bundle_complete"]
    assert str(tmp_path) not in json.dumps(result)


def test_plan_mutation_does_not_change_authorised_defaults(protocol):
    original = acquisition_plan(protocol)
    changed = acquisition_plan(protocol)
    changed["groups"]["wind"].append("not_required")
    changed["requests"][1]["request"]["area"][0] = 90
    assert acquisition_plan(protocol) == original


@pytest.fixture
def static_files(tmp_path, protocol):
    xr = pytest.importorskip("xarray")
    pytest.importorskip("netCDF4")
    entry = acquisition_plan(protocol)["requests"][0]
    coords = {
        "valid_time": pd.date_range("2016-01-01", periods=1, freq="h"),
        "latitude": np.arange(61, 48.875, -0.25),
        "longitude": np.arange(-12, 4.125, 0.25),
    }
    values = {}
    for variable in entry["request"]["variable"]:
        name, units = VARIABLES[variable]
        values[name] = (
            ("valid_time", "latitude", "longitude"),
            np.ones((1, 49, 65)),
            {"units": units},
        )
    ds = xr.Dataset(values, coords=coords)
    path = tmp_path / "static.nc"
    ds.to_netcdf(path)
    return entry, path, ds


def test_netcdf_coordinates_units_and_coverage(static_files, tmp_path):
    entry, path, ds = static_files
    assert inspect_netcdf([path], entry)["grid_cells"] == 3185
    bad = tmp_path / "missing.nc"
    ds.isel(longitude=slice(1, None)).to_netcdf(bad)
    with pytest.raises(ValueError, match="longitude"):
        inspect_netcdf([bad], entry)
    ds["z"].attrs["units"] = "incorrect"
    ds.to_netcdf(tmp_path / "units.nc")
    with pytest.raises(ValueError, match="units"):
        inspect_netcdf([tmp_path / "units.nc"], entry)


def test_missing_variable_and_timestamps_fail(static_files, tmp_path):
    entry, path, ds = static_files
    ds.drop_vars("z").to_netcdf(tmp_path / "missing.nc")
    with pytest.raises(ValueError, match="Missing ERA5 variables"):
        inspect_netcdf([tmp_path / "missing.nc"], entry)
    ds.assign_coords(valid_time=pd.date_range("2017-01-01", periods=1)).to_netcdf(
        tmp_path / "wrongtime.nc"
    )
    with pytest.raises(ValueError, match="timestamps"):
        inspect_netcdf([tmp_path / "wrongtime.nc"], entry)


@pytest.mark.parametrize("name", ["../escape.nc", "sub/file.nc", "C:/escape.nc", "file.txt"])
def test_archive_cannot_escape_destination(tmp_path, name):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(name, "untrusted")
    with pytest.raises(ValueError, match="filenames"):
        _netcdf_files(archive, tmp_path)


def test_job_resume_does_not_resubmit_and_cache_is_rechecked(static_files, tmp_path):
    entry, path, _ = static_files

    class Remote:
        request_id = "11111111-1111-4111-8111-111111111111"
        results_ready = False

        def download(self, target):
            with zipfile.ZipFile(target, "w") as zipped:
                zipped.write(path, "static.nc")

    remote = Remote()

    class Client:
        submits = 0
        resumes = 0

        def submit(self, dataset, request):
            self.submits += 1
            return remote

        def get_remote(self, job):
            self.resumes += 1
            return remote

    client = Client()
    root = tmp_path / "raw"
    result = fetch_entry(entry, root, client, max_wait_seconds=0)
    assert result["status"] == "queued" and client.submits == 1
    remote.results_ready = True
    result = fetch_entry(entry, root, client, max_wait_seconds=0)
    assert result["status"] == "downloaded_verified" and client.submits == 1 and client.resumes == 1
    assert fetch_entry(entry, root, client)["status"] == "verified_cached"
    from pathlib import Path

    manifest = Path(result["manifest"])
    record = json.loads(manifest.read_text())
    assert "request_id" not in record and "key" not in record
    (manifest.parent / "static.nc").write_bytes(b"tamper")
    with pytest.raises(ValueError, match="checksum"):
        verify_snapshot(manifest, entry)
