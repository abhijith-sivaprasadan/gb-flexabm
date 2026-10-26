"""Fail-closed, offline coverage audit for *original* legacy Elexon MID CSV archives.

The 2018 BMRS CSV guide describes MID,provider,YYYYMMDD,SP,price,volume
with optional active flag. This reader deliberately does not relabel Insights API
observations as an original archive. No price interpolation or provider fallback.

A complete product calendar is NOT a source-vintage, licence, historical price
target, S2-admission, or GB investor calibration certificate.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .data import calendar_coverage, settlement_start_utc
from .market_data import PROVIDER
from .provenance import canonical_hash


def _utc_instant(value: str) -> str:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Retrieved-at must be ISO-8601 with an explicit UTC offset") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Retrieved-at must be timezone-aware")
    return stamp.astimezone(__import__("datetime").timezone.utc).isoformat()


def _settlement_day(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y%m%d" if len(raw) == 8 else "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Invalid original MID settlement date") from exc


def _finite_number(raw: str, label: str) -> float:
    try:
        result = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"MID {label} is not numerical") from exc
    if not math.isfinite(result):
        raise ValueError(f"MID {label} must be finite")
    return result


def audit_mid_archive(
    source: Path,
    year: int,
    *,
    source_url: str,
    licence: str,
    retrieved_at_utc: str,
    revision_rule: str = "unique_only",
) -> dict:
    """Inspect one original legacy BMRS MID CSV, not an arbitrary reformatted API table.

    `unique_only`: no duplicate APXMIDP settlement keys; explicit inactive records
    are unacceptable because no vintage-selection rule is documented.
    `active_flag`: require Y/N on every target record; select only Y and reject
    duplicate active entries. This is a declared selection, not historical proof.
    """
    if type(year) is not int or not 2000 <= year <= 2100:
        raise ValueError("A single calendar year from 2000 to 2100 is required")
    if revision_rule not in {"unique_only", "active_flag"}:
        raise ValueError("Unsupported MID revision rule")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("Explicit HTTPS archive source URL required")
    if not isinstance(licence, str) or not licence.strip():
        raise ValueError("Explicit archive licence or rights note required")
    acquired = _utc_instant(retrieved_at_utc)
    data = source.read_bytes()
    if not data or len(data) > 150_000_000:
        raise ValueError("Empty/oversized legacy MID archive")
    try:
        lines = csv.reader(io.StringIO(data.decode("utf-8-sig")))
        archive_total = 0
        target_total = 0
        other_provider = 0
        inactive = 0
        outside_year = 0
        trailer = None
        selected: dict[pd.Timestamp, tuple[float, float]] = {}
        for line in lines:
            if not line or not any(cell.strip() for cell in line):
                continue
            fields = [part.strip() for part in line]
            if fields[0] == "HDR":
                if archive_total or trailer is not None:
                    raise ValueError("Header encountered after data")
                continue
            if fields[0] == "FTR":
                if trailer is not None or len(fields) != 2:
                    raise ValueError("Invalid/duplicate MID trailer")
                trailer = int(fields[1])
                continue
            if trailer is not None or fields[0] != "MID" or len(fields) not in {6, 7}:
                raise ValueError("Expected legacy MID CSV rows with 6/7 fields")
            archive_total += 1
            _, provider, day_text, sp_text, price_text, volume_text, *tail = fields
            if provider != PROVIDER:
                other_provider += 1
                continue
            target_total += 1
            day = _settlement_day(day_text)
            try:
                period = int(sp_text)
            except ValueError as exc:
                raise ValueError("Invalid MID settlement period") from exc
            timestamp = pd.Timestamp(settlement_start_utc(day, period))
            price = _finite_number(price_text, "price")
            volume = _finite_number(volume_text, "volume")
            if volume < 0:
                raise ValueError("MID volume cannot be negative")
            flag = tail[0] if tail else ""
            if flag not in {"", "Y", "N"}:
                raise ValueError("Unknown MID active flag")
            if revision_rule == "active_flag" and flag not in {"Y", "N"}:
                raise ValueError("Active-flag selection requires an explicit flag per record")
            if revision_rule == "unique_only" and flag == "N":
                raise ValueError("Inactive revision requires an active-flag selection rule")
            if flag == "N":
                inactive += 1
                continue
            if day.year != year:
                outside_year += 1
                continue
            if timestamp in selected:
                raise ValueError("Duplicate active APXMIDP settlement key: revisions ambiguous")
            selected[timestamp] = price, volume
        if trailer is not None and trailer != archive_total:
            raise ValueError("MID trailer count contradicts data rows")
    except UnicodeDecodeError as exc:
        raise ValueError("Legacy MID archive must be UTF-8 CSV") from exc

    ordered = sorted(selected)
    frame = pd.DataFrame({"timestamp_utc": ordered})
    coverage = calendar_coverage(frame, year)
    zero_volume = sum(volume == 0 for _, volume in selected.values())
    complete = bool(coverage["complete"]) and not zero_volume
    return {
        "schema_version": 1,
        "classification": "OFFLINE_LEGACY_MID_PRODUCT_COVERAGE_AUDIT_ONLY",
        "dataset": "MID",
        "provider": PROVIDER,
        "calendar_year": year,
        "source_url": source_url,
        "licence_note": licence,
        "retrieved_at_utc": acquired,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(data),
        "revision_rule": revision_rule,
        "all_mid_rows": archive_total,
        "other_provider_rows": other_provider,
        "apx_source_rows": target_total,
        "inactive_apx_rows_excluded": inactive,
        "out_of_year_apx_rows": outside_year,
        "unique_apx_rows": len(selected),
        "zero_volume_apx_rows": zero_volume,
        "coverage": coverage,
        "apx_price_product_complete": complete,
        "vintage_certified": False,
        "archive_authenticity_certified": False,
        "historical_bundle_admitted": False,
        "S2_complete": False,
        "note": (
            "Original CSV bytes and calendar only; reconcile publisher authenticity, "
            "rights, settlement-run revisions, overlapping Insights observations, "
            "price semantics, asset fleet/cost vintages and training protocol separately."
        ),
    }


def write_mid_audit(report: dict, output: Path) -> None:
    """Write a checksummed summary to a new file. Never modify source bytes."""
    if output.exists():
        raise FileExistsError("Do not overwrite an earlier archive audit")
    body = {**report, "report_sha256": canonical_hash(report)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(body, stream, indent=2, allow_nan=False)
        stream.write("\n")


def verify_mid_audit(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    digest = report.pop("report_sha256", None)
    if digest != canonical_hash(report):
        raise ValueError("MID archive audit report checksum mismatch")
    if (
        report.get("S2_complete") is not False
        or report.get("historical_bundle_admitted") is not False
        or report.get("archive_authenticity_certified") is not False
    ):
        raise ValueError("Product coverage audit cannot claim historical admission")
    return report
