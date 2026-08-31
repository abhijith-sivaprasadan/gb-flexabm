# Public-input acquisition and extraction

Updated 31 August 2026. **Acquired references are not a normalized historical bundle. S2 remains in progress.** No paid API, trading account or subscription was used.

## Acquired evidence

The [catalogue](../studies/historical-v1/public-sources.json) identifies 177 resource URLs. The [rehashed inventory](reference/public-inputs-inventory.json) records **175 acquired and mechanically extracted files: 465,042,005 bytes (443.50 MiB)**. There are 25 CSV, 135 PDF, nine XLSX, five HTML and one JSON files. This includes the two user-supplied IMRP files; pinning their hashes is not an independent publisher identity verification.

| Input | Acquired references | Remaining interpretation/gate |
|---|---|---|
| Wholesale | LCCC IMRP actuals/dictionary: 89,064 rows, 30 June 2016–27 August 2026 | Different product from APXMIDP; no 2013–2015 data; timezone alignment and explicit target decision pending |
| Fuel | QEP 3.2.1: all eight sheets, nominal and publisher-deflated prices | Quarterly/annual purchase-price proxies, thermal units, suppressed cells and tax notes; do not deflate an already-real series twice |
| Carbon | **114 unique common-platform/UK auction PDFs** linked for 2013–2020, UK carbon-market reports covering 2021–2024, HMRC CPS tables | EUA versus aviation/futures prices; daily coverage and third-party rights; 2025 UK ETS gap. CPS Table 3 is not main Climate Change Levy Table 1 |
| Costs | 19 reports/annexes including 2013/2016/2020/2023/2025 editions and renewable, thermal, storage and hurdle-rate assumptions | Technology/units/money-base mapping and publication vintage; an edition named 2025 can be published in 2026 |
| Money | ONS D7BT CPI and daily ECB GBP-per-EUR rates requested for 2013–2025 | Index choice, scheme-specific indexation, currency/calendar alignment; no invented weekend FX observations |
| Fleet | REPD July 2026: 14,657 data rows, 53 columns | Historical DUKES reconciliation, small embedded installations, commissioning/retirement and GB/NI boundary |
| Capacity Market | All eight NESO register CSVs; LCCC obligation/payment CSV/dictionary | Asset/auction/delivery-year matching, eligibility and de-rating; change logs are not automatically historical information snapshots |
| CfD | Portfolio status (610 data rows), actual generation/payments, BMU mapping, auction outcomes/parameters/dictionaries, 304 administrative-strike-price API records | Executed contracts, indexed strikes/start dates, eligibility and settlement rules; portfolio/auction tables are not the full legal register |
| Legacy support | RO aggregate archive 2006–March 2018, 2018–19 report, 2024–25 report/dataset and buy-out history; FIT 2025 tariff workbook and 2024–25 report/dataset | Plant-level accreditation and historical tariff/banding/recycling rules. RO archive is aggregated, not an asset register; buy-out price is not observed ROC market price |

## IMRP findings

Native columns are `IMRP_Date`, `Settlement_Period`, `IMRP_Amount`. Periods are **hourly**, not Elexon's half-hours. The dictionary does not establish the UTC conversion contract, so native labels remain unchanged.

| Training year | Rows | Absent dates | Native period findings |
|---|---:|---:|---|
| 2013 | 0 | 365 | No records |
| 2014 | 0 | 365 | No records |
| 2015 | 0 | 365 | No records |
| 2016 | 4,441 | 181 | Starts 30 June; one 25-period day |
| 2017 | 8,760 | 0 | 363 × 24, one × 23 and one × 25; contiguous keys |
| 2018 | 8,760 | 0 | Same native calendar pattern; contiguous keys |

No duplicate native keys occur in the supplied file, and no non-finite/nonnumeric training prices were found. Later years were counted structurally; price numeric QA is training-only. **IMRP has not replaced APXMIDP, repaired its failed coverage gate or changed study windows.** See the preserved [market audit](MARKET_DATA.md).

## Local files and safeguards

- Originals: ignored `data/raw/public-inputs/<id>/<sha256>/`. Cached bytes are rehashed; changed files create new snapshots. No originals were deleted or overwritten.
- Current extraction: ignored `data/processed/public-inputs-v2/<id>/<sha256>/`. Earlier diagnostic extractions remain local but are not the current evidence.
- XLSX: row/cell-addressed JSONL with OOXML types, cached values, style indices and formulas/shared-formula attributes. Styles, merged headings and dates are not semantically resolved; formulas are not recalculated.
- CSV: strings and quoted newlines retained. REPD uses Windows-1252. The 291 MB NESO pre-aggregation history has 1,918,503 data rows and uses streaming row-indexed JSONL. Public CM contact details remain local, not in published evidence.
- PDF: page-indexed text across **3,688 pages**, not a certified numeric-table database. Blank/image pages are counted. Plain extraction retains rotated text omitted by the initial layout pass. Sample visual checks covered the October 2018 UK auction table and a near-blank common-platform page; this is not an all-page certification.
- HTML: cell text and span attributes retained. Mechanical extraction applies no tax, energy, inflation or currency conversion.
- HTTPS-only reviewed hosts and observed storage redirects; no credentials/cookies. Signed redirect query strings are not saved. Default file cap: 100 MB; inspected NESO history: explicit 300 MB cap. Rate limits stop a run; resume after cooldown. Run one process per output root.
- Publisher files and observations are **not committed**. Code is MIT; source terms and third-party exceptions remain separate. Carbon/consultant-report redistribution rights still require review.

## Access exceptions

The two administrative-strike-price CSV links returned 403. LCCC's openly licensed public datastore supplied **304/304 records and field definitions** instead; this JSON is separately identified, not reported as a successful CSV. The full CfD register page also returned 403: the accessible OGL portfolio/auction data do not replace all contract details.

European Commission rate limits were respected; all 114 selected reports were acquired after a cooldown. An initially downloaded pre-2007 ROC XLS remains ignored locally, outside the active catalogue/inventory. No paid source was substituted. Existing ERA5 jobs were not restarted; weather-to-power conversion is still pending.

## Reproduce

From the repository root, using new report paths:

```sh
uv sync --locked --extra dev --extra gui --extra research
uv run --locked python scripts/collect_public_inputs.py fetch --report runs/public-download.json
uv run --locked --extra research python scripts/extract_public_inputs.py --report runs/public-extraction.json
uv run --locked python scripts/audit_public_inputs.py --report runs/public-inventory.json
```

Fetch supports `--ids` for comma-separated subsets and `--imrp PATH --definitions PATH` for supplied copies. Fetch failures record inaccessible URLs, not proof of absent historical observations. Extraction success only describes the mechanical operation. Inventory always reports `model_ready: false`; exit status is not an S2 acceptance gate.

## Exposure and next work

Mechanical extraction includes post-training observations and current revisions. Do not claim an untouched holdout. IMRP numeric QA is training-only; no fitting, model-input installation, source substitution or split change occurred. Earlier 2024 demand exposure remains disclosed.

Next S2 work: semantic units/money/vintage normalization, historical GB fleet and support eligibility, fleet-weighted weather conversion, and an explicit price-target decision. S3–S5 empirical work must wait for those gates.
