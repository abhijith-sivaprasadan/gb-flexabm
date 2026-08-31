# Verification record — 30 August 2026

## Reproducible reference

The full [reference experiment](reference/experiment/) was generated from clean source commit `014125940547c2e2e497e95fd862d07964f3c44a` using locked dependencies, Python 3.12.14 and Windows 11. Later documentation/test/CI-only changes do not alter its scientific source. Run identity: `5043d2b799be566c5f0747daff24c9b2f9df75b09c7c133fdf78118206b24ec0`.

`scripts/reproduce.py` ran seeds 101–120 under both designs, six years, 168 synthetic periods/year. The independent replay agreed for every numeric CSV (rtol 1e-8, atol 1e-5; timing fields excluded). Experiment and replay took 54.08 s and 54.90 s. Every recorded scientific check passed, including the common-accounting planner lower bound. Original output bytes are preserved in Git for checksum verification.

```sh
uv run --locked gbflex verify --run docs/reference/experiment
uv run --locked python scripts/reproduce.py --output runs/new-reference
uv run --locked gbflex compare-runs docs/reference/experiment runs/new-reference/experiment
```

Changing scientific source or dependencies can change outputs. Use the generating commit for exact historical reproduction. Manifests are integrity records, not authenticity signatures or empirical validation.

## Finding: no investment response in this stress fixture

| Quantity | Value |
|---|---:|
| Planner resource NPV | GBP 101,663,469,425.84 |
| ABM resource NPV, either design, every seed | GBP 111,458,655,297.18 |
| Planner–agent resource gap | GBP 9,795,185,871.34 |
| Payment minus energy-only resource NPV | GBP 0, every paired seed |
| Six-year capacity receipts | GBP 11,467,125,000, undiscounted |

Investment scores are positive throughout the eligible construction horizon. Annual finance budgets cap the requested quantities; the extra payment does not move a request across an investment threshold. Seed-dependent scores vary but accepted capacity paths do not, so physical-result quantile bands collapse. `decisions.csv` and `settlements.csv` make this inspectable. A separate threshold regression test demonstrates that a payment can change an investor decision when its NPV crosses zero.

This is a **negative result about one authored fixture**, not evidence of real-market policy ineffectiveness. The planner gap includes perfect foresight and unconstrained investor finance in the planner; it is not a measured welfare loss. VOLL-driven stress costs are not estimates of GB system expenditure.

## Measured synthetic dispatch benchmarks

| Chronological periods | Weighted hours | Model + solve time | Solver-call time | Peak Python allocations |
|---|---:|---:|---:|---:|
| 168 | 8760 | 0.476 s | 0.379 s | 4,201,983 bytes |
| 8760 | 8760 | 25.112 s | 19.504 s | 179,610,635 bytes |

Machine: Windows-11-10.0.26200-SP0; processor identifier `AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD`; single-thread HiGHS 1.13.1. These are individual measurements, not repeated benchmark confidence intervals. `tracemalloc` excludes native solver memory: **not peak RSS**. Full metrics, dispatch CSVs and manifests are in [benchmark-168](reference/benchmark-168/) and [benchmark-8760](reference/benchmark-8760/).

Both cases pass balance/storage/objective checks. Maximum power-balance residual is approximately 3.64e-12 MW. These are single-year **synthetic dispatch** benchmarks, not full-year empirical ABM validation. Unserved energy changes from 4.307 TWh in the weighted short block to 7.839 TWh in the full synthetic year: the short block is **not** an established annual scarcity approximation.

## Data and software checks

- Official NESO 2024 acquisition parsed 17,568 half-hour rows, 8,784 hours, and 230,902,926 MWh of National Demand. Raw SHA-256: `fa7895b6e9ab5eb1b450949d969cb18ffeb6005359fc71c79c87e1c47e59cac6`. Raw files are not redistributed and are not model inputs; [acquisition manifest](reference/neso-2024-manifest.json) records source/licence/hash metadata only.
- Offline tests cover analytical optima, dual scaling, cyclic storage, vintages, investment budgets, payment thresholds, monotonicity, random-stream isolation, invalid inputs, rejected solver failure, schema/DST/unit contracts and tamper detection.
- A fresh public-repository clone was installed into an independent virtual environment for a second installation/test/smoke check. Consult CI for current cross-platform results; no live data API is required by tests.
- Python 3.13 CI explicitly selects the matrix interpreter through `UV_PYTHON`, overriding the repository's default `.python-version` (3.12). This prevents an accidental environment replacement from masking the intended version test.
- The locked Matplotlib version emits upstream Pyparsing deprecation warnings. These are visible and do not fail the numerical tests; they are not suppressed as part of verification.

## S1 / software v0.2 — local workbench and data completeness (31 August 2026)

