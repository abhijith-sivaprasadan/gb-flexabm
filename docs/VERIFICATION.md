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

Read the [model card](MODEL_CARD.md) and [roadmap](ROADMAP.md) before interpreting or extending these results.
