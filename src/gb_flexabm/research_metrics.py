"""Calibration/evaluation primitives, not a claim of historical calibration."""

from __future__ import annotations

import numpy as np


def capacity_metrics(predicted: np.ndarray, observed: np.ndarray) -> dict:
    p, o = np.asarray(predicted, dtype=float), np.asarray(observed, dtype=float)
    if p.shape != o.shape or p.ndim != 2 or not p.size or not np.isfinite([p, o]).all():
        raise ValueError("Capacity must align by year and technology")
    if min(p.min(), o.min()) < 0 or np.any(o.sum(axis=1) <= 0) or np.any(p.sum(axis=1) <= 0):
        raise ValueError("Positive annual totals and nonnegative capacity required")
    return {
        "share_mae_pp": float(
            100 * np.abs(p / p.sum(axis=1, keepdims=True) - o / o.sum(axis=1, keepdims=True)).mean()
        ),
        "total_relative_error_max": float(
            np.max(np.abs(p.sum(axis=1) - o.sum(axis=1)) / o.sum(axis=1))
        ),
        "wmape": float(np.abs(p - o).sum() / o.sum()),
    }


def sensitivity_screen(
    parameters: np.ndarray, targets: np.ndarray, tolerance: float = 1e-8
) -> dict:
    """Standardised linear screening across trials, not structural identifiability proof."""
    x, y = np.asarray(parameters, dtype=float), np.asarray(targets, dtype=float)
    if (
        x.ndim != 2
        or y.ndim != 2
        or len(x) != len(y)
        or len(x) < 2
        or min(x.shape[1], y.shape[1]) < 1
    ):
        raise ValueError(
            "Aligned nonempty trial-by-parameter and trial-by-target matrices required"
        )
    if (
        not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or not np.isfinite(tolerance)
        or tolerance <= 0
    ):
        raise ValueError("Finite sensitivity inputs and positive tolerance required")
    xs, ys = x.std(axis=0), y.std(axis=0)
    xn = (x - x.mean(axis=0)) / np.where(xs > 0, xs, 1)
    yn = (y - y.mean(axis=0)) / np.where(ys > 0, ys, 1)
    design_rank = int(np.linalg.matrix_rank(xn, tol=tolerance))
    coefficients = np.linalg.lstsq(xn, yn, rcond=tolerance)[0]
    rank = int(np.linalg.matrix_rank(coefficients, tol=tolerance))
    return {
        "design_rank": design_rank,
        "response_rank": rank,
        "parameter_count": x.shape[1],
        "passed_linear_screen": design_rank == x.shape[1] and rank == x.shape[1],
        "coefficient_norms": np.linalg.norm(coefficients, axis=1).tolist(),
        "constant_targets": np.flatnonzero(ys == 0).tolist(),
        "note": "Local/global nonlinear identifiability still needs scientific assessment.",
    }


def seed_convergence(
    values: np.ndarray,
    *,
    minimum: int = 100,
    relative_tolerance: float = 0.01,
    absolute_tolerance: float = 0.0,
) -> dict:
    """Fixed-ensemble normal-approximation mean CI; never a sequential stopping rule."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) < 2 or not np.isfinite(array).all():
        raise ValueError("At least two finite independent-seed results required")
    if (
        type(minimum) is not int
        or minimum < 2
        or not np.isfinite([relative_tolerance, absolute_tolerance]).all()
        or min(relative_tolerance, absolute_tolerance) < 0
    ):
        raise ValueError("Valid prespecified seed count and tolerances required")
    mean = float(array.mean())
    halfwidth = float(1.96 * array.std(ddof=1) / np.sqrt(len(array)))
    tolerance = max(absolute_tolerance, relative_tolerance * abs(mean))
    return {
        "seeds": len(array),
        "mean": mean,
        "mean_ci95_halfwidth": halfwidth,
        "tolerance": tolerance,
        "passed": len(array) >= minimum and halfwidth <= tolerance,
        "note": "Mean only, normal approximation; does not establish tail or empirical uncertainty convergence.",
    }


def rolling_baselines(history: np.ndarray, prediction: np.ndarray) -> dict:
    """One-step forecasts: prediction[i] must be frozen using only history[:i].

    This metric helper cannot prove how supplied model predictions were created.
    An independently audited origin-vintage runner is still required for S5.
    """
    actual, model = np.asarray(history, dtype=float), np.asarray(prediction, dtype=float)
    if (
        actual.ndim != 2
        or actual.shape != model.shape
        or len(actual) < 3
        or not np.isfinite([actual, model]).all()
    ):
        raise ValueError(
            "Aligned annual capacity and prediction matrices, at least three years, required"
        )
    if min(actual.min(), model.min()) < 0:
        raise ValueError("Capacity cannot be negative")
    persistence, trend = [], []
    for origin in range(2, len(actual)):
        persistence.append(actual[origin - 1])
        x = np.arange(origin, dtype=float)
        slope = ((x - x.mean())[:, None] * (actual[:origin] - actual[:origin].mean(axis=0))).sum(
            axis=0
        ) / np.square(x - x.mean()).sum()
        trend.append(np.maximum(0, actual[:origin].mean(axis=0) + slope * (origin - x.mean())))
    model_errors = np.abs(model[2:] - actual[2:]).mean(axis=1)
    result = {}
    for name, baseline in (("persistence", persistence), ("linear_trend", trend)):
        errors = np.abs(np.asarray(baseline) - actual[2:]).mean(axis=1)
        mean_error = float(errors.mean())
        result[name] = {
            "baseline_mae_mw": mean_error,
            "model_mae_mw": float(model_errors.mean()),
            "relative_improvement": float(1 - model_errors.mean() / mean_error)
            if mean_error
            else None,
            "strict_win_fraction": float((model_errors < errors).mean()),
            "origins": len(errors),
        }
    return result


def cfd_transfer(
    eligible_mwh: float, strike_gbp_per_mwh: float, reference_gbp_per_mwh: float
) -> float:
    """Signed two-sided transfer on already-eligible energy; not contract eligibility."""
    if (
        not np.isfinite([eligible_mwh, strike_gbp_per_mwh, reference_gbp_per_mwh]).all()
        or eligible_mwh < 0
    ):
        raise ValueError("Finite prices and nonnegative eligible MWh required")
    return eligible_mwh * (strike_gbp_per_mwh - reference_gbp_per_mwh)


def capacity_obligation_transfer(
    obligation_mw: float, price_gbp_per_kw_year: float, delivery_fraction: float
) -> float:
    """Already de-rated obligation; explicit delivery fraction, no second de-rating."""
    if (
        not np.isfinite([obligation_mw, price_gbp_per_kw_year, delivery_fraction]).all()
        or min(obligation_mw, price_gbp_per_kw_year) < 0
        or not 0 <= delivery_fraction <= 1
    ):
        raise ValueError("Nonnegative obligation/price and delivery fraction in [0,1] required")
    return obligation_mw * 1000 * price_gbp_per_kw_year * delivery_fraction
