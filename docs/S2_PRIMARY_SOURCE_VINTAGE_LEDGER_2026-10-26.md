# S2 primary-source vintage and recovery ledger — 26 October 2026

**Admission decision: blocked.** This ledger records discovery, not acquisition, numeric extraction, permission to redistribute or historical model-input certification. None of the sources below closes S2 by itself. Existing raw public-inputs inventory remains authoritative about previously downloaded material.

## Market-index product: Elexon APXMIDP

- Required estimand: original half-hourly **MID / APXMIDP** prices and volumes keyed by GB settlement date and period, 2013–2018; active flag/revision rules must be declared. Do not silently substitute LCCC hourly IMRP, a day-ahead auction price, national imbalance price, or another MID provider.
- Elexon legacy BMRS guide: https://assets.elexon.co.uk/wp-content/uploads/2018/09/28160411/BMRS-API-Data-Push-User-Guide.pdf (MID schema/product identity, **not** archived data completeness).
- Current Insights API documentation: https://bmrs.elexon.co.uk/api-documentation/endpoint (discover access paths, but a successful HTTP request is not evidence of full coverage).
- Elexon Open Settlement Data MD1 publication page: https://www.elexon.co.uk/open-settlement-data/ ; MD1 files are a **different publication family** and must not be declared the original market index target.
- Previously committed observation: no complete APXMIDP training year via API, 2013–2018. A local legacy archive auditor now exists (`scripts/audit_legacy_mid_archive.py`), **but no authentic archive has been newly supplied or run through it**.
- Recovery request prepared as a user-reviewable Gmail draft to Elexon Insights Support on 2026-10-26. It asks for original export access, completeness/revisions, settlement-period semantics, rights and timestamps. **Not sent**; a pending request is not acquired data. If confirmed, download via authorised path, hash originals, compare overlapping API settlement keys, run `audit_legacy_mid_archive.py`, and retain its fail-closed verdict. Do not bypass restrictions.

## Historical fleet boundary: backcasts versus contemporaneous releases

| Candidate | Publisher page | Publication/vintage consideration | Proposed use; blocking checks |
|---|---|---|---|
| DUKES 2018 tables | https://www.gov.uk/government/statistics/digest-of-uk-energy-statistics-dukes-2018 | Government statistical edition published in July **2018**; contains historical series but is **not** contemporaneous to 2013–2017 | Independently cross-check retrospective capacity/generation and unit definitions; not an as-of-2013 plant inventory |
| DUKES 2019 tables | https://www.gov.uk/government/statistics/digest-of-uk-energy-statistics-dukes-2019 | Published July **2019**; hindsight for earlier investor decisions | Validation / revised fleet comparison only, subject to exact worksheet and UK-versus-GB geographical boundary |
| REPD July 2026 CSV | https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract | Already inventoried in `studies/historical-v1/public-sources.json`; **2026 snapshot** | Useful plant planning / commissioning cross-check, but cannot supply contemporaneous 2013–2018 active-fleet and retirement records alone |
| Historical power-station registers | DUKES and dated Ofgem / regulator plant listings to be established | Earliest observed publication, asset name/version, tech, MW, commissioning and retirement dates not yet reconciled | Build plant crosswalk with boundary GB (exclude NI), de-duplication and uncertainty log, **do not** set a fleet-admitted flag until audited |

## Generation-cost basis: edition is not enough

| Candidate | Publisher page | Edition / availability caveat | Needed before model admission |
|---|---|---|---|
| DECC electricity generation costs (2013) | https://www.gov.uk/government/publications/decc-electricity-generation-costs-2013 | 2013 published estimates, not actual realized commissioning cost | Report/table/page, technology, GBP price base, CAPEX/OPEX unit, build year, assumed size, discount/WACC basis |
| BEIS electricity generation costs (November 2016) | https://www.gov.uk/government/publications/beis-electricity-generation-costs-november-2016 | **2016 report**, but linked Excel annexes were uploaded in **May 2019**; annex file's publication timestamp must not be backdated without proof same numerical information was published in 2016 | Pair actual 2016 report pages to later annex rows, mark each cell `as_of_unknown` until established |
| BEIS generation costs 2020 | https://www.gov.uk/government/publications/beis-electricity-generation-costs-2020 | Later revised outlook | Historical sensitivity / retrospective comparison only, not an investor information state in 2016 |

Already-catalogued supporting studies include PB 2013 renewable/non-renewable technology assumptions, Arup 2016 renewables, Leigh Fisher/Jacobs 2016 thermal, and NERA 2015 hurdle rates. Their source bytes and mechanically extracted texts were inventoried earlier. **No line-level costs or asset capacities are estimated, fitted or asserted in this ledger.**

## Source-row admissibility contract

For every prospective normalized observation require at minimum:

1. `source_id`, publisher URL, literal edition, immutable original SHA-256, source licence and access conditions.
2. `publisher_released_at_utc` / `available_at_utc` (or explicit `unknown`), download time and revision identity; *model year* never substitutes for *available-at*.
3. Original source file/sheet/page/row/cell, technology/plant identifier and input variable.
4. Literal raw value, unit and price base, annualization/deflation/currency methodology, geographic boundary, assumptions and transformation code version.
5. An adjudicated `reference_only | eligible_for_candidate_bundle | rejected` state, and reasons; no automatic promotion when a row parses.

**S2 status: blocked.** Next actionable dependencies are the original APXMIDP archive and a dated plant/year fleet crosswalk, followed by explicit cost-row mappings and independent verification. No synthetic parameter has been mistaken for an empirical GB estimate.
