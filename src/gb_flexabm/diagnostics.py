"""Chronology-aware reduction experiments and predeclared comparison metrics.

Only exogenous demand/availability enter clustering. Independent representative
days deliberately reset storage; their error against a linked annual solve is
reported, never described as a seasonal-storage approximation certificate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .optimisation import dispatch
from .schema import Periods, System


@dataclass(frozen=True)
class RepresentativeDays:
    medoids: tuple[int, ...]
    counts: tuple[int, ...]
    assignments: tuple[int, ...]
    forced_extremes: tuple[int, ...]


def representative_days(periods: Periods, count: int) -> RepresentativeDays:
    n = len(periods.demand_mw)
    if n % 24 or set(periods.duration_hours) != {1.0} or set(periods.occurrences) != {1.0}:
        raise ValueError("Reduction requires complete, hourly, unweighted chronological days")
    days = n // 24
    if type(count) is not int or not 1 <= count <= days:
        raise ValueError("Representative-day count must be within the number of source days")
    demand = np.asarray(periods.demand_mw).reshape(days, 24)
    availability = np.asarray(periods.availability).reshape(len(periods.availability), days, 24)
    # Peak demand, lowest all-profile mean availability, largest daily demand ramp.
    forced = tuple(
        sorted(
            {
                int(np.argmax(demand.max(axis=1))),
                int(np.argmin(availability.mean(axis=(0, 2)))),
                int(np.argmax(np.abs(np.diff(demand, axis=1)).max(axis=1))),
            }
        )
    )
    if count < len(forced):
        raise ValueError(f"Need at least {len(forced)} medoids to retain all forced extremes")
    raw = np.concatenate([demand, *availability], axis=1)
    scale = raw.std(axis=0)
    features = (raw - raw.mean(axis=0)) / np.where(scale > 0, scale, 1)
    # Euclidean distance, not squared distance, for k-medoids objective.
    norm = np.sum(features * features, axis=1)
    distances = np.sqrt(np.maximum(0, norm[:, None] + norm[None, :] - 2 * features @ features.T))
    np.fill_diagonal(distances, 0)
    medoids = list(forced)
    while len(medoids) < count:
        nearest = distances[:, medoids].min(axis=1)
        nearest[medoids] = -1
        medoids.append(int(np.argmax(nearest)))
    for _ in range(100):
        labels = distances[:, medoids].argmin(axis=1)
        # Deterministic self-assignment keeps duplicate-profile medoids nonempty.
        for cluster, medoid in enumerate(medoids):
            labels[medoid] = cluster
        replacement = medoids.copy()
        for cluster, medoid in enumerate(medoids):
            if medoid in forced:
                continue
            members = np.flatnonzero(labels == cluster)
            replacement[cluster] = int(
                members[np.argmin(distances[np.ix_(members, members)].sum(axis=1))]
            )
        if replacement == medoids:
            break
        medoids = replacement
    labels = distances[:, medoids].argmin(axis=1)
    for cluster, medoid in enumerate(medoids):
        labels[medoid] = cluster
    counts = np.bincount(labels, minlength=count)
    return RepresentativeDays(
        tuple(medoids), tuple(map(int, counts)), tuple(map(int, labels)), forced
    )


def relative_error(predicted: float, observed: float) -> float | None:
    if not np.isfinite([predicted, observed]).all():
        raise ValueError("Metric inputs must be finite")
    if observed == 0:
        return 0.0 if predicted == 0 else None
    return float(abs(predicted - observed) / abs(observed))


def price_metrics(predicted: np.ndarray, observed: np.ndarray) -> dict:
    p, o = np.asarray(predicted, dtype=float), np.asarray(observed, dtype=float)
    if p.ndim != 1 or p.shape != o.shape or not p.size or not np.isfinite([p, o]).all():
        raise ValueError("Aligned, finite nonempty price observations required")
    grid = np.sort(np.concatenate([p, o]))
    ks = np.max(
        np.abs(
            np.searchsorted(np.sort(p), grid, side="right") / p.size
            - np.searchsorted(np.sort(o), grid, side="right") / o.size
        )
    )
    mae = float(np.abs(p - o).mean())
    scale = float(np.abs(o).mean())
    return {
        "mae_gbp_per_mwh": mae,
        "nmae": mae / scale if scale else None,
        "ks_distance": float(ks),
        "normalisation": "mean absolute observed price; zero is undefined",
    }


def generation_share_mae_pp(predicted_mwh: np.ndarray, observed_mwh: np.ndarray) -> float:
    p, o = np.asarray(predicted_mwh, dtype=float), np.asarray(observed_mwh, dtype=float)
    if p.ndim != 1 or p.shape != o.shape or not p.size or not np.isfinite([p, o]).all():
        raise ValueError("Aligned generation categories required")
    if min(p.min(), o.min()) < 0 or min(p.sum(), o.sum()) <= 0:
        raise ValueError("Nonnegative generation and positive totals required")
    return float(100 * np.abs(p / p.sum() - o / o.sum()).mean())


def dispatch_reduction(
    system: System, periods: Periods, capacity_mw: np.ndarray, count: int
) -> dict:
    selected = representative_days(periods, count)
    full = dispatch(system, periods, capacity_mw)
    reduced: dict[str, float] = {}
    reduced_generation = np.zeros(len(system.technologies))
    storage_throughput = 0.0
    for medoid, occurrences in zip(selected.medoids, selected.counts):
        start, end = medoid * 24, (medoid + 1) * 24
        block = Periods(
            periods.demand_mw[start:end],
            tuple(a[start:end] for a in periods.availability),
            (1.0,) * 24,
            (float(occurrences),) * 24,
            f"medoid-day-{medoid}-independent-storage",
        )
        result = dispatch(system, block, capacity_mw)
        for key in (
            "variable_resource_cost_gbp",
            "demand_mwh",
            "unserved_mwh",
            "scarcity_hours",
            "renewable_curtailment_mwh",
        ):
            reduced[key] = reduced.get(key, 0.0) + result.summary[key]
        reduced_generation += result.generation_mw @ block.weights
        storage_throughput += float(
            (result.hourly.charge_mw + result.hourly.discharge_mw) @ block.weights
        )
    comparisons = {
        key: {
            "full": full.summary[key],
            "reduced": value,
            "absolute_error": abs(value - full.summary[key]),
            "relative_error": relative_error(value, full.summary[key]),
        }
        for key, value in reduced.items()
    }
    full_throughput = float((full.hourly.charge_mw + full.hourly.discharge_mw) @ periods.weights)
    comparisons["storage_throughput_mwh"] = {
        "full": full_throughput,
        "reduced": storage_throughput,
        "absolute_error": abs(storage_throughput - full_throughput),
        "relative_error": relative_error(storage_throughput, full_throughput),
    }
    peak = max(max(periods.demand_mw[m * 24 : (m + 1) * 24]) for m in selected.medoids)
    return {
        "source_label": periods.label,
        "hours": periods.annual_hours,
        "medoids": selected.medoids,
        "counts": selected.counts,
        "forced_extremes": selected.forced_extremes,
        "weighted_hours": sum(selected.counts) * 24,
        "metrics": comparisons,
        "peak_demand_relative_error": relative_error(peak, max(periods.demand_mw)),
        "generation_share_mae_pp": generation_share_mae_pp(
            reduced_generation, full.generation_mw @ periods.weights
        ),
        "storage_treatment": "linked full chronology versus independent 24h cycles, each starting/ending half full",
        "empirical_validation": False,
        "note": "Reduction error experiment only; historical labels need separately verified source data.",
    }
