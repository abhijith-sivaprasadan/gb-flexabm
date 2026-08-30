"""Price-taking investor economics, independent of any agent framework."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from .schema import Technology, finite


def random_stream(seed: int, *keys: object) -> np.random.Generator:
    """Named substreams: unrelated draws and iteration order cannot shift paths."""
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    digest = hashlib.sha256(repr((seed, keys)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], "big"))


def capacity_payment_gbp(
    capacity_mw: float, derating: float, price_gbp_per_kw_year: float
) -> float:
    for name, value in [
        ("capacity", capacity_mw),
        ("derating", derating),
        ("capacity price", price_gbp_per_kw_year),
    ]:
        finite(name, value)
    if derating > 1:
        raise ValueError("derating must be <= 1")
    return capacity_mw * derating * price_gbp_per_kw_year * 1000


def project_npv(tech: Technology, annual_net_margin_gbp_per_mw: float, hurdle_rate: float) -> float:
    finite("hurdle rate", hurdle_rate)
    if not np.isfinite(annual_net_margin_gbp_per_mw):
        raise ValueError("Annual margin must be finite")
    factors = sum(
        (1 + hurdle_rate) ** -h
        for h in range(tech.construction_years, tech.construction_years + tech.lifetime_years)
    )
    return -tech.capex_gbp_per_mw + annual_net_margin_gbp_per_mw * factors


@dataclass(frozen=True)
class Investor:
    investor_id: str
    technology: str
    hurdle_rate: float
    expectation_weight: float
    risk_aversion: float
    forecast_noise_fraction: float
    annual_budget_gbp: float
    project_size_mw: float
    threshold_gbp_per_mw: float = 0

    def __post_init__(self) -> None:
        if not self.investor_id or not self.technology:
            raise ValueError("Investor identity and technology are required")
        for name in (
            "hurdle_rate",
            "risk_aversion",
            "forecast_noise_fraction",
            "annual_budget_gbp",
            "project_size_mw",
            "threshold_gbp_per_mw",
        ):
            finite(name, getattr(self, name))
        if not 0 <= self.expectation_weight <= 1 or self.project_size_mw == 0:
            raise ValueError("Expectation weight must be in [0,1]; project size must be positive")

    def update(self, previous: float, observed: float, seed: int, year: int) -> float:
        noise = random_stream(seed, "expectation", self.investor_id, year).normal(
            0, self.forecast_noise_fraction * abs(observed)
        )
        return float(
            self.expectation_weight * observed + (1 - self.expectation_weight) * previous + noise
        )

    def request(
        self, tech: Technology, expected_margin: float, capacity_price: float
    ) -> tuple[float, float]:
        net = (
            expected_margin
            + capacity_payment_gbp(1, tech.derating, capacity_price)
            - tech.fixed_cost_gbp_per_mw_year
        )
        risk_penalty = self.risk_aversion * self.forecast_noise_fraction * abs(expected_margin)
        score = project_npv(tech, net - risk_penalty, self.hurdle_rate)
        if score <= self.threshold_gbp_per_mw or tech.capex_gbp_per_mw == 0:
            return 0.0, score
        affordable = (
            np.floor(self.annual_budget_gbp / (tech.capex_gbp_per_mw * self.project_size_mw))
            * self.project_size_mw
        )
        return float(min(affordable, tech.max_build_mw_per_year)), score
