"""Audit an authorized ORIGINAL BMRS MID CSV without fetching network data.

Usage:
python scripts/audit_legacy_mid_archive.py archive.csv --year 2017 \\
  --source-url https://publisher.example/original.csv \\
  --licence "Publisher terms apply (review pending)" \\
  --retrieved-at-utc 2026-10-26T19:00:00Z \\
  --output runs/mid-2017-archive-audit.json

The example URL is not a claim of an actual accessible archive.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gb_flexabm.legacy_mid_archive import audit_mid_archive, write_mid_audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--licence", required=True)
    parser.add_argument("--retrieved-at-utc", required=True)
    parser.add_argument(
        "--revision-rule", choices=("unique_only", "active_flag"), default="unique_only"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit_mid_archive(
        args.source,
        args.year,
        source_url=args.source_url,
        licence=args.licence,
        retrieved_at_utc=args.retrieved_at_utc,
        revision_rule=args.revision_rule,
    )
    write_mid_audit(report, args.output)
    print(
        json.dumps(
            {
                "year": args.year,
                "product_calendar_complete": report["apx_price_product_complete"],
                "missing_intervals": report["coverage"]["missing_intervals"],
                "zero_volume_rows": report["zero_volume_apx_rows"],
                "historical_bundle_admitted": False,
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
