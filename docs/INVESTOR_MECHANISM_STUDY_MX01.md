# Study MX-01 — paired investor mechanism stress test (registered before runs)

**Scope:** pure synthetic scenario-based mechanism experiment, not British electricity market validation. This register establishes the complete design BEFORE the first GitHub Actions solve.

## Central question

The August reference `docs/reference/experiment` is a 20-seed simulation in which increasing a highly stylised generator payment changes monetary transfers but not physical investment. Test whether this **numerical policy null** is specific to the synthetic investor rules by perturbing one behavioural or financial constraint at a time, with identical physical capacity/planning equations.

## Fixed design

- Exactly six synthetic model years, 2026–2031; 168 synthetic hourly observations cyclically weighted to 8,760 hours for each year. Every case uses the **identical synthetic physical system and demand, technology costs, build limits and planner**.
- Paired common random seeds **401–412** inclusive, 12 seeds; each is evaluated with exactly two stylised policy treatments, `energy_only` (payment 0) and `stylised_capacity_payment` (75 GBP/kW/year) as coded in the fixture. This is **NOT** a credible official GB capacity auction model.
- Five investigator-chosen single-lever settings fixed before execution:
  1. `baseline`: unchanged demo assumptions.
  2. `budget_20pct`: every investor's original fixed annual budget multiplied by 0.2; project size/finance is unchanged.
  3. `budget_zero`: every investor budget set to 0; a structural negative control with no new investments permitted, not a plausible estimate.
  4. `high_hurdle`: each investor's personal investment discount/hurdle rate increased by 0.15 **absolute percentage points as a fraction** (e.g. 0.08→0.23). We mean 15 **percentage points**, not 15% relative.
  5. `zero_expectation_noise`: each investor's forecast noise fraction set to exactly zero; other parameters untouched.
- **60 matched pairs / 120 separate ABM solutions** planned. The continuous central planner is solved separately for each variant by the shared `run_demo` API; it should have the same optimum because no physical/economic `Technology` or demand inputs are modified.
- All runs must pass the previously shipped solver and accounting checks. The per-case full output must include decisions, assets, annual physical/price results, planner solution, provenance manifest and hashes.

## Outcomes and interpretation

Primary: the **paired difference** in ABM discounted resource costs under the two payment settings within the same variant and seed; paired accepted new MW; **year-by-year technology capacity and unserved MWh**. Secondary: fraction with exactly zero policy response (≤0.01 GBP cost difference and ≤1e-5 MW construction), total capacity transfers and distribution (median, 10th–90th quantiles **across seeds**, not confidence or calibrated prediction intervals), planner resource-gap comparison, investor request volume. Do NOT report a difference just because the payment transfers money: transfers are not resource costs.

No significance claims or selective removal of seeds; all 12 per-case attempts, failures and counterexamples must be reported. Paired noise streams are deterministic by seed and investor, but endogenous prices and therefore *noise magnitudes* can change after policy pathways diverge. This comparison is conditional on the specified stylised rules and model-years, **not** a forecast of GB power investments, a policy causal estimate or empirical parameter identification.

**Historical empirical status remains BLOCKED** by the absent APXMIDP half-hourly price target, original 2013–18 generation coverage, fleet vintages, CAPEX origins and weather-availability transformation. This experiment intentionally does not simulate fake historical observations to bypass that blockade.

Run each variant:

```bash
uv run python -m scripts.run_investor_mechanisms --case baseline --output runs/mechanism-baseline
uv run python -m scripts.audit_policy_identification --run runs/mechanism-baseline --output runs/mechanism-baseline-policy.json
```

The automated workflow produces archived, hashed case directories; results are not admitted as real-world data simply because the workflow passes.
