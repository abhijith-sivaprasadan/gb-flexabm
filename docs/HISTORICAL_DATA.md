# Historical data acquisition — software v0.3

This is the S2–S5 **electricity** data checklist, not an instruction to download every ERA5 field. S6's heat, hydrogen, networks and hydrology need separate scope and validation. The model is still exploratory and synthetic; the complete historical bundle is not ready.

## Exact ERA5 selection

Use [ERA5 hourly single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download), **Reanalysis only**, hourly timestamps, 0.25° grid, and area **north 61, west −12, south 49, east 4**. This is a working bounding box covering GB and nearby offshore locations, not a GB jurisdiction polygon. Check all historical fleet locations against it before conversion; remove neighbouring countries by fleet/region masks, not by assuming every cell is GB.

| Group | CDS variable names | Frequency/purpose |
|---|---|---|
| Wind | `100m_u_component_of_wind`, `100m_v_component_of_wind`, `10m_u_component_of_wind`, `10m_v_component_of_wind`, `forecast_surface_roughness` | Hourly; hub-height wind/shear and roughness |
| Solar | `surface_solar_radiation_downwards`, `surface_net_solar_radiation`, `total_sky_direct_solar_radiation_at_surface`, `toa_incident_solar_radiation` | Hourly; direct/diffuse radiation and albedo inputs |
| Temperature | `2m_temperature`, `2m_dewpoint_temperature`, `soil_temperature_level_4` | Hourly; the standard atlite temperature bundle. Dewpoint/soil are compatibility extras, not new heat/soil model claims |
| Static | `geopotential`, `land_sea_mask` | One timestamp; terrain/land-sea context, not monthly repeated downloads |

