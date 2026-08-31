"""Publish a metadata-only inventory after rehashing local raw and extracted files."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from gb_flexabm.public_inputs import audit_imrp, checked_id, exclusive_json


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", type=Path, default=Path("studies/historical-v1/public-sources.json")
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/public-inputs"))
    parser.add_argument(
        "--extracted-root", type=Path, default=Path("data/processed/public-inputs-v2")
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report path must be new")
    catalogue = json.loads(args.catalog.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalogue_sha256": digest(args.catalog),
        "model_ready": False,
        "sources": [],
        "unacquired": [],
        "extraction_pending": [],
    }
    for entry in catalogue["sources"]:
        ident = checked_id(entry["id"])
        found = False
        for manifest in sorted((args.raw_root / ident).glob("*/manifest.json")):
            record = json.loads(manifest.read_text(encoding="utf-8"))
            if record["url"] != entry["url"]:
                continue
            path = manifest.parent / ("source." + entry["format"])
            if digest(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
                raise ValueError("Raw integrity failure: " + ident)
            found = True
            public = {
                k: record[k]
                for k in [
                    "id",
                    "url",
                    "title",
                    "group",
                    "format",
                    "sha256",
                    "bytes",
                    "retrieved_at",
                    "license_status",
                    "license_url",
                ]
            }
            extracted = args.extracted_root / ident / record["sha256"]
            if (extracted / "extraction.json").exists():
                receipt = json.loads((extracted / "extraction.json").read_text(encoding="utf-8"))
                for item in receipt["outputs"]:
                    if item["file"] not in {"extracted.json", "extracted.jsonl"}:
                        raise ValueError("Unexpected extraction filename")
                    if digest(extracted / item["file"]) != item["sha256"]:
                        raise ValueError("Extraction integrity failure: " + ident)
                public["extraction"] = receipt
            else:
                report["extraction_pending"].append(ident)
            report["sources"].append(public)
            if ident == "lccc-imrp":
                protocol = json.loads(Path("studies/historical-v1/protocol.json").read_text())
                report["imrp_audit"] = audit_imrp(path.read_bytes(), protocol["splits"]["train"])
            if ident == "lccc-administrative-strike-prices-api":
                payload = json.loads(path.read_bytes())
                if payload["success"] is not True or payload["result"]["total"] != len(
                    payload["result"]["records"]
                ):
                    raise ValueError("Incomplete public datastore response: " + ident)
                public["api_complete_records"] = payload["result"]["total"]
        if not found:
            report["unacquired"].append(ident)
    report["counts"] = {
        "catalogue_entries": len(catalogue["sources"]),
        "acquired_snapshots": len(report["sources"]),
        "raw_bytes": sum(s["bytes"] for s in report["sources"]),
        "by_group": dict(Counter(s["group"] for s in report["sources"])),
        "by_format": dict(Counter(s["format"] for s in report["sources"])),
    }
    report["exposure"] = (
        "Mechanical extraction includes post-training observations and current revisions. IMRP numeric QA is training-only. No fitting or target substitution; no pristine holdout claim."
    )
    report["limitations"] = [
        "Mechanical extraction is not a normalized historical bundle",
        "PDF text requires table/visual review; blank/image pages are counted",
        "Third-party rights remain subject to review",
        "Missing APXMIDP years, temporal/monetary/GB boundaries and weather conversion are unresolved",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    exclusive_json(args.report, report)
    print(
        json.dumps(
            {
                "counts": report["counts"],
                "unacquired": report["unacquired"],
                "extraction_pending": report["extraction_pending"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
