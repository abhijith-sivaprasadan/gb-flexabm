# Contributing

Small, reproducible contributions are welcome. Open an issue before changing scientific boundaries or adding a dataset. Explain the research question, units, source licence and proposed verification oracle. Do not upload private, restricted or credential-bearing data.

1. Fork, create a topic branch and install with `uv sync --locked --extra dev --extra gui` (GUI extra required for interface tests).
2. Change source plus the matching methods/model-card documentation.
3. Add an analytical or metamorphic regression test. Numerical plausibility alone is insufficient.
4. Run `uv run --locked --extra gui pytest -q`, `uv run --locked ruff check src tests scripts`, `uv run --locked ruff format --check src tests scripts` and `uv run --locked mypy`.
5. Open a PR describing the old/new scientific assumptions, reproduction command and results. Preserve all uncertainty and non-validation labels.

Every maintainer milestone also updates `README.md`, `docs/ROADMAP.md`, verification evidence, and the companion portfolio case study/README. Record the portfolio PR or commit. Push both repositories through normal review, check CI, and verify live Pages content before reporting publication complete. If a contributor cannot edit the portfolio, identify the maintainer follow-up explicitly. See `AGENTS.md`.

Normal CI is offline after dependency installation. Do not make tests depend on live market APIs. Update `uv.lock` deliberately when changing dependencies. Contribution implies permission to distribute your original contribution under MIT; external material requires separate attribution and compatible terms. Acceptance is by maintainer review, not an automatic commitment to support new features.
