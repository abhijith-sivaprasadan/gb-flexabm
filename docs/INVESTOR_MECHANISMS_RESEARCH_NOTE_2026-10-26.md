# Why a Stylised Capacity Payment Can Leave Investment Unchanged: A Synthetic Agent-Based Mechanism Audit

**Abhijith Sivaprasadan · 26 October 2026 · Author research note · Not peer-reviewed · No historical GB calibration**

## Abstract

We analyze a single-zone British-themed electricity investor model that shares physical dispatch constraints with a continuous perfect-foresight central planner. An existing 20-seed synthetic comparison found **no change in new investment or discounted resource costs** when a fixed illustrative capacity payment was introduced, despite sizable settlement transfers. We inspect that result at the investor-decision and asset-settlement level, then conduct a predeclared 5-variant × 12-seed × 2-treatment experiment: **120 six-year ABM trajectories**. Under all 60 matched policy comparisons, the capacity-payment treatment still changes transfers but not accepted construction, unserved energy, technology capacity or resource costs. Conversely, constraining fixed investor annual budgets to 20% of baseline raises synthetic discounted system resource costs from £111.459bn to £413.447bn; zero investment budgets raise them to £579.496bn. We derive the exact current investor profitability entry threshold from the code and demonstrate that payments cannot increase builds when investors are already above the threshold, cannot afford a project block, or cannot commission in time. These are model-specific structural results, not British market policy-effect estimates. Original historical market-price targets, generation vintages, costs and calibration remain unverified.

## 1. Research question and contribution

A central planner minimizes discounted resource costs with common technology capacity, build ceilings, storage and hourly demand. A heterogeneous collection of simulated investors instead bases investment on historically observed *within the simulation* prices, noisy adaptive margin expectations, fixed annual budgets, discrete project sizes, personal discount rates and technology construction lags. The model's policy counterfactual adds fixed payments for derated available capacity to investor revenue. It is **not** a GB Capacity Market auction, reliability standard, accreditation calculation, historical backtest or welfare evaluation.

The primary scientific question is **not** whether an imagined capacity payment 'works' in GB. It is whether the model's own payment mechanism has sufficient identification strength to alter the investment decisions whose effects are being interpreted. A second question is which investor mechanisms cause changes in physical outcomes when other physical/economic assumptions are held fixed.

## 2. Source audit: original 20-seed reference

The original committed `docs/reference/experiment` manifest contains **20 paired seeds**, 2026–2031 model years, identical annual technology capacities and a fixed 168-hour synthetic representative block per year reweighted to 8,760h; storage cycles within the block, not between real seasons. The audit recomputes paired year-by-year and investor-by-investor fields directly from `annual.csv`, `decisions.csv`, `settlements.csv` and `summary.csv`, after rejecting changed hashes.

| Original reference indicator | Energy-only | Payment model |
|---|---:|---:|
| Mean per-seed system discounted resource NPV, GBP bn | 111.459 | 111.459 |
| Mean per-seed central-planner resource gap, GBP bn | 9.795 | 9.795 |
| Accepted build MW aggregated across 20 seeds | 600,000 | 600,000 |
| Capacity-payment transfers aggregated over 20 seeds, GBP bn | 0.000 | 229.343 |

The archived energy-only decisions include 600 investor-year-seed records: all 600 have positive model NPV scores, but only 440 request construction. The other 160 are ineligible/unrequested given model horizon and construction timing; they should **not** be interpreted as unprofitable. In this specific fixture, investors already request projects when economically and temporally able. A larger monetary reward can make positive scores higher without relaxing fixed budgets or increasing requests.

## 3. Registered MX01: five controlled synthetic mechanism variants

The [MX01 register](INVESTOR_MECHANISM_STUDY_MX01.md) was committed before the new experiment was executed. Every case uses an identical physical system and planner, the same 12 seeds 401–412, two payment regimes (0 and 75 GBP/kW-year), the same six annual model years, synthetic weighted hours, and unchanged machinery. No case uses observed historical GB investor parameters.

| Mechanism variant | Mean resource NPV (£bn) | Mean planner gap (£bn) | Accepted new MW per seed | Six-year unserved MWh per seed | Mean transfer per seed (£bn) | Payment treatment changed resource cost in 12 pairs? |
|---|---:|---:|---:|---:|---:|---|
| Baseline | 111.459 | 9.795 | 30,000 | 6,726,484 | 11.467 | **No (0/12)** |
| Investor budgets 20% | 413.447 | 311.784 | 5,000 | 70,030,031 | 9.062 | **No (0/12)** |
| Investor budgets zero | 579.496 | 477.832 | 0 | 105,734,520 | 8.627 | **No (0/12)** |
| Higher hurdle rates (+15 percentage points) | 111.459 | 9.795 | 30,000 | 6,726,484 | 11.467 | **No (0/12)** |
| No expectation noise | 111.459 | 9.795 | 30,000 | 6,726,484 | 11.467 | **No (0/12)** |

