"""Publishable synthetic experiment recipe; no live API calls or overwrites."""

import argparse
import json
from pathlib import Path

from gb_flexabm.cli import compare_runs, default_config, run_demo

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
config = default_config()
seeds = list(range(101, 121))
for name in ("experiment", "replay"):
    manifest = run_demo(config, seeds, args.output / name)
    print(
        json.dumps(
            {"stage": name, "run_id": manifest["run_id"], "seconds": manifest["wall_seconds"]}
        ),
        flush=True,
    )
compare_runs(args.output / "experiment", args.output / "replay")
print("20 paired seeds: numerical replay passed", flush=True)
