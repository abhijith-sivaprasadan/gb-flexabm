"""Fetch the reviewed public catalogue, or audit local IMRP; no live calls in CI."""

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError

from gb_flexabm.public_inputs import acquire, audit_imrp, exclusive_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "audit-imrp"])
    parser.add_argument(
        "--catalog", type=Path, default=Path("studies/historical-v1/public-sources.json")
    )
    parser.add_argument("--root", type=Path, default=Path("data/raw/public-inputs"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--ids", help="Comma-separated source ids; default entire reviewed catalogue"
    )
    parser.add_argument("--imrp", type=Path)
    parser.add_argument("--definitions", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report path must be new")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.action == "audit-imrp":
        if args.imrp is None:
            parser.error("--imrp is required")
        protocol = json.loads(Path("studies/historical-v1/protocol.json").read_text())
        report = audit_imrp(args.imrp.read_bytes(), protocol["splits"]["train"])
    else:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        entries = catalog["sources"]
        if args.ids:
            selected = set(args.ids.split(","))
            if not selected <= {e["id"] for e in entries}:
                parser.error("Unknown source id")
            entries = [e for e in entries if e["id"] in selected]
        report = {
            "schema_version": 1,
            "scientific_acceptance": "not_assessed",
            "sources": [],
            "failures": [],
        }
        for entry in entries:
            try:
                local = (
                    args.imrp
                    if entry["id"] == "lccc-imrp"
                    else (args.definitions if entry["id"] == "lccc-imrp-definitions" else None)
                )
                record = acquire(args.root, entry, local)
                report["sources"].append(record)
                print(
                    json.dumps(
                        {"id": entry["id"], "bytes": record["bytes"], "status": "verified_bytes"}
                    ),
                    flush=True,
                )
                if record["acquisition"] == "public_https" and not record.get("cache_reused"):
                    time.sleep(1.0)
            except Exception as error:
                report["failures"].append({"id": entry["id"], "error": str(error)})
                print(json.dumps({"id": entry["id"], "error": str(error)}), flush=True)
                if isinstance(error, HTTPError) and error.code == 429:
                    # Save progress and stop this invocation; do not hammer a rate-limited host.
                    report["stopped_on_rate_limit"] = entry["id"]
                    break
    exclusive_json(args.report, report)
    return 2 if report.get("failures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