All 120 ABM simulation trajectories passed solver, accounting and provenance verification. [GitHub Actions MX01 run 40364326149](https://github.com/abhijith-sivaprasadan/gb-flexabm/actions/runs/40364326149) independently checks the five complete source artifacts and emits `mx01-final-crosscase-evidence`. Mean values over seeds should not be taken as forecast uncertainty; in this fixture, some outputs are **identical across all seeds**.

Budget reductions alter the resources available to investors. This can increase the central-planner gap dramatically under the model's chosen high scarcity penalty, **even when the policy treatment has no effect**. Those gaps are not estimates of GB welfare losses, lost load or expected unserved energy. The fixed-budget-zero variant is a deliberately infeasible financing control, not a plausible observed real-world baseline.

## 4. MX02: mechanism and analytical threshold

At a single investor-decision time, conditional on a fixed expected energy margin `m`, technology CAPEX `C`, fixed cost `F`, risk haircut `R`, construction years `L`, lifetime `T`, hurdle rate `h`, derating `d`, NPV threshold `H` and stylised capacity payment `p`:

```
A = Σ[t=L,...,L+T−1] (1+h)^(-t)
NPV(p) = -C + A ( m - F - R + 1000*d*p )
positive investment request iff NPV(p) > H
conditional entry price p* = max(0, ((C+H)/A - m + F + R)/(1000*d))
```

When a positive-score investor already chooses its entire budget-limited request, increasing `p` changes investment attractiveness but **not the amount**. A zero/inadequate budget cannot fund a project block at any price; neither can a project after the study horizon. With zero derating the capacity payment cannot move entry. Code-level tests of the threshold include just-above and just-below `p*`, zero budget, terminal horizon and zero derating. Because energy margin depends on endogenous dispatch prices, this is a **conditional static frontier**, not a solved dynamic transition threshold or behavioural estimate.

## 5. What remains scientifically unresolved

The [historical readiness audit](SCIENTIFIC_ADMISSION_STATUS.md) has no complete admissible APXMIDP wholesale market index year for 2013–2018 and incomplete Elexon generation-category coverage. Existing NESO historical generation mix contains publisher-applied seasonal decomposition and clipping of negative values, and its present-day revision is not necessarily a 2013 information vintage. Neither NESO processed fuel mix nor LCCC IMRP is silently interchangeable with missing Elexon settlement-level datasets. Verified 2013–2018 NESO demand ingestion does **not** mean the full historical system model is ready.

The model lacks empirical finance constraints, historical fleet and cost input vintages, proper official GB Capacity Market clearing, forecast-origin backtesting, transmission networks, endogenous closure, realistically linked seasonal storage and multi-weather-year probabilistic adequacy. The comparison to a perfect-foresight central planner is illustrative of modelling structure; it is not a measured causal inefficiency estimate.

## 6. Follow-up: minimum independent research gate

The next causal/empirical advance requires (1) lawful time-stamped source recovery for the intended price target or a **prospectively revised target definition**, (2) reconciled historical generation, fleet and real installed costs, (3) a transparent historical information set available at each scenario origin, (4) specified investor entry/construction and financing measurements, (5) an ex ante calibration and identification plan with a genuinely unused test window, (6) comparison against simple budget/threshold baselines and independent review. A further synthetic parameter sweep will not replace empirical identification.

## References and audit trail

- Repo source: `src/gb_flexabm/{simulation.py,agents.py,optimisation.py}`; original `docs/METHODS.md`, `docs/VERIFICATION.md` and `docs/reference/experiment/`.
- Cross-case source audit `scripts/summarize_investor_mechanisms.py`, `src/gb_flexabm/policy_identification.py`; cohort output in Actions artifact `mx01-final-crosscase-evidence`.
- Conditional frontier `src/gb_flexabm/investor_frontiers.py` and `tests/test_investor_frontiers.py`.
- [Elexon Insights official dataset documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint) (MID and alternative market index endpoint).
- [Elexon 2018 BMRS API guide](https://assets.elexon.co.uk/wp-content/uploads/2018/09/28160411/BMRS-API-Data-Push-User-Guide.pdf), historical MID with APXMIDP settlement date/period semantics, not proof today's API serves all archived observations.
- [NESO official historical generation mix documentation](https://www.neso.energy/data-portal/historic-generation-mix) — contains processed/revised data, so no direct original-vintage substitution.

**Disclosure:** This is an author-produced computational research note, with AI-assisted code, analysis and drafting. All numerical claims are from stored synthetic artifacts. It is not an accepted or peer-reviewed journal paper.
