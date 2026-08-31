# Local experiment workbench — v0.2 / S1

The GUI is a thin Streamlit interface to `cli.run_demo`, not a second scientific implementation or hosted service. It remains synthetic and uncalibrated.

## Start and use

```sh
uv sync --locked --extra dev --extra gui
uv run --locked --extra gui gbflex gui
```

Open **http://127.0.0.1:8501**. Start from the repository directory so discovery uses `data/raw/neso-demand`. Use `--port 8502` if needed; `--output runs/gui-other` selects another run directory. Stop with Ctrl+C. The launcher binds loopback only, disables usage telemetry, keeps CORS/XSRF protections, and uses dark text on light surfaces. It is not configured for public hosting, authentication or job scheduling.

1. Set periods, horizon, demand, growth, fixed payment and paired seeds.
2. Submit **Run paired experiment**; editing controls does not start the solver.
3. Inspect the chart, per-seed costs, annual tables, saved assumptions, source identity and checksums.
4. Download the verified ZIP and saved YAML. Reopen local results with the saved-run selector.
5. Under **Data readiness**, check a selected local demand manifest against a declared year. There is no automatic download or substitution of observed data into the model.

Interactive bounds: 24/48/168 periods, 2–6 years and 1–10 paired seeds. Use the CLI for larger studies. One solver workload per GUI process is allowed; a second session gets a busy error. Separate processes are not coordinated.

Each attempt gets a fresh UUID directory. Failed partial folders remain for diagnosis but are not offered as completed runs. Outputs are reverified on display/export. Editing controls does not relabel an old result. A failed attempt clears active success; tampering disables results/downloads. ZIP export contains only manifest-listed outputs and the manifest, never adjacent notes or raw data.

## Replay a GUI run

Download its YAML and use the **recorded seeds**, not currently edited controls:

```sh
uv run --locked gbflex demo run --config gbflex-scenario.yaml --seeds 11,12 --output runs/cli-replay
uv run --locked gbflex compare-runs runs/gui/RECORDED_FOLDER runs/cli-replay
```

Matching inputs reproduce numerical CSVs within the stated tolerances. Identity also records code/dependencies, so changed code is not the same scientific run. Historical reference artifacts remain v0.1 evidence, not silently regenerated v0.2 results.

## Acceptance evidence

- `tests/test_gui.py`: real Streamlit AppTest solver run and CLI numerical replay; saved assumptions, failed reruns, tamper rejection, launcher settings.
- `tests/test_workbench.py`: input/unit/seed bounds, exclusive solver access, failure cleanup, history and verified-only ZIPs.
- `tests/test_data.py`: complete common/leap years, DST, truncation, gaps, duplicates, wrong-year/unordered data and rejected partial acquisition.
- Browser checks and execution results are recorded in `VERIFICATION.md` and CI.

GitHub Pages hosts the [case study](https://abhijith-sivaprasadan.github.io/projects/gb-flexabm.html#workbench), **not the Python GUI**. S2's historical bundle and split protocol come next, not fitting the synthetic fixture.

Framework references: [forms](https://docs.streamlit.io/develop/concepts/architecture/forms), [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest), [configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml). Streamlit 1.62.0 is pinned in the optional GUI extra; the core CLI does not require it.
