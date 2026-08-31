"""Reproducible offline examples, explicit optional data acquisition and verification."""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .agents import Investor
from .data import CATALOG, calendar_coverage, fetch_neso, validate_data_manifest
from .optimisation import dispatch, planner
from .provenance import verify_run, write_manifest
from .reporting import build_report
from .schema import (
    Asset,
    Periods,
    Storage,
    System,
    Technology,
    load_config,
    synthetic_periods,
    system_from_config,
)
from .simulation import simulate
from .study import Protocol, StudyBundle, demand_audit


def default_config() -> dict[str, Any]:
    return load_config(str(files("gb_flexabm").joinpath("fixtures/demo.yaml")))


def _prepare(output: Path, config: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_text(
        json.dumps(config, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def run_demo(config: dict[str, Any], seeds: list[int], output: Path) -> dict[str, Any]:
    if (
        not seeds
        or len(set(seeds)) != len(seeds)
        or any(type(s) is not int or s < 0 for s in seeds)
    ):
        raise ValueError("Seeds must be nonempty, distinct nonnegative integers")
    system = system_from_config(config)
    years = config["years"]
    growth = config["demand_growth_fraction"]
    if not np.isfinite(growth) or growth <= -1:
        raise ValueError("Demand growth must be finite and > -1")
    periods = {
        y: synthetic_periods(
            system,
            config["hours"],
            config["base_demand_mw"],
            (1 + growth) ** n,
            config["annual_hours"],
        )
        for n, y in enumerate(years)
    }
    investors = tuple(Investor(**i) for i in config["investors"])
    _prepare(output, config)
    started = time.perf_counter()
    plan = planner(system, periods)
    plan.annual.to_csv(output / "planner_annual.csv", index=False)
    plan.builds.to_csv(output / "planner_builds.csv", index=False)
    reference = dispatch(system, periods[years[0]], system.capacity(years[0]))
    reference.hourly.to_csv(output / "dispatch_reference.csv", index=False)
    collected: dict[str, list[pd.DataFrame]] = {
        k: [] for k in ("annual", "decisions", "settlements", "assets")
    }
    summary = []
    all_checks = {
        **{f"planner_{k}": v for k, v in plan.checks.items()},
        **{f"dispatch_{k}": v for k, v in reference.checks.items()},
    }
    for seed in seeds:
        for design, payment in [
            ("energy_only", 0),
            ("stylised_capacity_payment", config["capacity_price_gbp_per_kw_year"]),
        ]:
            result = simulate(
                system,
                periods,
                investors,
                seed,
                payment,
                config["initial_expected_price_gbp_per_mwh"],
            )
            gap = result.resource_npv_gbp - plan.objective_gbp
            if gap < -max(0.1, abs(plan.objective_gbp) * 1e-8):
                raise RuntimeError(
                    "ABM feasible resource cost fell below the shared planner optimum"
                )
            for key in collected:
                frame = getattr(result, key).copy()
                frame["design"], frame["seed"] = design, seed
                collected[key].append(frame)
            all_checks.update({f"{design}_{seed}_{k}": v for k, v in result.checks.items()})
            summary.append(
                {
                    "design": design,
                    "seed": seed,
                    "resource_npv_gbp": result.resource_npv_gbp,
                    "planner_npv_gbp": plan.objective_gbp,
                    "resource_gap_gbp": gap,
                }
            )
    all_checks["planner_lower_bound"] = True
    merged = {key: pd.concat(frames, ignore_index=True) for key, frames in collected.items()}
    for key, frame in merged.items():
        frame.to_csv(output / f"{key}.csv", index=False)
    summary_frame = pd.DataFrame(summary)
    summary_frame.to_csv(output / "summary.csv", index=False)
    build_report(output, merged["annual"], summary_frame, plan.annual)
    return write_manifest(
        output, config, seeds, "paired_abm_planner", time.perf_counter() - started, all_checks
    )


def run_benchmark(config: dict[str, Any], output: Path) -> dict[str, Any]:
    system = system_from_config(config)
    _prepare(output, config)
    tracemalloc.start()
    started = time.perf_counter()
    periods = synthetic_periods(
        system, config["hours"], config["base_demand_mw"], annual_hours=config["annual_hours"]
    )
    result = dispatch(system, periods, system.capacity(config["years"][0]))
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result.hourly.to_csv(output / "dispatch.csv", index=False)
    metrics = {
        **result.summary,
        "hours": config["hours"],
        "weighted_hours": periods.annual_hours,
        "solve_seconds": result.solve_seconds,
        "total_seconds": elapsed,
        "peak_python_allocation_bytes": peak,
        "memory_measurement": "tracemalloc Python allocations; excludes native solver memory, not peak RSS",
    }
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return write_manifest(
        output, config, [], "synthetic_dispatch_benchmark", elapsed, result.checks
    )


def compare_runs(left: Path, right: Path) -> None:
    a, b = verify_run(left), verify_run(right)
    for key in ("config_sha256", "random_seeds", "kind"):
        if a[key] != b[key]:
            raise ValueError(f"Scientific inputs differ: {key}")
    for name in a["outputs"]:
        if name.endswith(".csv"):
            x, y = pd.read_csv(left / name), pd.read_csv(right / name)
            x = x.drop(columns=[c for c in x if isinstance(c, str) and c.endswith("seconds")])
            y = y.drop(columns=[c for c in y if isinstance(c, str) and c.endswith("seconds")])
            pd.testing.assert_frame_equal(x, y, check_exact=False, rtol=1e-8, atol=1e-5)


def smoke() -> dict[str, bool]:
    tech = Technology("test", 1000, 0, 50, 0, 20, 1, 100, 0.9)
    system = System(
        (tech,), (Asset("test", "test", "test", 100, 2020, 2050),), Storage(), 6000, 0.05
    )
    result = dispatch(
        system, Periods((40.0,), ((1.0,),), (0.5,), (10.0,), "hand-oracle"), np.array([100.0])
    )
    checks = {
        **result.checks,
        "known_cost": bool(np.isclose(result.summary["variable_resource_cost_gbp"], 10000)),
        "unweighted_marginal_price": bool(np.isclose(result.hourly.price_gbp_per_mwh.iloc[0], 50)),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Smoke oracle failed: {checks}")
    return checks


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="gbflex",
        description="Exploratory investment ABM and planner; not calibrated GB prediction",
    )
    sub = root.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo").add_subparsers(dest="action", required=True).add_parser("run")
    demo.add_argument("--config", type=Path)
    demo.add_argument("--seeds", default="11,22,33")
    demo.add_argument("--hours", type=int)
    demo.add_argument("--output", type=Path, default=Path("runs/demo"))
    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--hours", type=int, choices=[168, 8760], required=True)
    benchmark.add_argument("--config", type=Path)
    benchmark.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--run", type=Path, required=True)
    compare = sub.add_parser("compare-runs")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    validation = sub.add_parser("validate")
    validation.add_argument("--suite", choices=["smoke"], default="smoke")
    data = sub.add_parser("data").add_subparsers(dest="action", required=True)
    data.add_parser("catalog")
    fetch = data.add_parser("fetch")
    fetch.add_argument("--source", choices=["neso-demand"], required=True)
    fetch.add_argument("--year", type=int, required=True)
    fetch.add_argument("--output", type=Path, default=Path("data/raw"))
    check = data.add_parser("validate")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--year", type=int, help="Require the complete declared calendar year")
    study = sub.add_parser(
        "study", help="Historical study readiness; does not run a calibrated model"
    ).add_subparsers(dest="action", required=True)
    audit = study.add_parser("audit-demand")
    audit.add_argument("--protocol", type=Path, required=True)
    audit.add_argument("--raw", type=Path, default=Path("data/raw/neso-demand"))
    audit.add_argument("--output", type=Path, required=True)
    inventory = study.add_parser("inventory")
    inventory.add_argument("--protocol", type=Path, required=True)
    inventory.add_argument("--bundle", type=Path, required=True)
    gui = sub.add_parser("gui", help="Launch the optional local experiment workbench")
    gui.add_argument("--port", type=int, default=8501)
    gui.add_argument("--output", type=Path, default=Path("runs/gui"))
    export = sub.add_parser("config")
    export.add_argument("--output", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in {"demo", "benchmark"}:
            config = load_config(str(args.config)) if args.config else default_config()
            if args.hours is not None:
                config["hours"] = args.hours
            result = (
                run_demo(config, [int(s) for s in args.seeds.split(",")], args.output)
                if args.command == "demo"
                else run_benchmark(config, args.output)
            )
            print(
                json.dumps(
                    {
                        "run_id": result["run_id"],
                        "output": str(args.output),
                        "checks_passed": all(result["checks"].values()),
                        "wall_seconds": result["wall_seconds"],
                    }
                )
            )
        elif args.command == "verify":
            record = verify_run(args.run)
            print(
                json.dumps(
                    {
                        "run_id": record["run_id"],
                        "integrity": "pass",
                        "stored_scientific_checks": "pass",
                    }
                )
            )
        elif args.command == "compare-runs":
            compare_runs(args.left, args.right)
            print("Numerical replay comparison passed (rtol=1e-8, atol=1e-5; timings excluded)")
        elif args.command == "validate":
            print(json.dumps(smoke()))
        elif args.command == "config":
            import yaml

            with args.output.open("x", encoding="utf-8") as stream:
                yaml.safe_dump(default_config(), stream, sort_keys=False)
            print(args.output)
        elif args.command == "gui":
            from .workbench import launch

            return launch(args.port, args.output)
        elif args.command == "study":
            protocol = Protocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
            if args.action == "audit-demand":
                report = demand_audit(protocol, args.raw, args.output)
                print(
                    json.dumps(
                        {
                            "output": str(args.output),
                            "training_demand_complete": report["all_training_demand_complete"],
                            "S2_complete": False,
                        }
                    )
                )
            else:
                bundle = StudyBundle(
                    args.bundle.parent,
                    json.loads(args.bundle.read_text(encoding="utf-8")),
                    protocol,
                )
                print(json.dumps(bundle.readiness(), indent=2))
        elif args.action == "catalog":
            print(json.dumps(CATALOG, indent=2))
        elif args.action == "fetch":
            print(fetch_neso(args.year, args.output))
        elif args.action == "validate":
            frame = validate_data_manifest(args.manifest, expected_year=args.year)
            year = (
                args.year
                if args.year is not None
                else json.loads(args.manifest.read_text(encoding="utf-8")).get("calendar_year")
            )
            print(
                json.dumps(
                    {
                        "rows": len(frame),
                        "hours": float(frame.duration_hours.sum()),
                        "national_demand_mwh": float(
                            (frame.national_demand_mw * frame.duration_hours).sum()
                        ),
                        "calendar_coverage": calendar_coverage(frame, year)
                        if year is not None
                        else None,
                    }
                )
            )
    except (ValueError, RuntimeError, OSError, AssertionError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
