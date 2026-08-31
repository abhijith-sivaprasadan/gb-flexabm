# Methods and accounting

## Historical-study utilities (v0.3)

The synthetic physical/agent engine below is unchanged. Separate study tools implement phase-before-file access, immutable protocol/bundle identities, source-vintage checks, exogenous k-medoids with retained extremes, linked-chronology versus independent-day dispatch errors, common-seed grid-trial records and evaluation metrics. Their assumptions and pending historical integration are specified in [HISTORICAL_DATA.md](HISTORICAL_DATA.md). Representative-day storage resets are explicit; transfer helpers do not implement policy eligibility. No fitted model, parameter lock or empirical S3–S5 pass is claimed.

## One physical contract

`optimisation._block` builds both dispatch and planner operating constraints. For technology k and period t, generation is nonnegative and bounded by available capacity `a[k,t] * K[k]`. Energy balance in MW is:

```text
sum(generation) + discharge - charge + unserved = demand
0 <= unserved <= demand
SOC[t+1] = SOC[t] + dt[t] * (eta_charge * charge - discharge / eta_discharge)
0 <= SOC <= storage_energy; 0 <= charge, discharge <= storage_power
SOC[0] = SOC[last] = storage_energy / 2
```

SOC uses physical duration, not repetition weight. Operating cost weights are `dt * occurrences`; uniform occurrences are required within the single cyclic block. Both charging and discharging incur a small configured throughput cost. There is no binary mutual-exclusion constraint; simultaneous operation is not categorically prohibited. Nonnegative generation costs and positive throughput cost discourage it in the default fixture. Seasonal storage and representative-period transitions are not represented.

Operating resource cost is weighted generation variable cost, plus VOLL times unserved energy, plus storage throughput cost. Fixed O&M is charged to active generation capacity. Solver optimal termination is required before extracting solutions. Single-threaded HiGHS uses explicit random seed and 1e-7 primal/dual tolerances. Post-solve balance/capacity tolerance is 1e-5; costs are independently reconstructed within rtol 1e-8 and small absolute tolerances.

Dispatch price is the energy-balance dual **divided by dt × occurrences**, in GBP/MWh. The planner's intertemporal duals are not presented as wholesale prices. Scarcity hours sum weights where unserved MW exceeds 1e-5; no probabilistic LOLE is computed.

## Planning and timing

Initial asset investment costs are sunk and excluded. Initial assets are active for `commission_year <= year < retirement_year`. New investment is decided and paid at year-end, commissioned after the technology's integer construction lag, and retired after its lifetime. No new project may commission after the study horizon.

With y0 the first year, N the horizon length, r the social discount rate, C capital cost per MW, L lifetime and c commissioning year, the net capital coefficient for a decision in y is:

```text
C * [(1+r)^-(y-y0+1) - (remaining_life/L) * (1+r)^-N]
remaining_life = max(0, L - (last_year-c+1))
```

Annual variable resource costs and fixed O&M are discounted to the beginning of y0 using exponent `year-y0+1`. Terminal value is straight-line remaining-life salvage, a modelling assumption rather than a forecast sale price. The central planner optimises continuous additions, subject to the same per-technology annual build ceilings, physical equations, retirements, horizon and cost assumptions as the agents. Fixed storage is common and its sunk capital cost is excluded from both.

## Investor loop

For each completed year: activate/retire vintages → dispatch → settle revenues → update expectations → submit simultaneous investment requests → pro-rata allocate available build capacity → record future vintages.

An investor observes the opportunity margin of 1 MW of its technology, using the completed year's price, availability and weights. Expectations blend this observation and the previous expectation, plus normally distributed noise scaled by the observation magnitude. Named SHA-256-derived NumPy substreams keyed by master seed, investor and year prevent unrelated draws or iteration order from changing random paths. There is no look-ahead to future dispatch or planner solutions.

Net expected annual margin adds the stylised payment and subtracts fixed O&M and a risk haircut `risk_aversion × noise_fraction × abs(expected_margin)`. This is a transparent heuristic, **not CVaR or estimated investor utility**. Lifetime NPV discounts the constant expected margin using the investor's hurdle rate, from commissioning onward, less up-front capex. Positive NPV above the configured threshold requests affordable project blocks. Per-investor annual budgets are exogenous, not cash/balance-sheet evolution. Zero-capex technologies are dispatchable/plannable but do not receive agent investment in this release.

When aggregate requests exceed a technology ceiling, each is scaled pro rata. Accepted amounts can be fractional MW and need not preserve the requested project block size. Existing assets settle pro rata within their technology. Storage revenue is not allocated to generation investors.

## Market treatment and paired comparison

Energy-only has no capacity payment. The comparison pays active derated generation capacity a fixed illustrative GBP/kW/year amount: `MW × derating × rate × 1000`. This is **not an auction, accreditation model or official GB institutional rule**. Payments include eligible legacy capacity as well as agent builds and are recorded as transfers separately from resource costs.

The same seed is used on both sides of each pair. Endogenous prices and noise magnitudes may diverge; paired identity does not imply identical realised monetary errors. The planner has no investor budget or expectation constraint and is a relaxation of the ABM's feasible build paths. Every demo asserts its optimum is no greater than realised ABM resource cost under common accounting.
