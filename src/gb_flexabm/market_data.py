"""Bounded, training-only Elexon observations with explicit coverage failures.

MID is one provider's wholesale index, not the imbalance price. FUELHH contains
signed interconnector flows and metered generation, not renewable availability.
No observation or zero-volume index is silently filled or used for fitting.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import numpy as np
import pandas as pd

from .data import settlement_start_utc
from .provenance import canonical_hash, sha256
from .study import Protocol

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
PROVIDER = "APXMIDP"
CONTRACTS = {
    "mid": {
        "endpoint": "/balancing/pricing/market-index",
        "source_url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/balancing/pricing/market-index",
        "boundary": "APXMIDP wholesale index in nominal GBP/MWh; volume MWh. Not imbalance prices.",
        "revision": "Conflicting duplicates rejected: this endpoint supplies no revision timestamp.",
    },
    "fuelhh": {
        "endpoint": "/datasets/FUELHH/stream",
        "source_url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
        "boundary": "Half-hour mean MW by Elexon fuel category, including signed interconnector flows; not total GB end-use generation or weather availability.",
        "revision": "Latest publishTime per startTime/fuelType within the pinned response; tied conflicting revisions rejected.",
    },
}


def training_requests(
    protocol: Protocol, dataset: str, years: list[int] | None = None
) -> list[dict]:
    if dataset not in CONTRACTS:
        raise ValueError("Unsupported Elexon dataset")
    selected = protocol.record["splits"]["train"] if years is None else years
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Distinct, nonempty training years required")
    requests = []
    for year in selected:
        protocol.authorise(year, "train")
        for month in range(1, 13):
            start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
            end = start + pd.offsets.MonthBegin()
            while start < end:
                stop = min(start + pd.Timedelta(days=6), end)
                query = (
                    {"from": start.isoformat(), "to": stop.isoformat(), "format": "json"}
                    if dataset == "mid"
                    else {
                        "settlementDateFrom": str(start.date()),
                        "settlementDateTo": str(stop.date()),
                    }
                )
                requests.append(
                    {
                        "schema_version": 1,
                        "dataset": dataset,
                        "year": year,
                        "id": str(start.date()),
                        "start_utc": start.isoformat(),
                        "end_utc": stop.isoformat(),
                        "url": BASE + CONTRACTS[dataset]["endpoint"] + "?" + urlencode(query),
                        "contract": CONTRACTS[dataset],
                        "provider": PROVIDER if dataset == "mid" else None,
                    }
                )
                start = stop
    return requests


def _times(values: pd.Series) -> pd.Series:
    # Reject naive observations instead of silently assuming their timezone.
    if not values.map(lambda v: isinstance(v, str) and pd.Timestamp(v).tz is not None).all():
        raise ValueError("Elexon start/publication timestamps must be timezone-aware")
    return pd.to_datetime(values, utc=True, errors="raise")


def normalize(payload: bytes, request: dict) -> tuple[pd.DataFrame, dict]:
    dataset = request["dataset"]
    content = json.loads(payload)
    rows = content.get("data") if isinstance(content, dict) else content
    if not isinstance(rows, list):
        raise ValueError("Expected Elexon JSON observation list")
    start, end = pd.Timestamp(request["start_utc"]), pd.Timestamp(request["end_utc"])
    expected = pd.date_range(start, end, freq="30min", inclusive="left")
    category = "dataProvider" if dataset == "mid" else "fuelType"
    measures = ["price", "volume"] if dataset == "mid" else ["generation"]
    required = ["startTime", "settlementDate", "settlementPeriod", category, *measures]
    if dataset == "fuelhh":
        required += ["publishTime", "dataset"]
    raw = pd.DataFrame(rows) if rows else pd.DataFrame(columns=required)
    settlement_mismatches = 0
    if not set(required).issubset(raw) or raw[required].isna().any().any():
        raise ValueError("Missing Elexon observation fields")
    if raw.empty:
        raw["timestamp_utc"] = pd.Series(dtype="datetime64[ns, UTC]")
    else:
        raw["timestamp_utc"] = _times(raw.startTime)
        if not raw.timestamp_utc.eq(raw.timestamp_utc.dt.floor("30min")).all():
            raise ValueError("Elexon observations must lie on the UTC half-hour grid")
        periods = pd.to_numeric(raw.settlementPeriod, errors="raise")
        if not np.isfinite(periods).all() or not periods.eq(periods.astype(int)).all():
            raise ValueError("Settlement periods must be integers")
        settlement: list[datetime | None] = []
        for day, period in zip(raw.settlementDate, periods):
            try:
                settlement.append(settlement_start_utc(pd.Timestamp(day).date(), int(period)))
            except ValueError:
                if dataset == "mid":
                    raise
                # Some historical FUELHH auxiliary dates/SPs are inconsistent,
                # including SP48 attached to the 46-period spring-change day.
                # Retain the primary UTC observation time and flag the defect.
                settlement.append(None)
        settlement_mismatches = int(
            (
                ~raw.timestamp_utc.eq(
                    pd.to_datetime(pd.Series(settlement, index=raw.index), utc=True)
                )
            ).sum()
        )
        if settlement_mismatches and dataset == "mid":
            raise ValueError("Elexon settlement date/period and UTC timestamp disagree")
        if not raw[category].map(lambda v: isinstance(v, str) and bool(v)).all():
            raise ValueError("Missing Elexon category")
    for field in measures:
        raw[field] = pd.to_numeric(raw[field], errors="raise").astype(float)
        if not np.isfinite(raw[field]).all():
            raise ValueError("Non-finite Elexon observations")
    if dataset == "mid" and (raw.volume < 0).any():
        raise ValueError("Market index volume cannot be negative")
    if dataset == "fuelhh" and not raw.dataset.eq("FUELHH").all():
        raise ValueError("Response is not the requested FUELHH dataset")
    # APIs include their ending timestamp/settlement day. Crop before combining chunks.
    extra = int((~((raw.timestamp_utc >= start) & (raw.timestamp_utc < end))).sum())
    raw = raw[(raw.timestamp_utc >= start) & (raw.timestamp_utc < end)].copy()
    keys = ["timestamp_utc", category]
    if dataset == "fuelhh":
        raw["publication_utc"] = (
            _times(raw.publishTime) if not raw.empty else pd.Series(dtype="datetime64[ns, UTC]")
        )
        if (raw.publication_utc < raw.timestamp_utc).any():
            raise ValueError("Generation publication predates the observation")
        raw = raw.sort_values("publication_utc")
        newest = raw.groupby(keys).publication_utc.transform("max")
        raw = raw[raw.publication_utc.eq(newest)].copy()
    before = len(raw)
    raw = raw.drop_duplicates(keys + measures)
    if raw.duplicated(keys).any():
        raise ValueError("Conflicting Elexon revisions cannot be chosen arbitrarily")
    if dataset == "mid":
        raw = raw[raw.dataProvider == PROVIDER].copy()
    raw = raw.sort_values(keys).reset_index(drop=True)
    groups = [PROVIDER] if dataset == "mid" else sorted(raw.fuelType.unique())
    coverage = []
    for name in groups:
        observations = raw[raw[category] == name]
        actual = pd.DatetimeIndex(observations.timestamp_utc)
        coverage.append(
            {
                "category": name,
                "rows": len(actual),
                "expected_rows": len(expected),
                "missing_intervals": len(expected.difference(actual)),
                "complete": actual.equals(expected),
            }
        )
    zero_volume = int(raw.volume.eq(0).sum()) if dataset == "mid" else 0
    report = {
        "dataset": dataset,
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "rows": len(raw),
        "empty_response": not rows,
        "trimmed_boundary_rows": extra,
        "identical_duplicates_removed": before - len(raw) if dataset == "fuelhh" else None,
        "coverage": coverage,
        "complete_for_observed_categories": bool(coverage) and all(c["complete"] for c in coverage),
        "zero_volume_index_intervals": zero_volume,
        "target_usable": dataset == "mid"
        and bool(coverage)
        and all(c["complete"] for c in coverage)
        and zero_volume == 0,
        "category_universe_verified": False,
        "boundary_reconciled": False,
    }
    if dataset == "fuelhh" and settlement_mismatches:
        report["settlement_mismatch_rows"] = settlement_mismatches
        report["time_warning"] = (
            "Primary startTime retained; inconsistent auxiliary settlement date/period fields were not used to shift observations. Includes cropped boundary records. Review before model use."
        )
    columns = ["timestamp_utc", category, *measures]
    return raw[columns], report


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected Elexon redirect")


def _download(url: str) -> bytes:
    if not url.startswith(BASE + "/"):
        raise ValueError("Only the official Elexon API is allowed")
    with build_opener(_NoRedirect()).open(
        Request(url, headers={"Accept": "application/json"}), timeout=60
    ) as response:
        data = response.read(30_000_001)
    if len(data) > 30_000_000:
        raise ValueError("Elexon chunk exceeds 30 MB")
    return data


def _location(root: Path, request: dict) -> Path:
    return root / ("elexon-" + request["dataset"]) / request["id"] / canonical_hash(request)


def verify_chunk(root: Path, request: dict) -> tuple[pd.DataFrame, dict]:
    folder = _location(root, request)
    record = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if record.get("request") != request or record.get("sha256") != sha256(folder / "source.json"):
        raise ValueError("Elexon request/source checksum mismatch")
    frame, coverage = normalize((folder / "source.json").read_bytes(), request)
    if record.get("coverage") != coverage:
        raise ValueError("Elexon recorded coverage mismatch")
    return frame, record


def fetch_chunk(root: Path, request: dict) -> dict:
    folder = _location(root, request)
    if (folder / "manifest.json").exists():
        return verify_chunk(root, request)[1]
    if folder.exists():
        raise ValueError(
            "An incomplete/rejected snapshot exists; inspect it explicitly before retrying"
        )
    content = _download(request["url"])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "source.json").write_bytes(content)
    try:
        _, coverage = normalize(content, request)
    except (ValueError, KeyError, TypeError) as exc:
        (folder / "rejected.json").write_text(
            json.dumps(
                {
                    "request": request,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "error_type": type(exc).__name__,
                    "status": "source_retained_normalization_rejected",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        raise
    record = {
        "schema_version": 1,
        "request": request,
        "sha256": hashlib.sha256(content).hexdigest(),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage,
        "terms_url": "https://www.elexon.co.uk/bsc/data/",
        "redistribution": "Raw response kept local; publisher terms apply.",
        "available_at_utc": datetime.now(timezone.utc).isoformat(),
        "vintage_note": "Retrieval vintage only; not evidence this revision was available at a historical forecast origin.",
    }
    (folder / "manifest.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return record


def hourly_market(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Time-weighted hourly averages only when both half-hours are present.

    This does not certify whole-year coverage or a GB technology mapping.
    Generation remains signed MW; MID prices are not weighted by traded volume.
    """
    if dataset not in CONTRACTS or frame.empty:
        raise ValueError("A supported, nonempty market series is required")
    category = "dataProvider" if dataset == "mid" else "fuelType"
    measure = "price" if dataset == "mid" else "generation"
    if dataset == "mid" and (
        not frame.dataProvider.eq(PROVIDER).all()
        or not np.isfinite(frame.volume).all()
        or (frame.volume <= 0).any()
    ):
        raise ValueError("Hourly MID requires only APXMIDP and positive volume in both half-hours")
    times = pd.DatetimeIndex(frame.timestamp_utc)
    if times.tz is None or not times.equals(times.floor("30min")):
        raise ValueError("Timezone-aware half-hour grid required")
    if frame.duplicated(["timestamp_utc", category]).any() or not np.isfinite(frame[measure]).all():
        raise ValueError("Finite, unique market observations required")
    table = frame.copy()
    table["timestamp_utc"] = times.tz_convert("UTC").floor("h")
    grouped = table.groupby(["timestamp_utc", category])[measure]
    if not grouped.count().eq(2).all():
        raise ValueError("Both half-hours are required; missing observations are not filled")
    return grouped.mean().reset_index()


