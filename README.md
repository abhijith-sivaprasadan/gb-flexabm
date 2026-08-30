# GB-FLEXABM

[![Scientific CI](https://github.com/abhijith-sivaprasadan/gb-flexabm/actions/workflows/ci.yml/badge.svg)](https://github.com/abhijith-sivaprasadan/gb-flexabm/actions/workflows/ci.yml)

**An executable electricity investment experiment: heterogeneous investors versus a perfect-foresight central planner, using the same physical dispatch model.**

Scientific status: **v0.1 exploratory, synthetic and uncalibrated**. The GB label describes the intended research context and optional NESO data adapter, not a validated representation of Great Britain. This is independent portfolio research software, not an official market model, university project or investment tool.

## Research question

Under a common electricity-system boundary, how do bounded investor expectations, construction delays and a stylised capacity payment change investment and resource costs relative to an ideal planner?

The implementation includes:

- Pyomo/HiGHS dispatch with generation limits, energy balance, unserved demand, fixed storage and correctly unweighted marginal-price duals.
- A multi-year capacity-expansion LP reusing those physical constraints, with construction lags, retirements and terminal asset value.
- Technology-specialist investors with adaptive expectations, heterogeneous hurdle rates, finance budgets and named random substreams; simultaneous, pro-rata investment allocation.
- Paired energy-only / stylised-capacity-payment experiments, CSV audit trails, a generated report and checksum manifests.
- An **optional**, provenance-preserving official NESO demand adapter with 46/48/50-period daylight-saving checks. Observed data do not feed the synthetic experiment.
- Analytical, property-based and metamorphic tests, locked dependencies and cross-platform CI.

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

```sh
uv run --locked gbflex data catalog
uv run --locked gbflex data fetch --source neso-demand --year 2024 --output data/raw
uv run --locked gbflex data validate --manifest data/raw/neso-demand/2024/RETURNED_HASH/manifest.json
```

Use the exact manifest path printed by `fetch`. Raw files stay ignored locally, with their source URL, licence metadata, retrieval time and SHA-256. Dataset revisions create new hash directories. No API credential is needed. Upstream availability/schema can change; live acquisition is not part of offline CI.

## Read the evidence and boundaries

- [Model card](docs/MODEL_CARD.md): intended use, scientific status and non-claims.
- [Methods and accounting](docs/METHODS.md): equations, timing, common assumptions and differences.
- [Specification and acceptance map](docs/SPEC.md): implemented scope and test evidence.
- [Data contracts and sources](docs/DATA.md): demand boundary, units and provenance.
- [Roadmap](docs/ROADMAP.md): empirical calibration, adequacy, institutional mechanisms and multi-energy research gates.
- [Contributing](CONTRIBUTING.md), [security](SECURITY.md), [code of conduct](CODE_OF_CONDUCT.md), [citation](CITATION.cff).

Code, original documentation and synthetic fixtures are MIT-licensed. External datasets retain their publisher's terms. Please cite the exact commit and run manifest; there is no peer-reviewed validation, DOI or publication claim.