Selection was checked against the [official atlite ERA5 adapter](https://github.com/PyPSA/atlite/blob/master/atlite/datasets/era5.py) on 31 August 2026. The conversion package/configuration must still be pinned and validated; downloading these inputs does not make this repo an atlite implementation.

The committed [plan](../studies/historical-v1/era5-plan.json) contains **72 monthly training requests (2013–2018) plus one static request**. Each monthly job has 12 variables, one year/month, valid calendar days and all 24 hours: at most 8,928 variable-hour fields. The 121,000 limit reported by CDS when configuring this study is a request-selection limit, not a byte estimate or guaranteed permanent quota. Geographic subsetting reduces bytes; month/variable selection also bounds field count. Do not drop hours to make a request smaller.

At this grid there are 3,185 cells. A 31-day month with 12 float32 fields is approximately **114 MB uncompressed array values**, before metadata, archive/extracted duplicates or server packing/compression. Six years are about 8 GB of float32 values; allow **at least 25 GB free** for raw ZIPs, extracted NetCDFs and processing. This is a planning estimate, not a measured download size.

## Run and resume

From the cloned repository:

```sh
uv sync --locked --extra dev --extra gui --extra research
# First bounded run (the plan is already committed):
uv run --locked --extra research python scripts/fetch_era5.py fetch --ids static,2013-01 --limit 2
# Entire training plan, reusing verified snapshots and saved remote job IDs:
uv run --locked --extra research python scripts/fetch_era5.py fetch --limit 73
```

Enter the personal token at the hidden terminal prompt. The downloader fixes the official CDS URL, never accepts a token as a command-line flag, and does not read/write `.cdsapirc` or repository credentials. Accept dataset terms manually on CDS first; see the [official API setup](https://cds.climate.copernicus.eu/how-to-api). Never paste credentials into issues, notebooks, README files or public logs. Rotate any token previously shared in chat.

Requests run sequentially. The default wait is 180 seconds per queued job; exit **3** means pending, **2** means an acquisition failure, and **0** means the selected jobs verified. Rerun the same command to resume. `--max-wait-seconds 3600` allows a longer server wait. A job ID is saved before polling; credentials and signed download URLs are not saved. If submission itself fails ambiguously before returning an ID, check **Your requests** on CDS before retrying. Failed/expired jobs need explicit review, not silent resubmission. Run only one acquisition process against a raw-output root at a time.

Acquired ZIPs and flat NetCDF members remain under ignored `data/raw/era5/`. New attempts do not overwrite earlier snapshots. Verification checks file hashes, requested variables, exact units, every expected timestamp, grid coordinates and finite values. Soil values may be masked over sea; the missing count is reported, never filled. ZIP paths and inflated-size limits are checked before extraction. Cached files are rechecked, not trusted because a success marker exists.

The public plan has no credentials, job IDs or raw data. `scripts/check_cds_access.py` is a separate two-hour, tiny-area access probe, not a historical dataset.

Check local progress without credentials using `uv run --locked --extra research python scripts/fetch_era5.py status`. Add `--report NEW_PATH.json` to write a public-safe, timestamped inventory. It verifies available snapshots and distinguishes saved submissions from confirmed local downloads; it does not poll remote job state. The [initial acquisition evidence](reference/era5-acquisition-status.json) records the static fields and first complete month, not all 73 jobs.

### What raw weather does not solve

Radiation is retained in **J/m² at ERA5 validity timestamps**, while temperature is K and wind is m/s. Accumulation interval alignment, J/m²-to-W/m² conversion, solar geometry, turbine curves, hub heights, PV orientation/temperature losses, fleet locations/capacity weights and offshore/onshore separation still require explicit tests. Do not substitute observed wind/solar generation for unconstrained availability or mistake raw weather for capacity factors.

No 2019–2025 observations are requested by this training plan. The [study protocol](../studies/historical-v1/protocol.json) is still **draft**, not preregistered. The previous 2024 NESO demand inspection remains disclosed.

## Everything else needed for the historical bundle

| Input / target | Primary source | Required treatment / current gap |
|---|---|---|
| Half-hour demand | [NESO Historic Demand](https://www.neso.energy/data-portal/historic-demand-data) | Training 2013–2018 acquired and complete-year checked. ND is not total end-use demand; reconcile pumping, exports and embedded generation |
| Generation by technology | [Elexon FUELHH](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) | 402 training responses acquired/audited. Half-hour mean MW; coverage gaps, auxiliary time-label defects and changing categories remain unresolved. See [findings](MARKET_DATA.md) |
| Wholesale price target | [Elexon Market Index](https://bmrs.elexon.co.uk/api-documentation/endpoint/balancing/pricing/market-index) | 402 training responses acquired/audited for APXMIDP; no complete training price year. An archive or explicit protocol amendment is needed. Not imbalance prices; no gap filling |
| Fleet, technology capacities and vintages | [DESNZ DUKES electricity tables](https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes), [REPD](https://www.gov.uk/government/publications/renewable-energy-planning-database-monthly-extract) | Commission/retirement dates, geography, plant technology, embedded generation and capacity reconciliation. UK totals/current station lists are not a historical GB fleet |
| CAPEX, fixed/variable O&M, efficiency and lifetime | [DESNZ electricity generation costs](https://www.gov.uk/government/collections/electricity-generation-costs) | Pin publication vintages, money basis and technology mapping; current estimates are not information available to a historical investor |
| Fuel and carbon prices | [DESNZ power-producer fuel prices](https://www.gov.uk/government/statistical-data-sets/prices-of-fuels-purchased-by-major-power-producers), applicable historical EU/UK ETS and Carbon Price Support sources | Explicit thermal/electric energy units, efficiency, tax/policy regimes and timestamps. UK fuel-price proxies must be labelled; carbon series/rights still need selection |
| Inflation and currency | [ONS CPI series](https://www.ons.gov.uk/economy/inflationandpriceindices) | Explicit index and 2025 GBP base, nominal-to-real transformation; exchange rates where needed. No invented index values |
| CM and CfD contracts, obligations and settlements | [LCCC/ESC data portal](https://dp.lowcarboncontracts.uk/dataset/) and official CM registers/auction publications | Delivery years, contracted/de-rated MW, eligibility, indexed strikes/reference prices and negative-price provisions. Aggregate auction obligations are not asset contracts |
| Legacy renewables support | Official Renewables Obligation records/rules | Represent support or lock legacy assets exogenous. Do not fit behavioural preferences to compensate for omitted support |
| Imports/exports, pumped storage and boundary reconciliation | NESO/Elexon and relevant DESNZ tables | Specify whether interconnectors/storage are modelled or exogenous, align metering boundaries and avoid double counting |

Each normalized role needs year-specific tables, source/processed SHA-256, source URL/licence, units, boundary, transformation and publication-availability timestamp. Publisher data retain their terms; this code's MIT licence does not relicense them. NESO demand and Elexon response snapshots are acquired, but they are not a complete reconciled historical bundle. Elexon retrieval dates are not proof that the current revisions were available at historical forecast origins.

## Study utilities and remaining stage gates

`StudyBundle.read` checks the split before opening observation bytes, rejects wrong-year tables/checksum/path errors and checks source vintages in forecast-origin mode. A metadata inventory is explicitly **not** an observation-verification or readiness certificate. Python callbacks/filesystem access are not sandboxed; these guards prevent accidental leakage, not malicious bypass. Table-unit labels still require source-specific semantic validation.

`diagnostics.dispatch_reduction` uses exogenous demand/availability k-medoids, retains extreme days and reports demand, generation, cost, scarcity and storage-throughput errors against a linked full chronology. Representative days reset storage to half full; they are not certified seasonal-storage approximations. Current tests are authored fixtures, not historical S3 evidence.

`fit_capacity_grid` requires frozen candidate sets/common seeds/categories and all training roles, records every success/failure, and reports sensitivity. It uses a supplied predictor; a validated historical institutional predictor is **not implemented**. It does not issue a scientific parameter lock. CM/CfD helpers only calculate transfers on already-eligible inputs; they do not model contracts, auctions or investor incentives.

Capacity/price errors, fixed-ensemble mean convergence and training-only persistence/trend baseline metrics are implemented with zero-denominator handling. A locked no-fit evaluation runner, origin-vintage audit, historical convergence evidence and independent scientific review remain **pending**. S2–S5 are not complete.
