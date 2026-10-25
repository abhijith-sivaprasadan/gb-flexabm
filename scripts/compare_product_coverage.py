"""Derive bounded historical coverage for non-equivalent market products."""

from __future__ import annotations

import json
from pathlib import Path

from gb_flexabm.product_coverage import compare_product_coverage


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = (
        "docs/reference/training-market-mid.json",
        "docs/reference/training-market-fuelhh.json",
        "studies/historical-v1/imrp-coverage-probe.json",
    )
    reports = [json.loads((root / path).read_text(encoding="utf-8")) for path in paths]
    print(json.dumps(compare_product_coverage(*reports), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
