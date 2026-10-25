"""Compare original GB price and generation coverage against a separate product."""
from __future__ import annotations


def compare_product_coverage(mid: dict, fuelhh: dict, imrp: dict) -> dict:
    if mid["dataset"] != "mid" or fuelhh["dataset"] != "fuelhh":
        raise ValueError("Unexpected source products")
    if imrp["source_product"] != "LCCC_IMRP" or imrp["matches_original_target_semantics"]:
        raise ValueError("Different market product cannot be treated as identical")
    prices = {r["year"]: r for r in mid["years"]}
    generation = {r["year"]: r for r in fuelhh["years"]}
    years = sorted(int(y) for y in imrp["years"])
    if years != list(range(2013, 2019)) or set(prices) != set(years) or set(generation) != set(years):
        raise ValueError("Expected complete training-year inventory")
    rows = []
    for year in years:
        rows.append({
            "year": year,
            "original_market_usable": prices[year]["target_usable"],
            "original_generation_complete": generation[year]["complete"],
            "separate_hourly_native_rows": imrp["years"][str(year)],
        })
    return {
        "decision": "NO_SUBSTITUTION",
        "rows": rows,
        "complete_original_market_years": sum(r["original_market_usable"] for r in rows),
        "complete_original_generation_years": sum(r["original_generation_complete"] for r in rows),
        "new_original_data_verified": False,
        "models_fitted": False,
    }
