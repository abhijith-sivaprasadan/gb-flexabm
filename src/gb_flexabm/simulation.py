"""Annual dispatch, settlement, expectations and construction/retirement loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .agents import Investor, capacity_payment_gbp
from .optimisation import capital_coefficient, dispatch
from .schema import Asset, Periods, System


@dataclass
class SimulationResult:
    annual: pd.DataFrame
    decisions: pd.DataFrame
    settlements: pd.DataFrame
    assets: pd.DataFrame
    resource_npv_gbp: float
    checks: dict[str, bool]


def simulate(
    system: System,
    periods_by_year: dict[int, Periods],
    investors: tuple[Investor, ...],
    seed: int,
    capacity_price_gbp_per_kw_year: float = 0,
    initial_expected_price_gbp_per_mwh: float = 80,
) -> SimulationResult:
    years = tuple(periods_by_year)
    if not years or years != tuple(range(years[0], years[-1] + 1)):
        raise ValueError("Simulation requires consecutive increasing years")
    if len({i.investor_id for i in investors}) != len(investors):
        raise ValueError("Investor IDs must be unique")
    if not np.isfinite(initial_expected_price_gbp_per_mwh):
        raise ValueError("Initial expected price must be finite")
    capacity_payment_gbp(0, 0, capacity_price_gbp_per_kw_year)
    technologies = {t.name: (k, t) for k, t in enumerate(system.technologies)}
    if any(i.technology not in technologies for i in investors):
        raise ValueError("Investor references unknown technology")
    fleet = list(system.assets)
    first = periods_by_year[years[0]]
    expectations = {
        i.investor_id: float(
            np.sum(
                np.asarray(first.availability[technologies[i.technology][0]])
                * max(
                    0,
                    initial_expected_price_gbp_per_mwh
                    - technologies[i.technology][1].variable_cost_gbp_per_mwh,
                )
                * first.weights
            )
        )
        for i in investors
    }
    annual: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    settlements: list[dict[str, Any]] = []
    resource_npv = 0.0
    for year, periods in periods_by_year.items():
        cap = system.capacity(year, tuple(fleet))
        result = dispatch(system, periods, cap)
        prices = result.hourly["price_gbp_per_mwh"].to_numpy()
        weights = periods.weights
        fixed = float(cap @ np.array([t.fixed_cost_gbp_per_mw_year for t in system.technologies]))
        transfer = sum(
            capacity_payment_gbp(cap[k], t.derating, capacity_price_gbp_per_kw_year)
            for k, t in enumerate(system.technologies)
        )
        resource_npv += (result.summary["variable_resource_cost_gbp"] + fixed) * (
            1 + system.discount_rate
        ) ** -(year - years[0] + 1)
        row = {
            "year": year,
            "seed": seed,
            **result.summary,
            "fixed_cost_gbp": fixed,
            "capacity_payment_gbp": transfer,
            "solve_seconds": result.solve_seconds,
        }
        for k, tech in enumerate(system.technologies):
            row[f"capacity_{tech.name}_mw"] = cap[k]
            for asset in sorted(
                (a for a in fleet if a.technology == tech.name and a.active(year)),
                key=lambda a: a.asset_id,
            ):
                fraction = asset.capacity_mw / cap[k] if cap[k] > 0 else 0
                energy_revenue = float(result.generation_mw[k] @ (prices * weights) * fraction)
                variable = float(
                    result.generation_mw[k] @ weights * fraction * tech.variable_cost_gbp_per_mwh
                )
                payment = capacity_payment_gbp(
                    asset.capacity_mw, tech.derating, capacity_price_gbp_per_kw_year
                )
                settlements.append(
                    {
                        "year": year,
                        "asset_id": asset.asset_id,
                        "owner": asset.owner,
                        "technology": tech.name,
                        "energy_revenue_gbp": energy_revenue,
                        "capacity_payment_gbp": payment,
                        "operating_cashflow_gbp": energy_revenue
                        + payment
                        - variable
                        - asset.capacity_mw * tech.fixed_cost_gbp_per_mw_year,
                    }
                )
        annual.append(row)
        requests: dict[str, tuple[float, float]] = {}
        # All investors observe the same completed market year, then act simultaneously.
        for investor in sorted(investors, key=lambda i: i.investor_id):
            k, tech = technologies[investor.technology]
            observed = float(
                np.sum(
                    np.maximum(0, prices - tech.variable_cost_gbp_per_mwh)
                    * np.asarray(periods.availability[k])
                    * weights
                )
            )
            expected = investor.update(expectations[investor.investor_id], observed, seed, year)
            expectations[investor.investor_id] = expected
            request, score = investor.request(tech, expected, capacity_price_gbp_per_kw_year)
            if year + tech.construction_years > years[-1]:
                request = 0
            requests[investor.investor_id] = request, score
        for investor in sorted(investors, key=lambda i: i.investor_id):
            _, tech = technologies[investor.technology]
            requested, score = requests[investor.investor_id]
            total = sum(requests[i.investor_id][0] for i in investors if i.technology == tech.name)
            accepted = requested * min(1, tech.max_build_mw_per_year / total) if total else 0
            commission = year + tech.construction_years
            decisions.append(
                {
                    "year": year,
                    "investor": investor.investor_id,
                    "technology": tech.name,
                    "requested_mw": requested,
                    "accepted_mw": accepted,
                    "score_gbp_per_mw": score,
                    "expected_energy_margin_gbp_per_mw": expectations[investor.investor_id],
                    "commission_year": commission,
                }
            )
            if accepted > 1e-8:
                fleet.append(
                    Asset(
                        f"{investor.investor_id}-{year}",
                        investor.investor_id,
                        tech.name,
                        accepted,
                        commission,
                        commission + tech.lifetime_years,
                        year,
                    )
                )
                resource_npv += accepted * capital_coefficient(
                    tech, year, years, system.discount_rate
                )
    annual_frame = pd.DataFrame(annual)
    checks = {
        "dispatch_checks": True,
        "no_early_commissioning": all(
            a.decision_year is None
            or a.commission_year
            >= a.decision_year + technologies[a.technology][1].construction_years
            for a in fleet
        ),
        "capacity_stock": all(
            np.allclose(
                system.capacity(y, tuple(fleet)),
                [r[f"capacity_{t.name}_mw"] for t in system.technologies],
                rtol=1e-8,
                atol=1e-5,
            )
            for y, r in zip(years, annual)
        ),
        "finite_resource_cost": bool(np.isfinite(resource_npv)),
        "capacity_transfer_accounting": bool(
            np.isclose(
                sum(s["capacity_payment_gbp"] for s in settlements),
                annual_frame["capacity_payment_gbp"].sum(),
            )
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Simulation verification failed: {checks}")
    return SimulationResult(
        annual_frame,
        pd.DataFrame(decisions),
        pd.DataFrame(settlements),
        pd.DataFrame([asdict(a) for a in fleet]),
        resource_npv,
        checks,
    )
