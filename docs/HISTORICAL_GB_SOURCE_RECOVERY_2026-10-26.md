# Historical GB empirical-data recovery — audited gate, 26 October 2026

**Status: S2 blocked; no historical source gaps are silently resolved here.**
This record is part of the research sprint but is separate from MX01/MX02,
whose numerical findings are synthetic and cannot establish GB observations.

## Primary source product hierarchy

| Role / expected observation | What is confirmed | Unresolved admission boundary | Next evidence |
|---|---|---|---|
| NESO national demand (2013–2018) | Six source-coverage years passed the previously committed completeness audit | NESO national-demand category is not total customer load and has transmission/embedded generation semantics | Freeze exact reporting definition, units, daily DST/UTC aggregation and vintage for the historical model |
| Elexon APXMIDP Market Index Data (MID) | Committed historical audit: **zero fully admissible years** of 2013–2018 market target | Some publisher-API requests succeeded but settlement-period holes prevent an untouched complete target | Obtain an authorized original **MID/APXMIDP** archive with date/period, price and volume per product; reconcile record revisions |
| Generation by fuel | Elexon FUELHH responses have incomplete historical training coverage | Must preserve fuel categories and publication vintages rather than label postprocessed NESO mix as original FUELHH | Seek dated original dataset and compare overlapping years/categories to original |
| NESO historic GB generation mix | [NESO documents a record going back to January 2009](https://www.neso.energy/data-portal/historic-generation-mix), plus seasonal-decomposition corrections and clipping of negative outputs | Current-revision publisher-processed mix is **not** raw FUELHH, nor necessarily data available at an earlier forecast origin | Pin revision/license, compare categories, missingness and publication lag; do not call it identical source |
| LCCC hourly IMRP | Native 2017 and 2018 hour/settlement-key coverage documented in archive; 2016 partial, 2013–2015 absent | IMRP is an **administrative reference price**, not an equivalent market index price | Possible **separate prospective protocol/amended estimand**, explicit reviewer approval and overlap evaluation; never automatic replacement |
| Fleet/cost/money basis | Existing public-input downloader has many documents, not admitted model-ready technology-year records | Unit basis, build/retirement vintages, installed fleet and technology CAPEX/OPEX, and 2018 GBP rebasing are not locked | Type/unit/source-level inventory with original publisher document, row provenance, official conversions and source vintage |
| ERA5 wind/solar | Exact 2013–2018 Copernicus request plan exists | Original hourly meteorology still requires artifact admissibility, atlite/fleet-weighted technology availability, measured-capacity calibration and source hashes | Acquire against user-owned CDS account, verify hourly calendars/geographical coverage, then independently check physical conversions |
| Policy/CM/CfD | Existing model contains **one stylised £75/kW/year transfer** | No real accreditation, auction, clearing, settlement, delivery, derating, capacity demand or CfD rule reconstruction | Separate institution study with historical dated auction records and phase-scoped market policy |

The [official Elexon Insights documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint) lists the MID dataset and Market Index price service. Its [historical BMRS API guide (2018)](https://assets.elexon.co.uk/wp-content/uploads/2018/09/28160411/BMRS-API-Data-Push-User-Guide.pdf) describes MID records by **Data Provider / Settlement Date / Settlement Period**, including APXMIDP, price, volume and active flag. This establishes the *correct historical product identity and fields*, not proof that an accessible contemporary endpoint provides every 2013–2018 observation. Do not substitute one-hour UTC timestamps for GB settlement-period keys without a dated DST and rule crosswalk.

## Required train/admission roles

The exact source-bundle contract in `src/gb_flexabm/study.py` demands the following nine roles in each training year: `demand`, `fleet`, `technology_costs`, `fuel_carbon`, `money_index`, `wholesale_price`, `generation`, `weather_availability` and `policy`. Each must have rights/licence, reporting boundary, units, transform, available-at-UTC source vintage and a pinned checksum before calibration.

## Decision and information-leakage rules

1. **Do not reinterpret the MX01 five-case synthetic experiment as empirical validation.** The 2026–2031 dates are internally invented scenario years, not a hindcast.
2. If a complete original target cannot be obtained, create a **new prospective protocol revision** stating the alternative target, exact units and publisher origin, revised train/holdout windows, historical overlap and consequences for claims. Old trials remain attributable to the old protocol.
3. The recorded prior inspection of 2024 demand makes that year an exposed year for this research workflow. No later evaluation may describe it as pristine simply because a new code run hides its file from training.
4. Access `StudyBundle.read` through explicit training/validation/holdout authorization. Tests are guards against accidental study leakage, not an operating-system security guarantee.
5. High-value next empirical ROI is obtaining **complete primary-price product records and contemporaneous fleet vintage**, not writing a larger synthetic agent UI or tuning a missing-data metric to pass.

**No new official historical rows or source licences were acquired or certified by this document.**
