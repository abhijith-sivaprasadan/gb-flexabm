"""Small local GUI adapter; all scientific calculations stay in the CLI engine."""

from __future__ import annotations

import io
import json
import math
import os
import re
import subprocess
import sys
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .cli import default_config, run_demo
from .provenance import verify_run

_RUN_LOCK = threading.Lock()


def scenario(
    hours: int, year_count: int, demand_gw: float, growth_percent: float, payment: float
) -> dict[str, Any]:
    """Bound interactive workloads and convert display units once, at the boundary."""
    if type(hours) is not int or hours not in (24, 48, 168):
        raise ValueError("Interactive periods must be 24, 48 or 168")
    if type(year_count) is not int or not 2 <= year_count <= 6:
        raise ValueError("Interactive horizon must be 2–6 years")
    for name, value, low, high in (
        ("Base demand (GW)", demand_gw, 1, 60),
        ("Demand growth (%)", growth_percent, -5, 10),
        ("Capacity payment (GBP/kW/year)", payment, 0, 300),
    ):
        if isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be finite and between {low} and {high}")
    config = default_config()
    config.update(
        hours=hours,
        years=config["years"][:year_count],
        base_demand_mw=demand_gw * 1000,
        demand_growth_fraction=growth_percent / 100,
        capacity_price_gbp_per_kw_year=payment,
    )
    return config


def seed_set(first: int, count: int) -> list[int]:
    if type(first) is not int or not 0 <= first <= 1_000_000_000:
        raise ValueError("First seed must be an integer from 0 to 1,000,000,000")
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError(
            "Interactive runs support 1–10 paired seeds; use the CLI for larger studies"
        )
    return list(range(first, first + count))


def create_run(root: Path, config: dict[str, Any], seeds: list[int]) -> Path:
    # Matplotlib and the single-thread HiGHS scheduler are shared within this process.
    # A second browser session must not run them concurrently.
    if not _RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Another local experiment is running. Try again after it finishes.")
    try:
        output = root / uuid.uuid4().hex
        run_demo(config, seeds, output)
        verify_run(output)
        return output
    finally:
        _RUN_LOCK.release()


def saved_runs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            p
            for p in root.iterdir()
            if re.fullmatch(r"[0-9a-f]{32}", p.name)
            and p.is_dir()
            and not p.is_symlink()
            and (p / "manifest.json").is_file()
        ),
        key=lambda p: p.stat().st_mtime_ns,
        reverse=True,
    )


def run_bundle(output: Path) -> bytes:
    """Export only the verified manifest's files, never arbitrary adjacent files."""
    record = verify_run(output)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(record["outputs"]) | {"manifest.json"}):
            archive.write(output / name, arcname=name)
    return buffer.getvalue()


def read_result(output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    record = verify_run(output)
    if record["kind"] != "paired_abm_planner":
        raise ValueError("The workbench requires a paired ABM/planner run")
    required = {"config.json", "summary.csv", "annual.csv", "comparison.png"}
    if not required.issubset(record["outputs"]):
        raise ValueError("Displayed result files must all be listed in the checksum manifest")
    return record, json.loads((output / "config.json").read_text(encoding="utf-8"))


def launch(port: int, output: Path) -> int:
    try:
        import streamlit  # noqa: F401
    except ImportError as exc:
        raise ValueError(
            "GUI extra missing. Install it with: uv sync --locked --extra gui"
        ) from exc
    if not 1024 <= port <= 65535:
        raise ValueError("GUI port must be between 1024 and 65535")
    env = os.environ.copy()
    env["GBFLEX_GUI_RUNS"] = str(output.resolve())
    # CLI options take precedence over a user's global Streamlit config.
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(Path(__file__).with_name("gui.py")),
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--server.enableCORS=true",
            "--server.enableXsrfProtection=true",
            "--theme.base=light",
            "--theme.primaryColor=#194185",
            "--theme.backgroundColor=#ffffff",
            "--theme.secondaryBackgroundColor=#eef2f6",
            "--theme.textColor=#18232d",
        ],
        env=env,
    )
