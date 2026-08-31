"""Small explicit ERA5 access probe; credentials stay in memory, raw files local.

Run from the repository root after installing the research extra. This is an
access check, NOT a weather-to-power dataset or a historical validation result.
No .cdsapirc is read or written. Accept dataset terms on the CDS website first.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import cdsapi

DATASET = "reanalysis-era5-single-levels"
REQUEST = {
    "product_type": ["reanalysis"],
    "variable": ["100m_u_component_of_wind", "100m_v_component_of_wind"],
    "year": ["2018"],
    "month": ["01"],
    "day": ["01"],
    "time": ["00:00", "01:00"],
    "area": [55, -3, 54.75, -2.75],
    "data_format": "netcdf",
    "download_format": "unarchived",
}


def main() -> int:
    token = getpass.getpass("Copernicus personal access token (hidden): ").strip()
    if not token:
        print("No token supplied; no request made.")
        return 2
    # Silence client logs: remote exception text/URLs must not become public evidence.
    logging.disable(logging.CRITICAL)
    destination = Path("data/raw/era5-access-probe") / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / "sample.nc"
    try:
        client = cdsapi.Client(
            url="https://cds.climate.copernicus.eu/api",
            key=token,
            quiet=True,
            debug=False,
            timeout=60,
            retry_max=2,
            sleep_max=20,
        )
        print("Requesting two training-year hours at a four-cell location.", flush=True)
        client.retrieve(DATASET, REQUEST, str(target))
    except Exception as exc:
        # Classify without echoing secrets, signed URLs or arbitrary server text.
        message = str(exc).lower()
        reason = (
            "dataset terms must be accepted manually"
            if "licen" in message or "terms" in message
            else "authentication or permission refused"
            if "401" in message or "403" in message or "unauthorized" in message
            else "request failed; check CDS request status and connectivity"
        )
        print(f"ERA5 access check failed: {reason} ({type(exc).__name__}).")
        return 2
    finally:
        token = ""
    record = {
        "schema_version": 1,
        "purpose": "access_probe_only_not_weather_availability",
        "dataset": DATASET,
        "request": REQUEST,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "source_url": f"https://cds.climate.copernicus.eu/datasets/{DATASET}",
        "file": target.name,
    }
    (destination / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"ERA5 access succeeded. Local probe: {destination / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
