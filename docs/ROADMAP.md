# Delivery plan and scientific release gates

The current release is a usable exploratory foundation. The larger research programme is not marked complete.

Updated 31 August 2026. The high-level roadmap below is now broken into executable milestones. **Software v0.2 remains scientifically exploratory.** A GUI does not advance the model to calibrated or predictive status.

## Current position against the research plan

| Workstream | Current evidence | Status |
|---|---|---|
| Repository contracts | MIT, citation, schemas, locked environment, CLI, manifests, tests and cross-platform CI | Delivered for exploratory scope |
| Official data | NESO demand acquisition, immutable hashes, UTC/DST and complete-year gate | Partial: other historical inputs and targets missing |
| Dispatch and planner | Shared single-node LP, storage, vintages, dual prices and objective checks | Delivered for synthetic electricity experiments |
| Investors and markets | Adaptive investors, budgets, construction/retirement and fixed payment | Partial: official CM/CfD and empirical behaviour missing |
| Time reduction | Measured 168/8,760-period synthetic dispatch; repeated short blocks | Partial: no empirical approximation or annual ABM validation |
| GUI | Configure, run, reopen, inspect and export the same engine; data coverage checks | S1 implemented |
| Calibration and locked validation | No fitted parameters or historical skill metrics | Not started |
| Networks, heat and hydrogen | Not implemented | Deferred |

The 20-seed reference experiment and numerical replay are not a seed-convergence study. Its zero physical response to the capacity payment is preserved, not tuned away.

## Execution milestones

Use S-identifiers to separate delivery from scientific maturity. The research brief's maturity ladder and later release table used different version labels; neither label establishes validation.

| Stage | Deliverable and completion gate | Status |
|---|---|---|
| **S0 — Exploratory foundation** | Shared dispatch/planner, investor/vintage engine, reference experiment, analytical/property tests and non-claims | Done in v0.1 |
| **S1 — Experiment workbench** | Local GUI/CLI numerical-equivalence test; failure/tamper/export checks; complete-year demand gate; documentation/publication contract | Implemented in v0.2; see `WORKBENCH.md` and CI |
| **S2 — Historical bundle and split protocol** | Pinned demand, fleet, costs, fuel/carbon, wholesale targets and weather availability; licences/units/vintages/money basis; coverage report and enforced split-access rules | **Next — not implemented** |
| **S3 — Empirical dispatch and time reduction** | Historical full-year benchmark; generation/price baselines; exogenous-only medoids plus extremes; reduced/full-year energy, peaks, cost and storage errors | Pending S2 |
| **S4 — Institutions and calibration** | Historical CM/CfD, sensitivity screen, identifiable behavioural parameters, common seeds, all trials recorded and parameters locked | Pending S2–S3 |
| **S5 — Locked research evaluation** | No-fit validation/holdout, seed convergence, rolling-origin baseline comparisons, failures published and independent review | Pending S4 |
| **S6 — Integrated energy** | Zonal/PyPSA-GB, flexibility, probabilistic adequacy and then heat/hydrogen with shared energy balances and separate empirical gates | Deferred |

S2 will use reviewable slices: (a) historical demand and explicit series contracts; (b) fleet/cost and price/weather inputs; (c) versioned bundles and split-access tests. Do not fit with a demand-only dataset. Specify imports, embedded generation, availability versus curtailed output, price products and monetary base year. Elexon/DUKES/ERA5 connectors are not complete today.

### Historical split and prior exposure

Proposed windows: 2013–2018 training, 2019–2021 internal validation, 2022–2025 final evaluation. These are **not frozen or preregistered**. Assess coverage and forecast-origin vintages first. Calibration code must receive training observations only; future tests must reject later observations.

**2024 NESO demand has already been inspected** for ingestion and annual totals. Record that exposure; do not describe the entire proposed final window as pristine/untouched. This has not fitted behaviour, but no holdout-access guard or calibration pipeline exists yet. Distinguish explanatory backcasts (realised inputs) from forecast-origin backtests (information available then); only the latter can support predictive-skill claims.

Before S3–S5, freeze metrics/baselines in a versioned protocol. The brief's thresholds are proposed project gates, not universal standards: for example annual-demand aggregation error <1%, dispatch-cost approximation error <3%, generation-share MAE ≤3 percentage points. Publish failures. Full-year chronology, scarcity tails, linked storage and multiple weather years need separate tests. One hundred seeds is a proposed starting point, not a magic validation threshold.

## Definition of done — every future milestone

1. Implement a bounded stage and regressions; preserve old evidence and unrelated files.
2. Run lint, formatting, typing, offline tests and relevant GUI/reproduction checks.
3. Update **README**, this roadmap, relevant model/method/data documentation and verification evidence. State remaining work and limitations.
4. Update the **portfolio case study and its repository README**; update homepage/library/index summaries when capabilities change. Distinguish a local GUI from a hosted demo.
5. Commit and push both repositories through normal review. Verify CI, merge status, Pages deployment and live content. If blocked, identify the exact unpublished work; local edits alone are not a completed delivery.

This contract also appears in `AGENTS.md`, `CONTRIBUTING.md` and the PR checklist. The original scientific gates remain below; no gate is passed merely by adding a GUI.

## Gate 1 — empirical electricity baseline (pending)

- Pin official fleet, demand, technology-cost and weather-derived availability datasets with redistribution terms and monetary base years.
- Separate calibration and holdout years. Define price product and treatment of imports, embedded generation, availability versus observed output and non-dispatchable residual demand.
- Estimate behavioural parameters with identifiable targets and uncertainty; compare against naive investment rules and multiple plausible parameter sets.
- Reproduce seasonal/full-year chronology, scarcity tail events and storage energy behaviour. Quantify representative-period approximation error.
- Publish out-of-sample metrics against preregistered acceptance criteria. Do not label the model calibrated because the solver converges.

## Gate 2 — robust market-design research (pending)

- Endogenous Capacity Market demand/auction/eligibility and delivery rules; separately specified CfD settlement if introduced.
- Economic exit/mothballing, investor finance dynamics and sensitivity to foresight, risk, entry, construction delay and terminal value.
- Multi-weather-year forced-outage adequacy ensembles before any LOLE/EENS probability claim.
- Seed-convergence and paired effect-size analysis; 20 illustrative seeds are not a convergence proof. Add computational budgets and larger ensembles as warranted.
- Full-year multi-year ABM performance, independent model comparison and external scientific review.

## Gate 3 — integrated energy research (pending)

Add electricity–heat–hydrogen conversion, storage, network and market-boundary equations with explicit energy balances, efficiencies and shared dispatch/planner treatment. Start with analytical cross-vector fixtures; then extend empirical data and validation. Existing electricity tests cannot establish multi-energy correctness.

## Release policy

Do not rename an exploratory tag as a validated release. A stable research release needs the relevant gate evidence, versioned input snapshots, clean-commit replay, limitations, archived artifacts and independent review. A DOI/publication is a separate dissemination milestone, not implied by this repository.
