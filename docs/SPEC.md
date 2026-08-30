# Executable scope and acceptance map

This v0.1 implements a bounded first research-software release, not the complete empirical research programme. Source, tests and honest status take precedence over aspirational descriptions.

| Requirement | Implementation | Acceptance evidence |
|---|---|---|
| Shared dispatch/planning physics | `optimisation._block` | known-cost/dual, scarcity, storage, monotonicity tests |
| Consistent social-cost objective | `capital_coefficient`, `planner`, `simulate` | reconstruction, planner lower-bound, build-limit relaxation |
| Heterogeneous investors | `agents.Investor` | annuity, delay, budget, pro-rata and order-invariance tests |
| Vintage stock and construction | `schema.Asset`, annual simulation | no early commissioning; exact commission/retirement boundary tests |
| Transfer accounting | `capacity_payment_gbp`, settlement tables | MW→kW property test and transfer totals |
| Reproduction and audit trails | CLI, provenance, `scripts/reproduce.py` | two-run numerical comparison, tamper rejection, no overwrite |
| Public-data foundation | optional NESO adapter | offline schema, time/unit, DST and source-hash tests |
| Failure is explicit | solver/input contracts | nonoptimal solver rejection, negative/NaN inputs, seed and status checks |
| Communication | generated report, model card | quantities tied to CSVs; non-claims beside results |

No live APIs run during the test suite. GitHub CI tests Python 3.12 on Linux and Windows and Python 3.13 on Linux. CI's small demo tests the executable workflow; the larger 20-seed experiment and synthetic annual dispatch are explicit reproduction commands.

## Output contracts

`summary.csv`: one row per design/seed, resource NPV, planner NPV and difference. `annual.csv`: year/design/seed, capacity MW, energy MWh, emissions tonnes, weighted prices GBP/MWh, payment GBP and solve timing. `decisions.csv`: requested/accepted MW, expected margin, project score and commission year. `settlements.csv`: active asset energy receipts, payment and operating cashflow. `assets.csv`: owner/technology/vintage stock. `planner_annual.csv` and `planner_builds.csv`: benchmark solution. `dispatch_reference.csv`: initial-year physical LP output. `config.json` plus `manifest.json`: assumptions, source/version identity, seeds, dependency versions, solver settings, integrity hashes and machine/timing metadata.

There are no confidential inputs, placeholder analytical results or invented dataset downloads in the public fixture. Automatic documentation generation is limited to results actually produced by the model.
