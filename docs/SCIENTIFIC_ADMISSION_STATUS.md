# Historical research admission: source-derived negative result

The GB investor/central-planner model is a valid **synthetic exploratory**
comparison, not yet an empirically calibrated explanation of GB investment
outcomes. The new audit explicitly reports this negative research-readiness
result from committed records, without opening model data or using future-year
observations.

```bash
python scripts/audit_historical_readiness.py --output runs/historical_readiness.json
python -m pytest -q tests/test_historical_readiness.py
```

The evidence screened is:

- the **draft** protocol with training 2013–2018 and already-disclosed exposure
  to some later years;
- the independently source-audited complete 2013–2018 NESO daily/hourly demand
  coverage (not the entire consumer-demand boundary);
- the per-year Elexon market-index APXMIDP target with incomplete or absent
  historical coverage; and
- incomplete historical FUELHH fuel-type generation and a large public-source
  acquisition inventory that explicitly says `model_ready: false`.

The script checks the year windows, checks report fingerprints against the
current protocol and recalculates the readiness counts from the **per-year**
records. The fact that source archives were acquired, or that synthetic agent
runs solve, must not be used to bypass a missing price target, missing fleet
vintages, missing technology costs, incomplete generation coverage or
conversion of raw ERA5 weather into capacity availability.

The next scientific milestone is a complete, original-vintage, documented
training bundle with one source/boundary/units/release date and a fail-closed
time split for each input role. A replacement wholesale-price target requires
an *explicit prospective protocol amendment* and new independent-source
checks, not arbitrary gap filling or a relabelled Elexon dataset. Only then
can investor calibration and blind validation honestly proceed. The audit
does not claim a peer-reviewed empirical result, clean holdout, calibrated
agent behaviour, measured policy effect or source authorization.

This report is repeatable directly from committed JSON source-audit records
and intentionally cannot return `READY_FOR_HISTORICAL_CALIBRATION`.
