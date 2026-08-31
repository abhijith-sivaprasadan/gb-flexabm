# Training-market acquisition and the S2 decision gate

Updated 31 August 2026. **This is real source-coverage evidence, not a calibrated model or completed S2–S5 release.**

## What ran

The Elexon adapter acquired **402 bounded requests per dataset**: 67 chunks per year for 2013–2018, for both APXMIDP Market Index prices and FUELHH generation (**804 responses total**). Each request spans at most six days, staying below the price endpoint's observed seven-day inclusive limit. The draft study years are checked before network access. No 2019–2025 observations were requested.

Every response, including empty responses, is pinned locally by request identity and SHA-256. Cached responses are rehashed and reparsed. Rejected normalization retains the original source and a rejection record; it is not automatically overwritten or refetched. Public reports contain source hashes, coverage counts and defects, not raw observations or credentials:

- [Price audit](reference/training-market-mid.json)
- [Generation audit](reference/training-market-fuelhh.json)

The report's own checksum detects accidental editing, including a changed success flag. It is not independent authentication or scientific review.

## Actual wholesale-price coverage

One provider, **APXMIDP**, is selected explicitly. The API's other provider is not averaged in or used to fill gaps. Prices remain nominal GBP/MWh; volume remains MWh. Negative prices are valid. A zero-volume period is retained but fails the target-usability gate; its zero price is not treated as evidence of a zero wholesale price.

| Training year | Expected half-hours | APXMIDP rows | Missing half-hours | Additional zero-volume periods |
|---|---:|---:|---:|---:|
| 2013 | 17,520 | 0 | 17,520 | 0 |
| 2014 | 17,520 | 0 | 17,520 | 0 |
| 2015 | 17,520 | 0 | 17,520 | 0 |
| 2016 | 17,568 | 5,170 | 12,398 | 3 |
| 2017 | 17,520 | 17,186 | 334 | 15 |
| 2018 | 17,520 | 17,268 | 252 | 28 |

**No training year passes complete price coverage.** These results supersede the earlier January 1 probes. They describe the retrieved endpoint/provider snapshot, not proof that historical prices never existed. No interpolation, System Price substitution, provider switching or date-window change has been applied.

The current [official Open Settlement Data page](https://www.elexon.co.uk/bsc/data/open-settlement-data/) links MD1 archives for 2020–2026, organized by settlement-run production year rather than necessarily the delivery year. Read-only checks of plausible 2013/2018 archive URLs returned HTTP 403, which establishes neither availability nor nonexistence. The alternative MID stream documentation was discoverable but its tested API route returned 404. No restricted access was bypassed, no later-year archive observations were inspected, and no claim of a usable legacy archive is made.

## Generation is a different measurement boundary

[FUELHH](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) supplies half-hour **average MW**, not MWh. Interconnector flows retain their sign. Fuel categories remain separate; none is silently mapped to the demo's four technologies, treated as unconstrained wind/PV availability, or combined with NESO ND.

The audit found no records for 2013–2014, only one timestamp per 13 categories at the end of 2015, and incomplete later years. For the long-lived categories there are 14 missing half-hours in 2016, 9 in 2017 and 19 in 2018. BIOMASS appears partway through 2017; INTNEM appears for only 45 intervals in 2018. Absence before a category is introduced is not automatically equivalent to zero generation or to lost measurements. Category definitions and the GB boundary still need reconciliation.

Historical FUELHH responses also contain inconsistent auxiliary settlement-date/period fields at midnight and DST boundaries. The adapter retains the primary `startTime` UTC timestamp, records the discrepancy count and does **not** shift values to make the auxiliary labels agree. Counts include boundary records returned by inclusive queries and may repeat between chunks. The primary UTC grid is audited separately. This source warning must be assessed before using the series as a model target.

For FUELHH revisions, the latest supplied `publishTime` per primary timestamp/fuel category is selected; tied conflicting values fail. MID has no comparable publication field, so conflicting duplicates fail. Query-end observations are excluded using half-open UTC windows before concatenation. `hourly_market` computes arithmetic means only when both half-hours are present; MW × 0.5-hour aggregation conserves recorded energy. Missing entire hours/years and changing categories remain separate calendar gates.

## Alternative generation archive — not silently substituted

The [NESO historical generation mix archive](https://www.neso.energy/data-portal/historic-generation-mix) extends to 2009. Its metadata labels timestamps UTC, and a server-filtered 2013-01-01 probe returned 48 records. However, NESO states that it applies seasonal decomposition to missing/irregular data, clips net-negative values at zero, and includes batteries/transmission solar in OTHER. This is a publisher-processed alternative, not untouched raw metering. Its category, unit and demand-boundary reconciliation has not been completed, and it has not been installed as the calibration target.

## Required decision before fitting

The later [LCCC IMRP acquisition](PUBLIC_INPUTS.md) supplies a different hourly day-ahead reference from 30 June 2016. Native date/period keys are complete in 2017/2018, but this does not recover 2013–2015 or repair APXMIDP coverage. Timezone semantics and an explicit protocol decision are still required. No substitution was made.

The preferred next step is to obtain a legitimate, licensed legacy MID archive and reconcile overlaps against the pinned API observations. Portal/archive access has been requested from the maintainer; **never paste a password or API key into chat or public files**.

If such an archive cannot be obtained, the research protocol needs an explicit, reviewed amendment specifying which price years/intervals are evaluated, minimum monthly coverage, zero-volume treatment, missingness bias checks and which claims are withdrawn. Simply shortening training to 2017–2018 would not remove its gaps. A revised protocol must be frozen before fitting and retain the already-disclosed 2024 demand exposure. No acceptance threshold has been relaxed here.

This decision is necessary but not sufficient for S2. Historical fleet/vintages, costs, fuel/carbon, money indices, policy contracts and fleet-weighted weather conversion still need completion. S3 requires an empirical full-year dispatch study; S4 requires a historical institutional predictor, identified fitting and a parameter lock; S5 requires the locked no-fit runner, actual evaluation and independent scientific review. The existing tested helpers do not satisfy those empirical gates.

## Reproduce acquisition and audit

```sh
uv sync --locked --extra dev --extra gui --extra research
# No credentials required; explicit network operations, never run by tests or the GUI:
uv run --locked python scripts/fetch_market.py fetch --dataset mid --limit 402
uv run --locked python scripts/fetch_market.py fetch --dataset fuelhh --limit 402
# New output paths; audits reverify local source bytes and do not contact the API:
uv run --locked python scripts/fetch_market.py audit --dataset mid --output runs/market-mid-audit.json
uv run --locked python scripts/fetch_market.py audit --dataset fuelhh --output runs/market-fuelhh-audit.json
```

Use `--years` only for an explicit subset of the draft training window and `--limit` to bound a run. Run one process per dataset/output root; there is no cross-process download lock. HTTP/schema failures stop the invocation; inspect a rejected snapshot before retrying. The local GUI displays the committed, checksummed audit snapshots, not a live readiness certification. All raw publisher data retain their own terms and stay in ignored `data/raw/`.
