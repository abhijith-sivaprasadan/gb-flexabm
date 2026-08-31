"""Acquire/audit bounded training-only Elexon chunks; no credentials required."""

import argparse
import json
from pathlib import Path

from gb_flexabm.market_data import audit_market, fetch_chunk, training_requests
from gb_flexabm.study import Protocol


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "audit"])
    parser.add_argument("--dataset", choices=["mid", "fuelhh"], required=True)
    parser.add_argument(
        "--protocol", type=Path, default=Path("studies/historical-v1/protocol.json")
    )
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--years", help="Comma-separated training years; all training years by default"
    )
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--output", type=Path, help="New audit JSON path")
    args = parser.parse_args()
    protocol = Protocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
    if args.action == "audit":
        if args.output is None or args.years:
            parser.error("Audit needs --output and always checks all training years")
        report = audit_market(protocol, args.raw, args.dataset, args.output)
        print(json.dumps(report["years"], indent=2))
        return 0
    if args.limit < 1:
        parser.error("Positive chunk limit required")
    years = [int(y) for y in args.years.split(",")] if args.years else None
    requests = training_requests(protocol, args.dataset, years)
    for request in requests[: args.limit]:
        print(f"Fetching {args.dataset}/{request['id']}", flush=True)
        record = fetch_chunk(args.raw, request)
        print(
            json.dumps(
                {
                    "id": request["id"],
                    "rows": record["coverage"]["rows"],
                    "coverage_complete": record["coverage"]["complete_for_observed_categories"],
                }
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(
            f"Acquisition stopped ({type(exc).__name__}). Completed chunks remain reusable; inspect any rejected snapshot before retrying."
        )
        raise SystemExit(2) from None
