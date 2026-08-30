"""Deterministic scientific identities and tamper-evident run manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .optimisation import SOLVER_OPTIONS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def code_state() -> dict[str, Any]:
    package = Path(__file__).parent
    sources = {
        str(p.relative_to(package)).replace("\\", "/"): sha256(p)
        for p in package.rglob("*")
        if p.suffix in {".py", ".yaml"}
    }
    repo = package.parent.parent

    def git(*args: str) -> str | None:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    sha, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    return {
        "git_sha": sha,
        "working_tree_dirty": bool(status) if status is not None else None,
        "source_sha256": canonical_hash(sources),
        "version": __version__,
    }


def write_manifest(
    output: Path,
    config: dict[str, Any],
    seeds: list[int],
    kind: str,
    elapsed: float,
    checks: dict[str, bool],
) -> dict[str, Any]:
    versions = {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "pyomo", "highspy")}
    identity = {
        "config_sha256": canonical_hash(config),
        "random_seeds": seeds,
        "kind": kind,
        "code": code_state(),
        "dependencies": versions,
        "solver_options": SOLVER_OPTIONS,
        "data_kind": config["scientific_status"],
    }
    manifest = {
        **identity,
        "schema_version": 1,
        "run_id": canonical_hash(identity),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "wall_seconds": elapsed,
        "solver_status": "optimal",
        "checks": checks,
        "outputs": {
            str(p.relative_to(output)).replace("\\", "/"): sha256(p)
            for p in sorted(output.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return manifest


def verify_run(output: Path) -> dict[str, Any]:
    record = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    identity_keys = (
        "config_sha256",
        "random_seeds",
        "kind",
        "code",
        "dependencies",
        "solver_options",
        "data_kind",
    )
    if canonical_hash({k: record[k] for k in identity_keys}) != record["run_id"]:
        raise ValueError("Scientific run identity mismatch")
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    if canonical_hash(config) != record["config_sha256"]:
        raise ValueError("Configuration checksum mismatch")
    for name, expected in record["outputs"].items():
        path = (output / name).resolve()
        if (
            not path.is_relative_to(output.resolve())
            or not path.is_file()
            or sha256(path) != expected
        ):
            raise ValueError(f"Output checksum mismatch: {name}")
    if (
        record["solver_status"] != "optimal"
        or not record["checks"]
        or not all(record["checks"].values())
    ):
        raise ValueError("Stored scientific checks did not all pass")
    return record
