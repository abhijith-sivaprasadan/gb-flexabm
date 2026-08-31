"""Fail-closed historical study contracts; independent of the synthetic demo.

This is an accidental-leakage/integrity guard, not an OS security boundary or
external preregistration service. No observation is opened before split checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .data import calendar_coverage, validate_data_manifest
from .provenance import canonical_hash

REQUIRED_ROLES = (
    "demand",
    "fleet",
    "technology_costs",
    "fuel_carbon",
    "money_index",
    "wholesale_price",
    "generation",
    "weather_availability",
    "policy",
)


def _years(values: Any) -> tuple[int, ...]:
    if not isinstance(values, list) or not values or any(type(y) is not int for y in values):
        raise ValueError("Study years must be nonempty integer lists")
    if (
        values != list(range(values[0], values[-1] + 1))
        or not 2000 <= values[0] <= values[-1] <= 2100
    ):
        raise ValueError("Study years must be consecutive, increasing, and within 2000–2100")
    return tuple(values)


@dataclass(frozen=True)
class Protocol:
    document: str

    @classmethod
    def from_dict(cls, record: dict) -> Protocol:
        if record.get("schema_version") != 1 or record.get("status") not in {"draft", "frozen"}:
            raise ValueError("Expected a draft or frozen schema-1 study protocol")
        windows = [_years(record["splits"][phase]) for phase in ("train", "validation", "holdout")]
        if not windows[0][-1] < windows[1][0] or not windows[1][-1] < windows[2][0]:
            raise ValueError("Training, validation and holdout must be ordered and disjoint")
        if record.get("mode") not in {"explanatory_backcast", "forecast_origin"}:
            raise ValueError("Explicit study mode required")
        if (
            not record.get("prior_exposure")
            or not record.get("metrics")
            or not record.get("baselines")
        ):
            raise ValueError("Prior-exposure record, metrics and baselines are required")
        if type(record.get("money_base_year")) is not int:
            raise ValueError("Explicit constant-money base year required")
        return cls(json.dumps(record, sort_keys=True, allow_nan=False))

    @property
    def record(self) -> dict:
        return json.loads(self.document)

    @property
    def identity(self) -> str:
        return canonical_hash(self.record)

    def authorise(self, year: int, phase: str, *, locked: dict | None = None) -> None:
        if phase not in {"train", "validation", "holdout"}:
            raise ValueError("Unknown study phase")
        if type(year) is not int or year not in self.record["splits"][phase]:
            raise ValueError(f"Year {year} is not authorised for {phase}")
        if phase != "train":
            if self.record["status"] != "frozen" or not locked:
                raise ValueError("Evaluation requires a frozen protocol and parameter lock")
            verify_parameter_lock(locked, self)


def verify_parameter_lock(lock: dict, protocol: Protocol) -> None:
    body = {k: v for k, v in lock.items() if k != "lock_sha256"}
    if lock.get("lock_sha256") != canonical_hash(body):
        raise ValueError("Parameter lock checksum mismatch")
    if lock.get("protocol_sha256") != protocol.identity:
        raise ValueError("Parameter lock belongs to another protocol")
    for key in ("bundle_sha256", "trials_sha256", "code_sha256"):
        if not isinstance(lock.get(key), str) or len(lock[key]) != 64:
            raise ValueError(f"Missing lock provenance: {key}")
    if lock.get("training_years") != protocol.record["splits"]["train"]:
        raise ValueError("Parameter lock must identify exactly the training window")
    if not lock.get("parameters") or lock.get("identifiability_passed") is not True:
        raise ValueError("Unidentified or empty parameters cannot be locked")


def _inside(root: Path, name: str) -> Path:
    relative = Path(name)
    target = (root / relative).resolve()
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not target.is_relative_to(root.resolve())
    ):
        raise ValueError("Bundle path escapes its root")
    return target


class StudyBundle:
    """Metadata is visible; table bytes are only read by the phase-scoped method."""

    def __init__(self, root: Path, record: dict, protocol: Protocol):
        self.root, self.protocol = root.resolve(), protocol
        # Defensive copy prevents caller mutation after construction.
        self.document = json.dumps(record, sort_keys=True, allow_nan=False)
        if record.get("schema_version") != 1 or record.get("protocol_sha256") != protocol.identity:
            raise ValueError("Bundle protocol/schema mismatch")
        keys = [(r["role"], r["year"]) for r in record["resources"]]
        if len(keys) != len(set(keys)) or any(role not in REQUIRED_ROLES for role, _ in keys):
            raise ValueError("Duplicate or unsupported bundle resources")

    @property
    def record(self) -> dict:
        return json.loads(self.document)

    @property
    def identity(self) -> str:
        return canonical_hash(self.record)

    def readiness(self, phase: str = "train") -> dict:
        if phase not in {"train", "validation", "holdout"}:
            raise ValueError("Unknown study phase")
        available = {(r["role"], r["year"]) for r in self.record["resources"]}
        missing = [
            {"role": role, "year": year}
            for year in self.protocol.record["splits"][phase]
            for role in REQUIRED_ROLES
            if (role, year) not in available
        ]
        return {
            "phase": phase,
            "metadata_complete": not missing,
            "missing": missing,
            "observations_verified": False,
            "note": "Inventory only. A complete list does not establish valid inputs or scientific readiness.",
        }

    def read(
        self,
        role: str,
        year: int,
        phase: str = "train",
        *,
        locked: dict | None = None,
        origin: str | None = None,
    ) -> pd.DataFrame:
        self.protocol.authorise(year, phase, locked=locked)
        if locked is not None and locked.get("bundle_sha256") != self.identity:
            raise ValueError("Parameter lock belongs to another bundle")
        matches = [r for r in self.record["resources"] if (r["role"], r["year"]) == (role, year)]
        if len(matches) != 1:
            raise ValueError(f"Missing input: {role}/{year}")
        resource = matches[0]
        for field in (
            "source_url",
            "licence",
            "boundary",
            "units",
            "transform",
            "available_at_utc",
            "source_sha256",
        ):
            if not resource.get(field):
                raise ValueError(f"Missing source contract: {field}")
        vintage = pd.Timestamp(resource["available_at_utc"])
        if vintage.tz is None:
            raise ValueError("Source availability must be timezone-aware")
        if self.protocol.record["mode"] == "forecast_origin":
            if origin is None or pd.Timestamp(origin).tz is None:
                raise ValueError("Forecast-origin studies require a timezone-aware origin")
            if vintage > pd.Timestamp(origin):
                raise ValueError("Source vintage was not available at the forecast origin")
        path = _inside(self.root, resource["file"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != resource["sha256"]:
            raise ValueError("Bundle observation checksum mismatch")
        frame = pd.read_csv(path)
        if frame.empty or set(frame.columns) != set(resource["units"]):
            raise ValueError("Every table column needs an explicit unit/label contract")
        if frame.isna().any().any():
            raise ValueError("Missing observations are not imputed")
        for column in frame.select_dtypes(include="number"):
            if not np.isfinite(frame[column]).all():
                raise ValueError("Non-finite observations")
        if "year" in frame and not frame.year.eq(year).all():
            raise ValueError("Table includes observations outside its declared year")
        if "timestamp_utc" in frame:
            times = pd.to_datetime(frame.timestamp_utc, utc=True, errors="raise")
            if (
                not times.dt.year.eq(year).all()
                or times.duplicated().any()
                or not times.is_monotonic_increasing
            ):
                raise ValueError(
                    "Time series must be ordered, unique, and within its declared year"
                )
        return frame


def demand_audit(protocol: Protocol, raw_root: Path, output: Path) -> dict:
    """Recheck only training years, without reading later observations."""
    if output.exists():
        raise ValueError("Audit output must be a new file")
    rows = []
    for year in protocol.record["splits"]["train"]:
        protocol.authorise(year, "train")
        matches = sorted((raw_root / str(year)).glob("*/manifest.json"))
        if len(matches) != 1:
            rows.append(
                {"year": year, "complete": False, "reason": "Require exactly one pinned snapshot"}
            )
            continue
        record = json.loads(matches[0].read_text(encoding="utf-8"))
        frame = validate_data_manifest(matches[0], expected_year=year)
        hourly = frame.set_index("timestamp_utc").national_demand_mw.resample("1h").mean()
        energy = float((frame.national_demand_mw * frame.duration_hours).sum())
        error = abs(float(hourly.sum()) - energy) / energy if energy else 0.0
        rows.append(
            {
                **calendar_coverage(frame, year),
                "year": year,
                "sha256": record["sha256"],
                "national_demand_mwh": energy,
                "peak_half_hour_mw": float(frame.national_demand_mw.max()),
                "peak_hourly_mw": float(hourly.max()),
                "hourly_aggregation_relative_error": error,
                "aggregation_gate_passed": error < 0.01,
            }
        )
    report = {
        "schema_version": 1,
        "kind": "training_demand_ingestion_not_empirical_model_validation",
        "protocol_sha256": protocol.identity,
        "protocol_status": protocol.record["status"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "years": rows,
        "all_training_demand_complete": all(r["complete"] for r in rows),
        "S2_complete": False,
        "missing_roles": [r for r in REQUIRED_ROLES if r != "demand"],
        "prior_exposure": protocol.record["prior_exposure"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report
