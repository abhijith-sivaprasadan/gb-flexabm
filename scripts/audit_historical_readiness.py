"""Reproduce the scientific S2 admission-blocker report from committed evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gb_flexabm.historical_readiness import audit_historical_readiness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root

    def read(relative: str) -> dict:
        return json.loads((root / relative).read_text(encoding="utf-8"))

    report = audit_historical_readiness(
        read("studies/historical-v1/protocol.json"),
        read("docs/reference/training-demand-audit.json"),
        read("docs/reference/training-market-mid.json"),
        read("docs/reference/training-market-fuelhh.json"),
        read("docs/reference/public-inputs-inventory.json"),
    )
    data = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(data, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")


if __name__ == "__main__":
    main()
