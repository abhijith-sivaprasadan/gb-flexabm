# GB-FLEXABM

[![Scientific CI](https://github.com/abhijith-sivaprasadan/gb-flexabm/actions/workflows/ci.yml/badge.svg)](https://github.com/abhijith-sivaprasadan/gb-flexabm/actions/workflows/ci.yml)

**An executable electricity investment experiment: heterogeneous investors versus a perfect-foresight central planner, using the same physical dispatch model.**

Scientific status: **exploratory, synthetic and uncalibrated (software v0.3)**. The GB label describes the intended research context and optional historical-data tooling, not a validated representation of Great Britain. This is independent portfolio research software, not an official market model, university project or investment tool.

## Research question

Under a common electricity-system boundary, how do bounded investor expectations, construction delays and a stylised capacity payment change investment and resource costs relative to an ideal planner?

The implementation includes:

- Pyomo/HiGHS dispatch with generation limits, energy balance, unserved demand, fixed storage and correctly unweighted marginal-price duals.
- A multi-year capacity-expansion LP reusing those physical constraints, with construction lags, retirements and terminal asset value.
- Technology-specialist investors with adaptive expectations, heterogeneous hurdle rates, finance budgets and named random substreams; simultaneous, pro-rata investment allocation.
- Paired energy-only / stylised-capacity-payment experiments, CSV audit trails, a generated report and checksum manifests.
- An **optional local GUI** for configuring paired experiments, reopening runs, inspecting results/provenance and downloading verified ZIP/YAML artifacts.
- An **optional**, provenance-preserving official NESO demand adapter with 46/48/50-period daylight-saving and whole-calendar-year checks. Observed data do not feed the synthetic experiment.
- Analytical, property-based and metamorphic tests, locked dependencies and cross-platform CI.

## Current stage and next work

| Stage | Status |
|---|---|
| S0 — Shared model, investor engine, audit trails and reference experiment | Done, v0.1 |
| S1 — Local GUI, whole-year demand gate and delivery workflow | Implemented, v0.2 |
| S2 — Historical input/target bundle and split-access protocol | **In progress:** training-demand audit, split guards and resumable ERA5 acquisition; full bundle pending |
| S3–S5 — Empirical dispatch, calibration, locked validation and predictive baselines | Supporting utilities tested; historical institutions, fitting, evidence and independent evaluation pending |
| S6 — Zonal, flexibility, heat and hydrogen extensions | Deferred |

The [delivery plan](docs/ROADMAP.md) maps completed work to the research brief and defines acceptance criteria. Every milestone must update **this README and the [portfolio page](https://abhijith-sivaprasadan.github.io/projects/gb-flexabm.html)**, pass checks, and be committed/pushed with CI and Pages verified. See [maintainer instructions](AGENTS.md).

## Launch the GUI

After cloning (below), run from the repository directory:

```sh
uv sync --locked --extra dev --extra gui
uv run --locked --extra gui gbflex gui
```

Open **http://127.0.0.1:8501**. Configure → run → inspect → download; completed runs stay in `runs/gui/`. Use `--port 8502` if needed. The local-only launcher disables telemetry and supplies a high-contrast light theme. GitHub Pages hosts the case study, not the Python solver. The [workbench guide](docs/WORKBENCH.md) covers controls, limits, integrity and CLI replay. The GUI is optional: core commands below do not require Streamlit.

## Run offline

Requires Python 3.12 or 3.13, Git, and [uv](https://docs.astral.sh/uv/). Tested dependency resolution is committed in `uv.lock`; HiGHS is included, with no commercial solver required. Install uv with `python -m pip install uv==0.12.7` if needed.

```sh
git clone https://github.com/abhijith-sivaprasadan/gb-flexabm.git
cd gb-flexabm
uv sync --locked --extra dev
uv run --locked gbflex validate --suite smoke
uv run --locked gbflex demo run --seeds 11,22,33 --output runs/demo
uv run --locked gbflex verify --run runs/demo
```

After dependencies are installed, these commands do not require data downloads. Every output directory must be new: completed runs are never silently overwritten. Inspect `runs/demo/report.md`, `comparison.png`, `summary.csv` and `manifest.json`.

```sh
uv run --locked gbflex demo run --seeds 11,22,33 --output runs/replay
uv run --locked gbflex compare-runs runs/demo runs/replay
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked mypy
```

`verify` checks output integrity and recorded scientific checks, **not** empirical validity. `compare-runs` numerically compares CSV outputs (timings excluded; rtol 1e-8, atol 1e-5). Cross-platform byte-identical plots/timings are not promised.

## Reproduce the larger experiment

```sh
uv run --locked python scripts/reproduce.py --output runs/reference
uv run --locked gbflex benchmark --hours 168 --output runs/benchmark-168
uv run --locked gbflex benchmark --hours 8760 --output runs/benchmark-8760
```

The script runs 20 paired seeds, repeats the experiment and verifies the numerical replay. The 8,760-hour command is a **single-year synthetic dispatch benchmark**, not an annual calibrated ABM. Peak memory reports Python allocations only, excluding native solver allocations.

Export editable assumptions with `uv run --locked gbflex config --output my-scenario.yaml`, then pass `--config my-scenario.yaml` to `demo run`. Values carry explicit units and an assumption-source statement.

## Optional observed-data acquisition

New in v0.3: the [complete historical-data checklist](docs/HISTORICAL_DATA.md), training-only bundle/split guards, exogenous medoid/dispatch diagnostics, candidate/trial and sensitivity records, and evaluation metrics. These utilities do not establish historical calibration. The ERA5 plan contains **72 monthly 2013–2018 requests plus one static download** over a GB/offshore bounding box: 12 hourly wind/solar/temperature fields, not the whole catalogue.

```sh
uv sync --locked --extra dev --extra gui --extra research
uv run --locked --extra research python scripts/fetch_era5.py fetch --ids static,2013-01 --limit 2
# Process/resume the full training plan; enter the token at the hidden prompt:
uv run --locked --extra research python scripts/fetch_era5.py fetch --limit 73
uv run --locked gbflex study audit-demand --protocol studies/historical-v1/protocol.json --output runs/training-demand-audit.json
```

ERA5 commands are explicit network operations, never called by the experiment or offline tests. Jobs retain their remote IDs; cached NetCDFs are checked for hashes, units, timestamps and grid coverage. Credentials stay out of repository files. Raw weather still needs fleet-weighted wind/PV conversion. Use a fresh audit output path. See the guide for queue exit codes, storage estimates, the exact fields and all non-weather inputs.

```sh
uv run --locked gbflex data catalog
uv run --locked gbflex data fetch --source neso-demand --year 2024 --output data/raw
uv run --locked gbflex data validate --manifest data/raw/neso-demand/2024/RETURNED_HASH/manifest.json --year 2024
```

Use the exact manifest path printed by `fetch`. Raw files stay ignored locally, with their source URL, licence metadata, retrieval time and SHA-256. Dataset revisions create new hash directories. No API credential is needed. Upstream availability/schema can change; live acquisition is not part of offline CI.

New acquisitions require the entire requested year, including leap days and DST. Incomplete bytes remain for diagnosis but validation fails; no gaps are imputed. Pass `--year` explicitly for older v0.1 manifests, which did not declare a coverage year. **2024 demand was previously inspected for ingestion tests**; the proposed research holdout is not claimed untouched or preregistered.

## Read the evidence and boundaries

- [Model card](docs/MODEL_CARD.md): intended use, scientific status and non-claims.
- [Methods and accounting](docs/METHODS.md): equations, timing, common assumptions and differences.
- [Specification and acceptance map](docs/SPEC.md): implemented scope and test evidence.
- [Data contracts and sources](docs/DATA.md): demand boundary, units and provenance.
- [Roadmap](docs/ROADMAP.md): empirical calibration, adequacy, institutional mechanisms and multi-energy research gates.
- [Local workbench](docs/WORKBENCH.md): GUI setup, evidence export and acceptance tests.
- [Verification and reference results](docs/VERIFICATION.md): measured benchmarks, replay and the zero-effect stress-fixture finding.
- [Contributing](CONTRIBUTING.md), [security](SECURITY.md), [code of conduct](CODE_OF_CONDUCT.md), [citation](CITATION.cff).

Code, original documentation and synthetic fixtures are MIT-licensed. External datasets retain their publisher's terms. Please cite the exact commit and run manifest; there is no peer-reviewed validation, DOI or publication claim.
