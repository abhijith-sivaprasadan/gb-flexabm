# Data contracts and source register

## Synthetic experiment

The complete input is `src/gb_flexabm/fixtures/demo.yaml`. Its source statement identifies all parameters as authored demonstration assumptions. Demand, wind and solar are deterministic sinusoidal profiles (`schema.synthetic_periods`), not historical GB observations or fitted weather series. Default demand growth is an assumption; 8760 annual weight is a synthetic non-leap-year normalisation, not a claim about the actual calendar years.

Generation, demand and storage power are MW; energy is MWh; capital is GBP/MW; fixed O&M is GBP/MW/year; variable cost and VOLL are GBP/MWh; capacity payment is GBP/kW/year; emissions are tonnes/MWh. `energy_to_power_mw` requires duration explicitly. `constant_money` requires user-supplied source and target indices; the project does not silently invent CPI or currency data.

## Optional NESO adapter

The adapter discovers the exact annual resource from official metadata and stores an immutable SHA-256-named copy with metadata and a manifest. It retains original settlement labels and maps half-hour settlement periods to UTC using Europe/London midnight boundaries: 46 at spring DST, 50 at autumn DST and 48 normally. Duplicate and missing internal intervals, fractional periods, missing fields, negative/nonfinite ND and unsupported date formats fail rather than being imputed.

The boundary is NESO **National Demand (ND)**, not total end-use electricity demand. Its exclusions include specified station load, storage pumping and interconnector exports. Inspect publisher documentation before combining it with generation or pricing series.

Software v0.2 adds an explicit whole-year gate: `gbflex data validate --manifest PATH --year YEAR` requires every ordered half-hour from 1 January 00:00 UTC through the next 1 January (exclusive). GB calendar-year boundaries fall in GMT; settlement conversion still uses Europe/London DST. Expected duration is 8,760 hours in common years and 8,784 in leap years. Missing leading/trailing days, gaps, duplicates, wrong-year data or reordered timestamps fail. Acquisition declares its requested year and applies this gate automatically, including when reusing cached bytes. A partial current-year dataset therefore cannot pass annual validation; no imputation occurs. Rejected acquired bytes/metadata remain for diagnosis, with failed coverage recorded.

Older manifests without `calendar_year` remain compatible with basic integrity checks; pass `--year` to enforce annual coverage. Revalidation recomputes coverage from raw data, not the stored coverage summary, and checks recorded row/duration totals. Calendar completeness does not establish accuracy, product comparability or representativeness.

The 2024 file has already been inspected for ingestion/annual totals. Record that prior exposure when defining training/validation/holdout windows; no untouched holdout or frozen access protocol is claimed. Historical fleet, prices, fuel/carbon, costs and availability are still needed for S2.

Raw acquisition and metadata stay in ignored `data/raw/`; they are not relicensed as MIT. The manifest preserves upstream licence metadata. Network failures or publisher schema changes are explicit errors, not a reason to use synthetic data without labelling it.

## Primary sources inspected during implementation (30 August 2026)

The official download redirects to a specific NESO Cloudflare R2 object-store account. The adapter allows only that observed HTTPS host and resource-path prefix, checking redirects before following them. Temporary signed URLs are not retained. A changed hosting arrangement requires review rather than a wildcard allowlist.

- [NESO Historic Demand Data](https://www.neso.energy/data-portal/historic-demand-data): dataset definitions and resource discovery.
- [Official NESO metadata endpoint](https://api.neso.energy/api/3/action/datapackage_show?id=historic-demand-data): annual resource IDs, download URLs, update and licence metadata.
- [NESO Open Licence](https://www.neso.energy/data-portal/ngeso-open-licence): publisher terms; check these before redistribution or derived publication.
- [Pyomo solver recipes](https://pyomo.readthedocs.io/en/stable/howto/solver_recipes.html): optimal termination and explicit solution loading.

Elexon wholesale Market Index data, DUKES fleet data and ERA5-derived availability are **planned, not fetched or used**. Do not substitute imbalance System Prices for a wholesale-price calibration target. Such integration needs documented product/units, licences, time alignment and independent holdout validation.
