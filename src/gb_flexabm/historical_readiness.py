"""Fail-closed, source-derived S2 historical-input readiness screening.

This checks committed acquisition audits, not model calibration, input authenticity
or out-of-sample predictive performance. Observations never enter the module.
"""

from __future__ import annotations

from .provenance import canonical_hash
from .study import Protocol


def audit_historical_readiness(
    protocol_data: dict,
    demand: dict,
    price: dict,
    generation: dict,
    source_inventory: dict,
) -> dict:
    """Expose exact gaps by year without converting acquisition into validation."""
    protocol = Protocol.from_dict(protocol_data)
    years = protocol.record["splits"]["train"]
    pinned_hashes = set()
    for name, record in (
        ("demand", demand),
        ("price", price),
        ("generation", generation),
    ):
        pinned_hashes.add(record.get("protocol_sha256"))
        if record.get("schema_version") != 1:
            raise ValueError(f"Unsupported {name} audit schema")
    if len(pinned_hashes) != 1 or not all(
        isinstance(digest, str) and len(digest) == 64 for digest in pinned_hashes
    ):
        raise ValueError("Source audits belong to different protocols")
    archived_protocol_hash = next(iter(pinned_hashes))
    archived_matches_current = archived_protocol_hash == protocol.identity
    if price.get("dataset") != "mid" or generation.get("dataset") != "fuelhh":
        raise ValueError("Market-source roles are swapped or unsupported")
    if source_inventory.get("schema_version") != 1:
        raise ValueError("Unsupported public-source inventory schema")

    def year_index(report: dict, label: str) -> dict[int, dict]:
        entries = report.get("years")
        if not isinstance(entries, list):
            raise ValueError(f"Missing {label} year records")
        result = {}
        for entry in entries:
            year = entry.get("calendar_year", entry.get("year"))
            if type(year) is not int or year in result:
                raise ValueError(f"Duplicate or invalid {label} year")
            result[year] = entry
        if set(result) != set(years):
            raise ValueError(f"{label} years do not match training protocol")
        return result

    demand_years = year_index(demand, "demand")
    price_years = year_index(price, "price")
    generation_years = year_index(generation, "generation")

    yearly = []
    blockers = []
    if not archived_matches_current:
        blockers.append("Archived data audits were pinned to an older protocol; re-admission required")
    for year in years:
        day_count = 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
        n = day_count * 48
        d = demand_years[year]
        demand_ok = (
            d.get("complete") is True
            and d.get("expected_rows") == n
            and d.get("observed_rows") == n
            and d.get("missing_intervals") == 0
            and d.get("duplicate_intervals") == 0
            and d.get("aggregation_gate_passed") is True
        )
        p = price_years[year]
        price_ok = p.get("target_usable") is True and p.get("complete") is True
        g = generation_years[year]
        gen_ok = g.get("complete") is True
        if not demand_ok:
            blockers.append(f"NESO demand incomplete or unaudited: {year}")
        if not price_ok:
            blockers.append(f"Elexon APXMIDP wholesale target incomplete: {year}")
        if not gen_ok:
            blockers.append(f"Elexon FUELHH generation incomplete: {year}")
        yearly.append(
            {
                "year": year,
                "neso_demand_complete": demand_ok,
                "elexon_mid_wholesale_price_target_usable": price_ok,
                "elexon_fuelhh_generation_complete": gen_ok,
                "mid_reported_rows": sum(
                    x.get("rows", 0) for x in p.get("categories", []) if x.get("name") == "APXMIDP"
                ),
            }
        )
    if demand.get("all_training_demand_complete") is not all(
        x["neso_demand_complete"] for x in yearly
    ):
        raise ValueError("Training demand summary contradicts per-year evidence")
    if demand.get("S2_complete") is True or price.get("S2_complete") is True:
        raise ValueError("S2 completion flag contradicts unresolved market/model roles")
    if generation.get("S2_complete") is True:
        raise ValueError("Unverified FUELHH audit cannot certify S2 completion")
    if source_inventory.get("model_ready") is not False:
        raise ValueError("This dated inventory is not a verified model-ready bundle")
    if protocol.record["status"] != "frozen":
        blockers.append("Study protocol is draft; no locked held-out evaluation")
    missing = demand.get("missing_roles")
    if not isinstance(missing, list) or any(not isinstance(r, str) for r in missing):
        raise ValueError("Missing-role inventory absent or malformed")
    if missing:
        blockers.append("Missing normalized training input roles: " + ", ".join(missing))
    blockers.append("Public-source acquisition inventory has not been admitted as a model bundle")
    return {
        "status": "NOT_READY_FOR_HISTORICAL_CALIBRATION_OR_CLAIMS",
        "protocol_sha256": protocol.identity,
        "archived_audit_protocol_sha256": archived_protocol_hash,
        "archived_audit_matches_current_protocol": archived_matches_current,
        "training_years": years,
        "observed_demand_annual_completeness_count": sum(
            row["neso_demand_complete"] for row in yearly
        ),
        "price_usable_years": sum(
            row["elexon_mid_wholesale_price_target_usable"] for row in yearly
        ),
        "generation_complete_years": sum(
            row["elexon_fuelhh_generation_complete"] for row in yearly
        ),
        "yearly": yearly,
        "blockers": blockers,
        "prior_exposure_recorded": bool(protocol.record.get("prior_exposure")),
        "scope": (
            "Committed source/acquisition audits only. Not an empirical fit, "
            "complete GB system boundary, external validation or holdout estimate."
        ),
        "source_inventory_sha256": canonical_hash(source_inventory),
    }
