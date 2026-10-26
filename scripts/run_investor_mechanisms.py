"""Execute one pre-registered synthetic investor-identification variant."""

import argparse
import json
from pathlib import Path

from gb_flexabm.investor_mechanisms import CASES, run_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_case(args.case, args.output)
    keys = (
        "case",
        "n_complete_seed_pairs",
        "mean_policy_resource_difference_gbp",
        "median_policy_resource_difference_gbp",
        "q10_policy_resource_difference_gbp",
        "q90_policy_resource_difference_gbp",
        "count_seeds_no_effect_to_1penny",
    )
    print(json.dumps({k: report[k] for k in keys}, indent=2))


if __name__ == "__main__":
    main()
