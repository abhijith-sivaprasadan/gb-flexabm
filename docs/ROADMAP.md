# Research roadmap and release gates

The current release is a usable exploratory foundation. The larger research programme is not marked complete.

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
