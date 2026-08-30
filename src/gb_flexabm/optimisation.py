"""Shared physical LP constraints for dispatch and multi-year planning."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import TerminationCondition

from .schema import Periods, System

SOLVER_OPTIONS = {
    "threads": 1,
    "parallel": "off",
    "random_seed": 0,
    "primal_feasibility_tolerance": 1e-7,
    "dual_feasibility_tolerance": 1e-7,
}


@dataclass
class DispatchResult:
    hourly: pd.DataFrame
    generation_mw: np.ndarray
    summary: dict[str, float]
    solve_seconds: float
    checks: dict[str, bool]


@dataclass
class PlannerResult:
    builds: pd.DataFrame
    annual: pd.DataFrame
    objective_gbp: float
    independently_recomputed_gbp: float
    solve_seconds: float
    checks: dict[str, bool]


def _block(block: Any, system: System, periods: Periods, capacity: Any) -> None:
    """Use identical capacity/balance/storage equations in both models."""
    nk, nt = len(system.technologies), len(periods.demand_mw)
    if len(periods.availability) != nk:
        raise ValueError("One availability series per technology is required")
    weights, storage = periods.weights, system.storage
    block.k = pyo.RangeSet(0, nk - 1)
    block.t = pyo.RangeSet(0, nt - 1)
    block.g = pyo.Var(block.k, block.t, domain=pyo.NonNegativeReals)
    block.shed = pyo.Var(block.t, domain=pyo.NonNegativeReals)
    block.charge = pyo.Var(block.t, bounds=(0, storage.power_mw))
    block.discharge = pyo.Var(block.t, bounds=(0, storage.power_mw))
    block.soc = pyo.Var(range(nt + 1), bounds=(0, storage.energy_mwh))
    block.capacity_limit = pyo.Constraint(
        block.k, block.t, rule=lambda b, k, t: b.g[k, t] <= periods.availability[k][t] * capacity[k]
    )
    block.shed_limit = pyo.Constraint(block.t, rule=lambda b, t: b.shed[t] <= periods.demand_mw[t])
    block.balance = pyo.Constraint(
        block.t,
        rule=lambda b, t: (
            sum(b.g[k, t] for k in b.k) + b.discharge[t] - b.charge[t] + b.shed[t]
            == periods.demand_mw[t]
        ),
    )
    block.storage_balance = pyo.Constraint(
        block.t,
        rule=lambda b, t: (
            b.soc[t + 1]
            == b.soc[t]
            + periods.duration_hours[t]
            * (
                storage.charge_efficiency * b.charge[t]
                - b.discharge[t] / storage.discharge_efficiency
            )
        ),
    )
    block.initial_soc = pyo.Constraint(expr=block.soc[0] == storage.energy_mwh / 2)
    block.final_soc = pyo.Constraint(expr=block.soc[nt] == storage.energy_mwh / 2)
    block.variable_cost = pyo.Expression(
        expr=sum(
            weights[t]
            * (
                sum(
                    system.technologies[k].variable_cost_gbp_per_mwh * block.g[k, t]
                    for k in block.k
                )
                + system.voll_gbp_per_mwh * block.shed[t]
                + storage.throughput_cost_gbp_per_mwh * (block.charge[t] + block.discharge[t])
            )
            for t in block.t
        )
    )


def _solve(model: Any, duals: bool = False) -> float:
    if duals:
        model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    start = time.perf_counter()
    result = pyo.SolverFactory("highs").solve(model, options=SOLVER_OPTIONS, load_solutions=False)
    elapsed = time.perf_counter() - start
    if result.solver.termination_condition != TerminationCondition.optimal:
        raise RuntimeError(f"No optimal solution: {result.solver.termination_condition}")
    model.solutions.load_from(result)
    return elapsed


def _extract(
    block: Any,
    system: System,
    periods: Periods,
    capacity: np.ndarray,
    elapsed: float,
    dual: Any = None,
) -> DispatchResult:
    nk, nt = len(system.technologies), len(periods.demand_mw)
    g = np.array([[pyo.value(block.g[k, t]) for t in range(nt)] for k in range(nk)])

    def take(name: str) -> np.ndarray:
        return np.array([pyo.value(getattr(block, name)[t]) for t in range(nt)])

    shed, charge, discharge, soc = (take(n) for n in ("shed", "charge", "discharge", "soc"))
    soc_next = np.array([pyo.value(block.soc[t + 1]) for t in range(nt)])
    weights, demand = periods.weights, np.asarray(periods.demand_mw)
    prices = (
        np.array([dual[block.balance[t]] / weights[t] for t in range(nt)])
        if dual is not None
        else np.full(nt, np.nan)
    )
    available = np.asarray(periods.availability) * capacity[:, None]
    cost = float(
        np.sum(
            g
            * np.array([t.variable_cost_gbp_per_mwh for t in system.technologies])[:, None]
            * weights
        )
        + shed @ weights * system.voll_gbp_per_mwh
        + (charge + discharge) @ weights * system.storage.throughput_cost_gbp_per_mwh
    )
    balance = g.sum(axis=0) + discharge - charge + shed - demand
    storage_residual = (
        soc_next
        - soc
        - np.asarray(periods.duration_hours)
        * (
            charge * system.storage.charge_efficiency
            - discharge / system.storage.discharge_efficiency
        )
    )
    tol = 1e-5
    checks = {
        "energy_balance": bool(np.max(np.abs(balance)) <= tol),
        "storage_balance": bool(np.max(np.abs(storage_residual)) <= tol),
        "cyclic_storage": bool(abs(soc_next[-1] - soc[0]) <= tol),
        "capacity_bounds": bool(np.all(g >= -tol) and np.all(g <= available + tol)),
        "shed_bounds": bool(np.all(shed >= -tol) and np.all(shed <= demand + tol)),
        "storage_bounds": bool(
            np.all(soc_next >= -tol) and np.all(soc_next <= system.storage.energy_mwh + tol)
        ),
        "storage_power_bounds": bool(
            np.all(charge >= -tol)
            and np.all(charge <= system.storage.power_mw + tol)
            and np.all(discharge >= -tol)
            and np.all(discharge <= system.storage.power_mw + tol)
        ),
        "finite_dual_prices": dual is None or bool(np.isfinite(prices).all()),
        "objective_recomputed": bool(
            np.isclose(cost, pyo.value(block.variable_cost), atol=0.01, rtol=1e-8)
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Scientific dispatch check failed: {checks}")
    hourly = pd.DataFrame(
        {
            "demand_mw": demand,
            "weight_hours": weights,
            "price_gbp_per_mwh": prices,
            "unserved_mw": shed,
            "charge_mw": charge,
            "discharge_mw": discharge,
            "soc_start_mwh": soc,
            "soc_end_mwh": soc_next,
        }
    )
    for k, technology in enumerate(system.technologies):
        hourly[f"generation_{technology.name}_mw"] = g[k]
    renewable = np.array([t.profile != "firm" for t in system.technologies])
    summary = {
        "variable_resource_cost_gbp": cost,
        "demand_mwh": float(demand @ weights),
        "unserved_mwh": float(shed @ weights),
        "scarcity_hours": float(weights[shed > tol].sum()),
        "emissions_t": float(
            np.sum(
                g
                * np.array([t.emissions_t_per_mwh for t in system.technologies])[:, None]
                * weights
            )
        ),
        "renewable_curtailment_mwh": float(np.sum((available[renewable] - g[renewable]) * weights)),
        "balance_max_mw": float(np.max(np.abs(balance))),
        "storage_residual_max_mwh": float(np.max(np.abs(storage_residual))),
    }
    if dual is not None:
        summary["mean_price_gbp_per_mwh"] = float(prices @ weights / weights.sum())
        summary["consumer_energy_payment_gbp"] = float((demand - shed) @ (prices * weights))
    return DispatchResult(hourly, g, summary, elapsed, checks)


def dispatch(system: System, periods: Periods, capacity_mw: np.ndarray) -> DispatchResult:
    capacity = np.asarray(capacity_mw, dtype=float)
    if (
        capacity.shape != (len(system.technologies),)
        or not np.isfinite(capacity).all()
        or (capacity < 0).any()
    ):
        raise ValueError("Capacity must align with technologies and be finite/non-negative")
    model = pyo.ConcreteModel()
    model.operation = pyo.Block()
    _block(model.operation, system, periods, capacity)
    model.objective = pyo.Objective(expr=model.operation.variable_cost)
    elapsed = _solve(model, duals=True)
    return _extract(model.operation, system, periods, capacity, elapsed, model.dual)


def capital_coefficient(
    technology: Any, decision_year: int, years: tuple[int, ...], rate: float
) -> float:
    """Upfront capex less discounted straight-line terminal asset value."""
    commission = decision_year + technology.construction_years
    remaining = max(0, technology.lifetime_years - (years[-1] - commission + 1))
    return technology.capex_gbp_per_mw * (
        (1 + rate) ** -(decision_year - years[0] + 1)
        - remaining / technology.lifetime_years * (1 + rate) ** -len(years)
    )


def planner(system: System, periods_by_year: dict[int, Periods]) -> PlannerResult:
    years = tuple(periods_by_year)
    if not years or years != tuple(range(years[0], years[-1] + 1)):
        raise ValueError("Planner requires consecutive increasing years")
    model = pyo.ConcreteModel()
    model.y = pyo.Set(initialize=years, ordered=True)
    model.k = pyo.RangeSet(0, len(system.technologies) - 1)

    def bounds(m: Any, k: int, y: int) -> tuple[float, float]:
        tech = system.technologies[k]
        return 0, tech.max_build_mw_per_year if y + tech.construction_years <= years[-1] else 0

    model.build = pyo.Var(model.k, model.y, bounds=bounds)

    def capacity(m: Any, k: int, y: int) -> Any:
        tech = system.technologies[k]
        return system.capacity(y)[k] + sum(
            m.build[k, q]
            for q in years
            if q + tech.construction_years <= y < q + tech.construction_years + tech.lifetime_years
        )

    model.capacity = pyo.Expression(model.k, model.y, rule=capacity)
    model.operation = pyo.Block(model.y)
    objective = 0
    for y in years:
        cap_expressions = [model.capacity[k, y] for k in model.k]
        _block(model.operation[y], system, periods_by_year[y], cap_expressions)
        discount = (1 + system.discount_rate) ** -(y - years[0] + 1)
        objective += discount * (
            model.operation[y].variable_cost
            + sum(
                t.fixed_cost_gbp_per_mw_year * cap_expressions[k]
                for k, t in enumerate(system.technologies)
            )
        )
        objective += sum(
            capital_coefficient(t, y, years, system.discount_rate) * model.build[k, y]
            for k, t in enumerate(system.technologies)
        )
    model.objective = pyo.Objective(expr=objective)
    elapsed = _solve(model)
    annual: list[dict[str, Any]] = []
    builds: list[dict[str, Any]] = []
    independently = 0.0
    for y in years:
        cap = np.array([pyo.value(model.capacity[k, y]) for k in model.k])
        result = _extract(model.operation[y], system, periods_by_year[y], cap, elapsed)
        fixed = float(cap @ np.array([t.fixed_cost_gbp_per_mw_year for t in system.technologies]))
        row = {"year": y, **result.summary, "fixed_cost_gbp": fixed}
        independently += (result.summary["variable_resource_cost_gbp"] + fixed) * (
            1 + system.discount_rate
        ) ** -(y - years[0] + 1)
        for k, t in enumerate(system.technologies):
            built = float(pyo.value(model.build[k, y]))
            builds.append(
                {
                    "year": y,
                    "technology": t.name,
                    "build_mw": built,
                    "commission_year": y + t.construction_years,
                }
            )
            row[f"capacity_{t.name}_mw"] = cap[k]
            independently += built * capital_coefficient(t, y, years, system.discount_rate)
        annual.append(row)
    objective_value = float(pyo.value(model.objective))
    checks = {
        "objective_recomputed": bool(
            np.isclose(independently, objective_value, rtol=1e-8, atol=0.1)
        ),
        "dispatch_checks": True,
        "nonnegative_builds": all(b["build_mw"] >= -1e-5 for b in builds),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Planner verification failed: {checks}")
    return PlannerResult(
        pd.DataFrame(builds), pd.DataFrame(annual), objective_value, independently, elapsed, checks
    )