- Local Python 3.12: **77 tests pass**, Ruff lint/format pass, and mypy passes for 11 source files. GUI tests use the pinned Streamlit 1.62.0 optional extra. The 14 existing Matplotlib/Pyparsing deprecation warnings remain visible.
- A real Streamlit AppTest runs a 24-period, two-year, one-seed paired experiment and numerically compares all CSV outputs with `cli.run_demo` using identical saved configuration/seeds. The tests also cover failed reruns, modified result files, missing manifest entries, export scope, run locking and control bounds.
- Browser acceptance executed a 24-period, three-year, two-seed experiment with 22.5 GW base demand; the GUI displayed saved assumptions, resource comparisons, generated plots and export controls. The data tab accepted the existing 2024 manifest and rejected a requested 2023 year. The delivery-plan tab and saved-run controls were inspected. These are functional checks, not new empirical results.
- Whole-year validation of the previously acquired 2024 NESO snapshot passed: 17,568 ordered half-hours, 8,784 hours, no missing/unexpected/duplicate intervals, first UTC interval `2024-01-01T00:00:00+00:00`, last `2024-12-31T23:30:00+00:00`. Its raw SHA-256 and ND total remain unchanged. No new observations were fitted or substituted into the model.
- Browser review identified dim captions and low-contrast JSON/code syntax defaults. The light workbench now explicitly styles those text surfaces and status messages. The portfolio's 120 sampled case-study text elements passed the computed foreground/background contrast probe; this is a targeted check, not a full accessibility certification.
- The original v0.1 experiment and both benchmark bundles still pass integrity verification. They are preserved historical evidence with their original source identity, not regenerated v0.2 artifacts.
- CI installs the optional GUI extra and runs real AppTest checks on Python 3.12 Linux/Windows and 3.13 Linux. Use the linked live workflow for the current remote result. Portfolio static checks pass for 77 HTML pages, 60 JavaScript files and 23 JSON files.

At the S1 release, S2 remained unimplemented. Subsequent partial tooling is recorded below; previous inspection of 2024 demand remains disclosed and no pristine holdout is claimed.

## S2 data tooling / software v0.3 (31 August 2026)

- Local Python 3.12: **117 tests pass**, Ruff lint/format and mypy pass (16 source files). The 14 upstream Matplotlib/Pyparsing warnings remain visible. CI installs optional research dependencies but all tests use authored local fixtures/mocked jobs, not live services.
- [Training-demand audit](reference/training-demand-audit.json): all six years 2013–2018 have complete ordered half-hour coverage, no missing/duplicate/unexpected intervals, and zero energy error when aggregated to hourly means. Raw hashes are recorded; this is ingestion evidence, not historical model validation.
- [ERA5 acquisition snapshot](reference/era5-acquisition-status.json): static geopotential/land-sea mask and January 2013 were downloaded and verified. January contains 12 fields × 744 hours × 3,185 cells, with no missing values. This timestamped snapshot records **2 of 73** plan requests, not completion of the full training-weather acquisition. Public evidence excludes tokens, local private paths and remote job IDs.
- Resume tests prove a saved remote job is reused rather than resubmitted; cached content is rechecked. NetCDF tests reject wrong timestamps/grid/units, missing fields and altered files. Archive tests reject traversal/unexpected members. The bounded plan cannot be widened to holdout years by merely recomputing its checksum.
- Study tests reject phase violations before any observation read, invalid parameter-lock hashes, out-of-origin vintages and cross-year table contents. Candidate search logs failed seeds without exposing arbitrary callback exception text; it does not issue a scientific lock.
- Exogenous medoid tests preserve hours and forced extremes. A real LP test compares independent-day and linked storage chronology. Constant-response/confounded sensitivity tests and zero-denominator/seed/baseline tests preserve failed or undefined metrics. These are authored numerical oracles, not empirical S3–S5 evidence.
- Real Streamlit AppTest still numerically matches the CLI and checks exports/failures. Browser review confirms the acquisition list, hidden-token terminal instructions, selected training-demand year and explicit pending-stage labels. Each weather variable occupies its own readable row; no credential field was added to the GUI.
- A targeted light-theme DOM-text probe checked the GUI and portfolio. It identified a low-contrast footer link on the case study; that link now uses dark blue. Canvas-rendered dataframe text was inspected visually, not included in DOM contrast arithmetic. This is not a full accessibility certification.
- The original v0.1 experiment and both synthetic benchmark bundles still pass integrity checks and remain unchanged. The full historical bundle, weather conversion, institutional predictor, historical fitting/locking, no-fit evaluation and independent scientific review remain pending.

Read the [model card](MODEL_CARD.md) and [roadmap](ROADMAP.md) before interpreting or extending these results.
