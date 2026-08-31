"""Generate a training-only ERA5 plan or execute/resume bounded jobs."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
from pathlib import Path

from gb_flexabm.era5 import (
    CDS_URL,
    acquisition_plan,
    acquisition_status,
    fetch_entry,
    validate_plan,
)
from gb_flexabm.study import Protocol


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "fetch", "status"])
    parser.add_argument(
        "--protocol", type=Path, default=Path("studies/historical-v1/protocol.json")
    )
    parser.add_argument("--plan", type=Path, default=Path("studies/historical-v1/era5-plan.json"))
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--report", type=Path, help="New public-safe inventory report (status only)"
    )
    parser.add_argument(
        "--ids", help="Comma-separated planned IDs, e.g. static,2013-01; omitted means all"
    )
    parser.add_argument(
        "--limit", type=int, default=1, help="Maximum jobs to process in this invocation"
    )
    parser.add_argument("--max-wait-seconds", type=int, default=180)
    args = parser.parse_args()
    protocol = Protocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
    if args.action == "plan":
        plan = acquisition_plan(protocol)
        with args.plan.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(plan, indent=2) + "\n")
        print(
            f"Saved {len(plan['requests'])} bounded requests to {args.plan}. No download performed."
        )
        return 0
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    validate_plan(plan, protocol)
    if args.action == "status":
        report = acquisition_status(plan, protocol, args.output)
        if args.report:
            with args.report.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "verified_requests": report["verified_requests"],
                    "planned_requests": report["planned_requests"],
                    "full_historical_bundle_complete": False,
                }
            )
        )
        return 0
    if args.limit < 1 or not 0 <= args.max_wait_seconds <= 3600:
        raise ValueError("Positive limit and wait from 0 to 3600 seconds required")
    requested = args.ids.split(",") if args.ids else [entry["id"] for entry in plan["requests"]]
    if not set(requested).issubset({entry["id"] for entry in plan["requests"]}):
        raise ValueError("Unknown request ID; only training-plan requests can be fetched")
    selected = [entry for entry in plan["requests"] if entry["id"] in requested][: args.limit]
    from ecmwf.datastores import Client

    token = getpass.getpass("Copernicus personal access token (hidden; not stored): ").strip()
    if not token:
        print("No token supplied; no request made.")
        return 2
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        client = Client(
            url=CDS_URL,
            key=token,
            timeout=60,
            progress=False,
            maximum_tries=1,
            sleep_max=20,
            log_callback=lambda *args, **kwargs: None,
        )
        for entry in selected:
            print(
                f"Processing {entry['id']}: {len(entry['request']['variable'])} variables.",
                flush=True,
            )
            result = fetch_entry(entry, args.output, client, max_wait_seconds=args.max_wait_seconds)
            print(json.dumps(result), flush=True)
            if result["status"] == "queued":
                print("Resume the same command later; the saved remote job will be reused.")
                return 3
    except Exception as exc:
        message = str(exc).lower()
        reason = (
            "accept the dataset terms on CDS"
            if "licen" in message or "terms" in message
            else "authentication/permission refused"
            if "401" in message or "403" in message
            else "check CDS request status and local snapshot checks; no automatic resubmission after uncertain errors"
        )
        print(f"Acquisition failed ({type(exc).__name__}): {reason}.")
        return 2
    finally:
        token = ""
        logging.disable(previous_logging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
