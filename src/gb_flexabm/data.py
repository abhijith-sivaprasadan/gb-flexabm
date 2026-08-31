"""Optional official NESO acquisition; never called by the simulation implicitly."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NESO_METADATA = "https://api.neso.energy/api/3/action/datapackage_show?id=historic-demand-data"
# Exact object-store account observed in the official NESO download redirect.
# Do not persist its short-lived signed query parameters in public manifests.
NESO_OBJECT_HOST = "83025b28472d6aa2bf5ae59f3724aa78.eu.r2.cloudflarestorage.com"
CATALOG = {
    "neso-demand": {
        "publisher": "NESO",
        "status": "implemented",
        "metadata_url": NESO_METADATA,
        "licence_url": "https://www.neso.energy/data-portal/ngeso-open-licence",
        "boundary": "National Demand (ND), not total end-use demand; excludes specified station load, pumping and exports.",
    },
    "elexon-mid": {
        "publisher": "Elexon",
        "status": "planned",
        "boundary": "Wholesale Market Index target; not System Prices.",
    },
    "dukes": {"publisher": "DESNZ", "status": "planned"},
    "era5": {
        "publisher": "Copernicus",
        "status": "raw monthly acquisition implemented; conversion pending",
        "boundary": "Raw ERA5 weather; fleet-weighted availability conversion still required.",
    },
}


def settlement_start_utc(day: date, settlement_period: int) -> datetime:
    """GB settlement periods are elapsed half-hours between local midnights."""
    if type(settlement_period) is not int:
        raise ValueError("Settlement period must be an integer")
    london = ZoneInfo("Europe/London")
    start = datetime.combine(day, datetime.min.time(), london).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), london).astimezone(
        timezone.utc
    )
    count = int((end - start).total_seconds() / 1800)
    if not 1 <= settlement_period <= count:
        raise ValueError(f"{day} has {count} settlement periods; got {settlement_period}")
    return start + timedelta(minutes=30 * (settlement_period - 1))


def energy_to_power_mw(energy_mwh: float, duration_hours: float) -> float:
    if not np.isfinite([energy_mwh, duration_hours]).all() or duration_hours <= 0:
        raise ValueError("Finite energy and positive duration required")
    return energy_mwh / duration_hours


def constant_money(nominal: float, source_index: float, target_index: float) -> float:
    if (
        not np.isfinite([nominal, source_index, target_index]).all()
        or min(source_index, target_index) <= 0
    ):
        raise ValueError("Money/index inputs must be finite; indices must be positive")
    return nominal * target_index / source_index


def parse_neso_demand(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    required = {"SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "ND"}
    if not required.issubset(raw):
        raise ValueError(f"NESO schema changed; missing {sorted(required - set(raw))}")
    if raw.empty or raw[list(required)].isna().any().any():
        raise ValueError("NESO required observations must not be empty or missing")
    values = pd.to_numeric(raw["ND"], errors="raise")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("NESO ND must be finite and nonnegative")
    times = []
    for day, sp in zip(raw["SETTLEMENT_DATE"], raw["SETTLEMENT_PERIOD"]):
        stamp = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"):
            try:
                stamp = datetime.strptime(str(day), fmt).date()
                break
            except ValueError:
                continue
        if stamp is None:
            raise ValueError(f"Unsupported settlement-date format: {day}")
        if not float(sp).is_integer():
            raise ValueError("Fractional settlement period")
        times.append(settlement_start_utc(stamp, int(sp)))
    frame = pd.DataFrame(
        {
            "settlement_date": raw["SETTLEMENT_DATE"],
            "settlement_period": raw["SETTLEMENT_PERIOD"],
            "timestamp_utc": times,
            "national_demand_mw": values,
            "duration_hours": 0.5,
        }
    ).sort_values("timestamp_utc")
    if frame.timestamp_utc.duplicated().any():
        raise ValueError("Duplicate UTC observations")
    if (
        len(frame) > 1
        and not (frame.timestamp_utc.diff().dropna() == pd.Timedelta(minutes=30)).all()
    ):
        raise ValueError("Missing or non-contiguous settlement periods")
    return frame.reset_index(drop=True)


def calendar_coverage(frame: pd.DataFrame, year: int) -> dict:
    """Compare with the entire GB settlement calendar, not just the supplied span."""
    if type(year) is not int or not 1900 <= year <= 2100:
        raise ValueError("Calendar year must be an integer from 1900 to 2100")
    expected = pd.date_range(
        f"{year}-01-01", f"{year + 1}-01-01", freq="30min", inclusive="left", tz="UTC"
    )
    observed = pd.DatetimeIndex(frame.timestamp_utc)
    missing, unexpected = expected.difference(observed), observed.difference(expected)
    return {
        "calendar_year": year,
        "complete": observed.equals(expected),
        "expected_rows": len(expected),
        "observed_rows": len(observed),
        "expected_hours": len(expected) / 2,
        "missing_intervals": len(missing),
        "unexpected_intervals": len(unexpected),
        "duplicate_intervals": int(observed.duplicated().sum()),
        "first_utc": observed[0].isoformat() if len(observed) else None,
        "last_utc": observed[-1].isoformat() if len(observed) else None,
    }


def require_complete_year(frame: pd.DataFrame, year: int) -> dict:
    coverage = calendar_coverage(frame, year)
    if not coverage["complete"]:
        raise ValueError(
            f"Incomplete calendar coverage for {year}: "
            f"{coverage['missing_intervals']} missing, "
            f"{coverage['unexpected_intervals']} unexpected, "
            f"{coverage['duplicate_intervals']} duplicate half-hours; "
            f"expected {coverage['expected_rows']} ordered rows"
        )
    return coverage


def _allowed_download(url: str, redirect: bool = False) -> bool:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        return False
    return parsed.hostname == "api.neso.energy" or (
        redirect
        and parsed.hostname == NESO_OBJECT_HOST
        and parsed.path.startswith("/dx-national-grid/national-grid/resources/")
    )


class _NesoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_download(newurl, redirect=True):
            raise ValueError("Unexpected dataset redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url: str) -> bytes:
    if not _allowed_download(url):
        raise ValueError("Only HTTPS downloads from api.neso.energy are allowed")
    with build_opener(_NesoRedirect()).open(url, timeout=45) as response:
        if not _allowed_download(response.geturl(), redirect=True):
            raise ValueError("Unexpected dataset redirect")
        content = response.read(25_000_001)
    if len(content) > 25_000_000:
        raise ValueError("Dataset exceeds the 25 MB safety limit")
    return content


def fetch_neso(year: int, root: Path) -> Path:
    if type(year) is not int or not 1900 <= year <= 2100:
        raise ValueError("Calendar year must be an integer from 1900 to 2100")
    metadata_bytes = _download(NESO_METADATA)
    metadata = json.loads(metadata_bytes)["result"]
    resources = [
        r for r in metadata["resources"] if r.get("name") == f"historic_demand_data_{year}"
    ]
    if len(resources) != 1:
        raise ValueError(f"Expected exactly one NESO demand resource for {year}")
    resource = resources[0]
    content = _download(resource["path"])
    digest = hashlib.sha256(content).hexdigest()
    destination = root / "neso-demand" / str(year) / digest
    manifest = destination / "manifest.json"
    if manifest.exists():
        validate_data_manifest(manifest, expected_year=year)
        return manifest
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "source.csv").write_bytes(content)
    (destination / "metadata.json").write_bytes(metadata_bytes)
    frame = parse_neso_demand(destination / "source.csv")
    record = {
        "schema_version": 1,
        "publisher": "NESO",
        "dataset": "historic-demand-data",
        "resource_id": resource["id"],
        "source_url": resource["path"],
        "source_modified": resource.get("last_modified"),
        "licences": metadata.get("licenses", []),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "file": "source.csv",
        "rows": len(frame),
        "duration_hours": float(frame.duration_hours.sum()),
        "demand_definition": CATALOG["neso-demand"]["boundary"],
        "power_unit": "MW",
        "timezone": "UTC",
        "processing_function": "gb_flexabm.data.parse_neso_demand",
        "calendar_year": year,
        "calendar_coverage": calendar_coverage(frame, year),
    }
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    # Preserve the acquired bytes even when the calendar gate rejects them.
    require_complete_year(frame, year)
    return manifest


def validate_data_manifest(manifest: Path, expected_year: int | None = None) -> pd.DataFrame:
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if record.get("file") != "source.csv":
        raise ValueError("Unexpected raw data filename")
    path = manifest.parent / "source.csv"
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Raw data checksum mismatch")
    if (
        hashlib.sha256((manifest.parent / "metadata.json").read_bytes()).hexdigest()
        != record["metadata_sha256"]
    ):
        raise ValueError("Metadata checksum mismatch")
    frame = parse_neso_demand(path)
    if record["rows"] != len(frame) or record["duration_hours"] != float(
        frame.duration_hours.sum()
    ):
        raise ValueError("Recorded row count or duration does not match the raw data")
    declared_year = record.get("calendar_year")
    if expected_year is not None and declared_year is not None and expected_year != declared_year:
        raise ValueError("Expected year differs from the data manifest's declared calendar year")
    year = expected_year if expected_year is not None else declared_year
    if year is not None:
        require_complete_year(frame, year)
    return frame
