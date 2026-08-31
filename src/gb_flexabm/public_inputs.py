"""Bounded public-source snapshots; acquisition is not scientific acceptance.

No API credentials, cookies, paid services, fitting, or implicit source substitutions.
Publisher files stay local; only provenance and structural audits are publishable.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_HOSTS = {
    "www.gov.uk",
    "assets.publishing.service.gov.uk",
    "www.ons.gov.uk",
    "climate.ec.europa.eu",
    "commission.europa.eu",
    "www.ofgem.gov.uk",
    "www.neso.energy",
    "api.neso.energy",
    "dp.lowcarboncontracts.uk",
    "www.lowcarboncontracts.uk",
    "www.bankofengland.co.uk",
    "www.nationalarchives.gov.uk",
    "www.ecb.europa.eu",
    "data-api.ecb.europa.eu",
    "83025b28472d6aa2bf5ae59f3724aa78.eu.r2.cloudflarestorage.com",
    "lccc-ckan-storage-production.s3.amazonaws.com",
}
MAX_BYTES = 100_000_000


def byte_limit(entry: dict) -> int:
    limit = entry.get("max_bytes", MAX_BYTES)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 350_000_000:
        raise ValueError("Invalid reviewed byte limit")
    return limit


def check_url(url: str) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in ALLOWED_HOSTS
        or parts.username
        or parts.password
        or parts.port not in (None, 443)
    ):
        raise ValueError("Only credential-free HTTPS URLs on approved public hosts are allowed")
    return url


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def checked_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,149}", value):
        raise ValueError("Invalid source id")
    return value


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def exclusive_json(path: Path, record: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def snapshot(
    root: Path,
    entry: dict,
    body: bytes,
    *,
    final_url: str,
    acquisition: str,
    content_type: str = "",
) -> dict:
    ident = checked_id(entry["id"])
    check_url(entry["url"])
    check_url(final_url)
    if not body or len(body) > byte_limit(entry):
        raise ValueError("Empty or oversized source")
    fmt = entry["format"].lower()
    if fmt not in {"csv", "xlsx", "xls", "pdf", "html", "json"}:
        raise ValueError("Unsupported source format")
    # Do not record an HTML error/login page as a successful binary/data download.
    head = body[:512].lstrip().lower()
    if fmt == "pdf" and not body.startswith(b"%PDF-"):
        raise ValueError("Response is not a PDF")
    if fmt == "xlsx" and not body.startswith(b"PK"):
        raise ValueError("Response is not an XLSX ZIP")
    if fmt in {"csv", "xls", "xlsx", "json"} and (b"<html" in head or b"<!doctype html" in head):
        raise ValueError("HTML returned instead of data")
    digest = sha256(body)
    directory = root / ident / digest
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("source." + fmt)
    if target.exists():
        if target.read_bytes() != body:
            raise ValueError("Existing snapshot does not match its digest")
    else:
        with target.open("xb") as stream:
            stream.write(body)
    record = {
        "schema_version": 1,
        **entry,
        "sha256": digest,
        "bytes": len(body),
        "final_url": final_url.split("?", 1)[0],
        "acquisition": acquisition,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_type": content_type,
        "raw_path": str(target.relative_to(root).as_posix()),
        "scientific_acceptance": "not_assessed",
        "redistribution": "raw_files_not_committed",
    }
    manifest = directory / "manifest.json"
    if not manifest.exists():
        exclusive_json(manifest, record)
    else:
        record = json.loads(manifest.read_text(encoding="utf-8"))
    return record


def acquire(root: Path, entry: dict, local: Path | None = None) -> dict:
    ident = checked_id(entry["id"])
    check_url(entry["url"])
    if local is not None:
        if local.stat().st_size > byte_limit(entry):
            raise ValueError("Oversized local import")
        return snapshot(
            root,
            entry,
            local.read_bytes(),
            final_url=entry["url"],
            acquisition="user_supplied_copy; publisher identity not independently matched",
        )
    # Resume by verifying source bytes, not trusting a success marker.
    for manifest in sorted((root / ident).glob("*/manifest.json")):
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if record.get("url") != entry["url"]:
            continue
        target = manifest.parent / ("source." + entry["format"].lower())
        if sha256(target.read_bytes()) != record["sha256"]:
            raise ValueError("Cached source hash mismatch")
        return {**record, "cache_reused": True}
    request = Request(entry["url"], headers={"User-Agent": "GB-FLEXABM-public-data/0.3"})
    with build_opener(PublicRedirect()).open(request, timeout=45) as response:
        check_url(response.url)
        size = response.headers.get("Content-Length")
        if size and int(size) > byte_limit(entry):
            raise ValueError("Source Content-Length exceeds reviewed byte limit")
        body = response.read(byte_limit(entry) + 1)
        return snapshot(
            root,
            entry,
            body,
            final_url=response.url,
            acquisition="public_https",
            content_type=response.headers.get("Content-Type", ""),
        )


def audit_imrp(body: bytes, train_years: list[int]) -> dict:
    """Audit native date/period keys, without inventing a UTC/DST interpretation.

    Only training-year price values are inspected; later rows are counted by date.
    The supplied dictionary does not resolve 23/25-hour settlement-day semantics.
    """
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    expected = ["IMRP_Date", "Settlement_Period", "IMRP_Amount"]
    if reader.fieldnames != expected:
        raise ValueError("Unexpected IMRP schema")
    rows_by_year: Counter = Counter()
    keys: Counter = Counter()
    day_periods: dict[date, list[int]] = {}
    invalid_numeric = negative_training = duplicates = 0
    first = last = None
    for row in reader:
        if None in row or any(row[key] is None for key in expected):
            raise ValueError("Ragged IMRP row")
        day = date.fromisoformat(row["IMRP_Date"][:10])
        period = int(row["Settlement_Period"])
        if not 1 <= period <= 25:
            raise ValueError("Invalid hourly settlement period")
        key = (day, period)
        duplicates += keys[key] > 0
        keys[key] += 1
        rows_by_year[day.year] += 1
        day_periods.setdefault(day, []).append(period)
        first = day if first is None else min(first, day)
        last = day if last is None else max(last, day)
        if day.year in train_years:
            try:
                value = float(row["IMRP_Amount"])
                invalid_numeric += not math.isfinite(value)
                negative_training += math.isfinite(value) and value < 0
            except ValueError:
                invalid_numeric += 1
    years = {}
    for year in train_years:
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        years[str(year)] = {
            "rows": rows_by_year[year],
            "absent_dates": sum(d not in day_periods for d in days),
            "day_row_count_histogram": dict(Counter(len(day_periods.get(d, [])) for d in days)),
            "noncontiguous_period_days": sum(
                sorted(day_periods[d]) != list(range(1, len(day_periods[d]) + 1))
                for d in days
                if d in day_periods
            ),
        }
    return {
        "sha256": sha256(body),
        "rows": sum(rows_by_year.values()),
        "first_date": str(first),
        "last_date": str(last),
        "rows_by_year": dict(sorted(rows_by_year.items())),
        "duplicate_native_keys": duplicates,
        "training_years": years,
        "training_invalid_prices": invalid_numeric,
        "training_negative_prices_retained": negative_training,
        "timezone_alignment": "pending; native publisher date/period keys retained",
        "later_year_prices_inspected": False,
        "target_substitution": "none; IMRP is not APXMIDP",
    }
