"""Explicit, immutable scientific inputs with units in field names."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import yaml


def finite(name: str, value: float, minimum: float = 0) -> None:
    if not np.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")


@dataclass(frozen=True)
class Technology:
    name: str
    capex_gbp_per_mw: float
    fixed_cost_gbp_per_mw_year: float
    variable_cost_gbp_per_mwh: float
    emissions_t_per_mwh: float
    lifetime_years: int
    construction_years: int
    max_build_mw_per_year: float
    derating: float
    profile: str = "firm"

    def __post_init__(self) -> None:
        if not self.name or self.profile not in {"firm", "wind", "solar"}:
            raise ValueError("Technology requires a name and supported profile")
        for name in (
            "capex_gbp_per_mw",
            "fixed_cost_gbp_per_mw_year",
            "variable_cost_gbp_per_mwh",
            "emissions_t_per_mwh",
            "max_build_mw_per_year",
            "derating",
        ):
            finite(name, getattr(self, name))
        if self.derating > 1:
            raise ValueError("derating must be <= 1")
        for name in ("lifetime_years", "construction_years"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Asset:
    asset_id: str
    owner: str
    technology: str
    capacity_mw: float
    commission_year: int
    retirement_year: int
    decision_year: int | None = None

    def __post_init__(self) -> None:
        finite("capacity_mw", self.capacity_mw)
        if not self.asset_id or not self.owner:
            raise ValueError("Asset identity and owner are required")
        for name in ("commission_year", "retirement_year", "decision_year"):
            value = getattr(self, name)
            if value is not None and type(value) is not int:
                raise ValueError(f"{name} must be an integer year")
        if self.retirement_year <= self.commission_year:
            raise ValueError("Retirement must follow commissioning")

    def active(self, year: int) -> bool:
        return self.commission_year <= year < self.retirement_year


@dataclass(frozen=True)
class Storage:
    power_mw: float = 0
    energy_mwh: float = 0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    throughput_cost_gbp_per_mwh: float = 1

    def __post_init__(self) -> None:
        for name in ("power_mw", "energy_mwh", "throughput_cost_gbp_per_mwh"):
            finite(name, getattr(self, name))
        for efficiency in (self.charge_efficiency, self.discharge_efficiency):
            if not 0 < efficiency <= 1:
                raise ValueError("Storage efficiencies must be in (0, 1]")
        if bool(self.power_mw) != bool(self.energy_mwh):
            raise ValueError("Storage requires both positive power and energy, or neither")


@dataclass(frozen=True)
class Periods:
    demand_mw: tuple[float, ...]
    availability: tuple[tuple[float, ...], ...]
    duration_hours: tuple[float, ...]
    occurrences: tuple[float, ...]
    label: str

    def __post_init__(self) -> None:
        n = len(self.demand_mw)
        if not n or not self.availability:
            raise ValueError("Periods must not be empty")
        for values in (self.demand_mw, self.duration_hours, self.occurrences, *self.availability):
            if len(values) != n or not np.isfinite(values).all():
                raise ValueError("Period arrays must align and be finite")
        if min(self.demand_mw) < 0:
            raise ValueError("Demand cannot be negative")
        if min(self.duration_hours) <= 0 or min(self.occurrences) <= 0:
            raise ValueError("Durations and occurrences must be positive")
        if any(min(a) < 0 or max(a) > 1 for a in self.availability):
            raise ValueError("Availability must be in [0, 1]")
        if len(set(self.occurrences)) != 1:
            raise ValueError("This chronological cyclic block requires uniform occurrences")

    @property
    def weights(self) -> np.ndarray:
        return np.asarray(self.duration_hours) * np.asarray(self.occurrences)

    @property
    def annual_hours(self) -> float:
        return float(self.weights.sum())


@dataclass(frozen=True)
class System:
    technologies: tuple[Technology, ...]
    assets: tuple[Asset, ...]
    storage: Storage
    voll_gbp_per_mwh: float
    discount_rate: float

    def __post_init__(self) -> None:
        names = [t.name for t in self.technologies]
        if not names or len(set(names)) != len(names):
            raise ValueError("Technology names must be nonempty and unique")
        if len({a.asset_id for a in self.assets}) != len(self.assets):
            raise ValueError("Asset IDs must be unique")
        for asset in self.assets:
            if asset.technology not in names:
                raise ValueError(f"Unknown technology: {asset.technology}")
        finite("voll", self.voll_gbp_per_mwh, 1)
        finite("discount_rate", self.discount_rate)

    def capacity(self, year: int, assets: tuple[Asset, ...] | None = None) -> np.ndarray:
        fleet = self.assets if assets is None else assets
        return np.array(
            [
                sum(a.capacity_mw for a in fleet if a.technology == t.name and a.active(year))
                for t in self.technologies
            ]
        )


def load_config(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("Expected configuration schema_version: 1")
    if config.get("scientific_status") != "exploratory_synthetic":
        raise ValueError("This release only supports exploratory_synthetic configurations")
    if not config.get("assumption_source"):
        raise ValueError("An explicit assumption_source is required")
    years = config.get("years", [])
    if (
        not years
        or any(type(y) is not int for y in years)
        or years != list(range(years[0], years[-1] + 1))
    ):
        raise ValueError("Years must be consecutive increasing integers")


def system_from_config(config: dict[str, Any]) -> System:
    validate_config(config)
    return System(
        tuple(Technology(**t) for t in config["technologies"]),
        tuple(Asset(**a) for a in config["assets"]),
        Storage(**config["storage"]),
        config["voll_gbp_per_mwh"],
        config["discount_rate"],
    )


def synthetic_periods(
    system: System,
    hours: int = 168,
    base_demand_mw: float = 25000,
    growth: float = 1,
    annual_hours: float = 8760,
) -> Periods:
    """Deterministic demonstration signals, never described as GB observations."""
    if type(hours) is not int or hours < 1:
        raise ValueError("hours must be a positive integer")
    finite("base_demand_mw", base_demand_mw)
    finite("growth", growth)
    finite("annual_hours", annual_hours, 1)
    h = np.arange(hours)
    demand = (
        base_demand_mw
        * growth
        * (1 + 0.15 * np.sin(2 * np.pi * h / 24) + 0.08 * np.cos(2 * np.pi * h / 168))
    )
    wind = 0.40 + 0.25 * np.sin(2 * np.pi * h / 120 + 0.4)
    solar = np.maximum(0, np.sin(2 * np.pi * (h % 24 - 6) / 24)) * 0.85
    profiles = {"firm": np.ones(hours), "wind": wind, "solar": solar}
    return Periods(
        tuple(demand),
        tuple(tuple(profiles[t.profile]) for t in system.technologies),
        (1.0,) * hours,
        (annual_hours / hours,) * hours,
        f"synthetic-{hours}h-block-weighted-{annual_hours:g}h",
    )
