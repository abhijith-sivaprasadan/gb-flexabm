"""Bounded ERA5 acquisition plans and resumable CDS jobs; no implicit downloads.

Raw weather is NOT capacity-factor data. Conversion, fleet weighting and
time-interval alignment remain separate scientific steps.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .provenance import canonical_hash
from .study import Protocol

DATASET = "reanalysis-era5-single-levels"
CDS_URL = "https://cds.climate.copernicus.eu/api"
# N, W, S, E; covers the working GB/offshore study domain, not a jurisdiction mask.
AREA = [61, -12, 49, 4]
GROUPS = {
    "wind": [
        "100m_u_component_of_wind",
        "100m_v_component_of_wind",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "forecast_surface_roughness",
    ],
    "solar": [
        "surface_solar_radiation_downwards",
        "surface_net_solar_radiation",
        "total_sky_direct_solar_radiation_at_surface",
        "toa_incident_solar_radiation",
    ],
    "temperature": ["2m_temperature", "2m_dewpoint_temperature", "soil_temperature_level_4"],
    "static": ["geopotential", "land_sea_mask"],
}
VARIABLES = {
    "100m_u_component_of_wind": ("u100", "m s**-1"),
    "100m_v_component_of_wind": ("v100", "m s**-1"),
    "10m_u_component_of_wind": ("u10", "m s**-1"),
    "10m_v_component_of_wind": ("v10", "m s**-1"),
    "forecast_surface_roughness": ("fsr", "m"),
    "surface_solar_radiation_downwards": ("ssrd", "J m**-2"),
    "surface_net_solar_radiation": ("ssr", "J m**-2"),
    "total_sky_direct_solar_radiation_at_surface": ("fdir", "J m**-2"),
    "toa_incident_solar_radiation": ("tisr", "J m**-2"),
    "2m_temperature": ("t2m", "K"),
    "2m_dewpoint_temperature": ("d2m", "K"),
    "soil_temperature_level_4": ("stl4", "K"),
    "geopotential": ("z", "m**2 s**-2"),
    "land_sea_mask": ("lsm", "(0 - 1)"),
}


def acquisition_plan(protocol: Protocol) -> dict:
    requests: list[dict[str, Any]] = []
    for year in protocol.record["splits"]["train"]:
        protocol.authorise(year, "train")
        for month in range(1, 13):
            request = {
                "product_type": ["reanalysis"],
                "variable": [
                    v for group in ("wind", "solar", "temperature") for v in GROUPS[group]
                ],
                "year": [str(year)],
                "month": [f"{month:02d}"],
                "day": [f"{d:02d}" for d in range(1, calendar.monthrange(year, month)[1] + 1)],
                "time": [f"{h:02d}:00" for h in range(24)],
                "area": AREA.copy(),
                "grid": [0.25, 0.25],
                "data_format": "netcdf",
                "download_format": "zip",
            }
            requests.append({"id": f"{year}-{month:02d}", "kind": "monthly", "request": request})
    static = {
        **requests[0]["request"],
        "variable": GROUPS["static"].copy(),
        "day": ["01"],
        "time": ["00:00"],
    }
    requests.insert(0, {"id": "static", "kind": "static", "request": static})
    body = {
        "schema_version": 1,
        "dataset": DATASET,
        "protocol_sha256": protocol.identity,
        "phase": "train",
        "groups": {name: variables.copy() for name, variables in GROUPS.items()},
        "requests": requests,
        "note": "Raw weather only; land/fleet masking, conversion, source attribution and empirical validation remain separate.",
    }
    return {**body, "plan_sha256": canonical_hash(body)}


def validate_plan(plan: dict, protocol: Protocol) -> None:
    # Rebuild the bounded plan: changing a checksum alone cannot enlarge its scope.
    if plan != acquisition_plan(protocol):
        raise ValueError("Plan differs from the protocol's bounded training-only ERA5 selection")


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json(path: Path, record: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(record, indent=2, allow_nan=False) + "\n")


def _netcdf_files(archive: Path, destination: Path) -> list[Path]:
    if not zipfile.is_zipfile(archive):
        raise ValueError("Expected a ZIP archive of NetCDF files")
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        if not members or len(members) > 24 or sum(m.file_size for m in members) > 2_000_000_000:
            raise ValueError("Unexpected archive count/size")
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or any(
            "/" in name
            or "\\" in name
            or ":" in name
            or not name.endswith(".nc")
            or name.startswith(".")
            for name in names
        ):
            raise ValueError("Archive must contain unique flat NetCDF filenames")
        result = []
        for member in members:
            path = destination / member.filename
            with zipped.open(member) as source, path.open("xb") as target:
                shutil.copyfileobj(source, target)
            result.append(path)
        return result


def inspect_netcdf(paths: list[Path], entry: dict) -> dict:
    import xarray as xr

    request = entry["request"]
    year, month = int(request["year"][0]), int(request["month"][0])
    hours = 1 if entry["kind"] == "static" else calendar.monthrange(year, month)[1] * 24
    expected_time = pd.date_range(f"{year}-{month:02d}-01", periods=hours, freq="h")
    north, west, south, east = request["area"]
    expected_lat = np.arange(south, north + 0.125, 0.25)
    expected_lon = np.arange(west, east + 0.125, 0.25)
    expected = {VARIABLES[v][0]: VARIABLES[v][1] for v in request["variable"]}
    found = {}
    for path in paths:
        with xr.open_dataset(path) as ds:
            time_name = "valid_time" if "valid_time" in ds.coords else "time"
            if time_name not in ds.coords or not pd.DatetimeIndex(ds[time_name].values).equals(
                expected_time
            ):
                raise ValueError("ERA5 hourly timestamps are incomplete, duplicated or unexpected")
            for coordinate, values in (("latitude", expected_lat), ("longitude", expected_lon)):
                if (
                    coordinate not in ds.coords
                    or ds[coordinate].size != len(values)
                    or not np.allclose(np.sort(ds[coordinate].values), values)
                ):
                    raise ValueError(f"ERA5 {coordinate} does not match the requested grid")
            for name in ds.data_vars:
                if name not in expected:
                    raise ValueError(f"Unexpected ERA5 variable: {name}")
                if name in found or set(ds[name].dims) != {time_name, "latitude", "longitude"}:
                    raise ValueError("Repeated variable or unexpected ensemble/forecast dimensions")
                units = ds[name].attrs.get("units")
                if units != expected[name]:
                    raise ValueError(f"Unexpected units for {name}: {units}")
                missing = 0
                finite_count = 0
                # Bound memory even when reading a whole monthly archive.
                for start in range(0, hours, 24):
                    array = ds[name].isel({time_name: slice(start, start + 24)}).values
                    if np.isinf(array).any():
                        raise ValueError(f"Infinite ERA5 values: {name}")
                    missing += int(np.isnan(array).sum())
                    finite_count += int(np.isfinite(array).sum())
                # Soil can be masked over sea: report missing cells, do not fill them.
                if finite_count == 0 or (missing and name != "stl4"):
                    raise ValueError(f"Missing required ERA5 values: {name}")
                found[name] = {
                    "units": units,
                    "hours": hours,
                    "missing_values": missing,
                    "finite_values": finite_count,
                }
    if set(found) != set(expected):
        raise ValueError(f"Missing ERA5 variables: {sorted(set(expected) - set(found))}")
    return {
        "complete": True,
        "variables": found,
        "hours": hours,
        "grid_cells": len(expected_lat) * len(expected_lon),
        "source_time_basis": "ERA5 validity time in UTC; accumulated radiation retains J/m2; no conversion/alignment yet",
    }


def verify_snapshot(manifest: Path, entry: dict) -> dict:
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if record.get("request") != entry["request"] or record.get("dataset") != DATASET:
        raise ValueError("ERA5 snapshot/request mismatch")
    paths = []
    for name, digest in record["files"].items():
        if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise ValueError("Unexpected ERA5 snapshot filename")
        path = manifest.parent / name
        if path.is_symlink() or _sha(path) != digest:
            raise ValueError("ERA5 snapshot checksum mismatch")
        if name.endswith(".nc"):
            paths.append(path)
    coverage = inspect_netcdf(paths, entry)
    if coverage != record["coverage"]:
        raise ValueError("ERA5 recorded coverage differs from observations")
    return record


def acquisition_status(plan: dict, protocol: Protocol, root: Path) -> dict:
    """Public-safe local inventory: no credentials, private paths or remote job IDs."""
    validate_plan(plan, protocol)
    entries = []
    for entry in plan["requests"]:
        destination = root / "era5" / entry["id"] / canonical_hash(entry["request"])
        snapshots = sorted(destination.glob("snapshots/*/manifest.json"))
        if snapshots:
            record = verify_snapshot(snapshots[-1], entry)
            entries.append(
                {
                    "id": entry["id"],
                    "status": "verified",
                    "files": record["files"],
                    "coverage": record["coverage"],
                }
            )
        else:
            entries.append(
                {
                    "id": entry["id"],
                    "status": "submitted_remote_state_not_checked"
                    if (destination / "job.json").exists()
                    else "not_acquired",
                }
            )
    return {
        "schema_version": 1,
        "plan_sha256": plan["plan_sha256"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "requests": entries,
        "verified_requests": sum(r["status"] == "verified" for r in entries),
        "planned_requests": len(entries),
        "full_historical_bundle_complete": False,
        "scientific_status": "raw_weather_not_capacity_factors_or_model_validation",
    }


def fetch_entry(entry: dict, root: Path, client: Any, *, max_wait_seconds: float = 180) -> dict:
    """Submit at most one job; persist its ID before waiting, resume on rerun."""
    digest = canonical_hash(entry["request"])
    destination = root / "era5" / entry["id"] / digest
    destination.mkdir(parents=True, exist_ok=True)
    completed = sorted(destination.glob("snapshots/*/manifest.json"))
    if completed:
        record = verify_snapshot(completed[-1], entry)
        return {
            "id": entry["id"],
            "status": "verified_cached",
            "manifest": str(completed[-1]),
            "coverage": record["coverage"],
        }
    job_file = destination / "job.json"
    if job_file.exists():
        job = json.loads(job_file.read_text(encoding="utf-8"))
        if job["request_sha256"] != digest:
            raise ValueError("Saved CDS job/request mismatch")
        uuid.UUID(job["request_id"])
        remote = client.get_remote(job["request_id"])
    else:
        # An uncertain submit failure is deliberately NOT blindly resubmitted here.
        remote = client.submit(DATASET, entry["request"])
        _json(job_file, {"request_id": remote.request_id, "request_sha256": digest})
    deadline = time.monotonic() + max_wait_seconds
    while not remote.results_ready:
        if time.monotonic() >= deadline:
            return {"id": entry["id"], "status": "queued", "job_file": str(job_file)}
        time.sleep(min(20, max(0, deadline - time.monotonic())))
    attempt = destination / "snapshots" / uuid.uuid4().hex
    attempt.mkdir(parents=True, exist_ok=False)
    archive = attempt / "source.zip"
    remote.download(str(archive))
    paths = _netcdf_files(archive, attempt)
    coverage = inspect_netcdf(paths, entry)
    record = {
        "schema_version": 1,
        "dataset": DATASET,
        "request": entry["request"],
        "request_sha256": digest,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": f"https://cds.climate.copernicus.eu/datasets/{DATASET}",
        "licence": "CC-BY; retain CDS dataset attribution and current terms",
        "files": {path.name: _sha(path) for path in [archive, *paths]},
        "coverage": coverage,
        "scientific_status": "raw_weather_not_capacity_factors_or_model_validation",
    }
    manifest = attempt / "manifest.json"
    _json(manifest, record)
    return {
        "id": entry["id"],
        "status": "downloaded_verified",
        "manifest": str(manifest),
        "coverage": coverage,
    }