def audit_market(protocol: Protocol, root: Path, dataset: str, output: Path) -> dict:
    if output.exists():
        raise ValueError("Audit output must be new")
    requests = training_requests(protocol, dataset)
    entries: list[dict] = []
    tables: dict[int, list[pd.DataFrame]] = {}
    for request in requests:
        key = request["id"]
        if not (_location(root, request) / "manifest.json").exists():
            status = "not_acquired"
            if (_location(root, request) / "source.json").exists():
                status = "retained_but_not_verified"
            entries.append({"id": key, "status": status})
            continue
        frame, record = verify_chunk(root, request)
        tables.setdefault(request["year"], []).append(frame)
        entries.append(
            {
                "id": key,
                "status": "verified_response",
                "sha256": record["sha256"],
                "coverage": record["coverage"],
            }
        )
    annual = []
    for year in protocol.record["splits"]["train"]:
        chunks = tables.get(year, [])
        row = {
            "year": year,
            "verified_chunks": len(chunks),
            "expected_chunks": sum(r["year"] == year for r in requests),
            "complete": False,
        }
        if chunks:
            combined = pd.concat(chunks, ignore_index=True)
            category = "dataProvider" if dataset == "mid" else "fuelType"
            if combined.duplicated(["timestamp_utc", category]).any():
                raise ValueError("Overlapping chunks detected")
            expected = pd.date_range(
                f"{year}-01-01", f"{year + 1}-01-01", tz="UTC", freq="30min", inclusive="left"
            )
            groups = [PROVIDER] if dataset == "mid" else sorted(combined[category].unique())
            row["categories"] = [
                {
                    "name": name,
                    "rows": int(combined[category].eq(name).sum()),
                    "missing_intervals": len(
                        expected.difference(
                            pd.DatetimeIndex(
                                combined.loc[combined[category] == name, "timestamp_utc"]
                            )
                        )
                    ),
                }
                for name in groups
            ]
            row["complete"] = (
                bool(groups)
                and row["verified_chunks"] == row["expected_chunks"]
                and all(c["missing_intervals"] == 0 for c in row["categories"])
            )
            if dataset == "mid":
                row["zero_volume_index_intervals"] = int(combined.volume.eq(0).sum())
                row["target_usable"] = row["complete"] and row["zero_volume_index_intervals"] == 0
        annual.append(row)
    report = {
        "schema_version": 1,
        "kind": "training_market_coverage_not_model_validation",
        "protocol_sha256": protocol.identity,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "contract": CONTRACTS[dataset],
        "years": annual,
        "requests": entries,
        "S2_complete": False,
        "note": "Coverage of observed categories is not a complete GB accounting boundary. No imputation, provider averaging, or automatic zero-volume price substitution.",
    }
    report["audit_sha256"] = canonical_hash(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def read_market_audit(path: Path) -> dict:
    """Read a public-safe audit snapshot; integrity does not imply target readiness."""
    report = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in report.items() if key != "audit_sha256"}
    if report.get("audit_sha256") != canonical_hash(body):
        raise ValueError("Market audit checksum mismatch")
    if (
        report.get("schema_version") != 1
        or report.get("dataset") not in CONTRACTS
        or report.get("kind") != "training_market_coverage_not_model_validation"
        or report.get("S2_complete") is not False
    ):
        raise ValueError("Unsupported market audit schema/status")
    return report


def audit_summary(report: dict) -> pd.DataFrame:
    rows = []
    for year in report["years"]:
        categories = year.get("categories", [])
        rows.append(
            {
                "year": year["year"],
                "verified response chunks": year["verified_chunks"],
                "planned chunks": year["expected_chunks"],
                "category count": len(categories),
                "missing half-hours (sum across categories)": sum(
                    c["missing_intervals"] for c in categories
                )
                if categories
                else None,
                "calendar coverage complete": year["complete"],
                "zero-volume price intervals": year.get("zero_volume_index_intervals"),
            }
        )
    return pd.DataFrame(rows).astype(
        {
            "missing half-hours (sum across categories)": "Int64",
            "zero-volume price intervals": "Int64",
        }
    )
