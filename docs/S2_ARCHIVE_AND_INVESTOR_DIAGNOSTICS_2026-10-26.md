# GB-FlexABM — S2 archive preflight and investor-response audit (26 October 2026)

**Research engineering milestone, not a calibrated-GB results release.**
This is a source-admission and mechanistic-analysis increment after MX01, not
a prospectively registered policy experiment or a journal manuscript.

## Research question and ROI priorities

The previous MX01 sweep solved 120 synthetic investor trajectories across five
investor-only variants. No paired treatment changed accepted investment; this
must not be interpreted as a measured zero effect of the GB Capacity Market.

This increment addresses two separate bottlenecks:

1. **S2 archive preflight**: Can an authorised, original historical Elexon MID
   CSV provide a complete APXMIDP settlement-period index for a declared year?
   The existing Elexon API acquisition has **zero complete admissible years**
   across 2013–2018. Archive authenticity, rights, revisions and historical
   information availability must still be checked by a human reviewer.
2. **Mechanism explainability**: Given *archived synthetic decision and
   expectation evidence*, does the implemented NPV/budget/construction rule
   reproduce every investor's saved requests, and which economic constraints
   make a payment nonbinding? This is an **ex post diagnostic**, not a new
   hypothesis test. It does not create additional synthetic or empirical runs.

## Original MID CSV preflight

Official archived BMRS guidance lists the legacy row fields: record type
`MID`, data provider (e.g. `APXMIDP`), settlement date, settlement period,
price and volume, with an active flag in some formats. This preflight accepts
the *six-column legacy CSV* and an optional seventh active flag, and `HDR` /
`FTR` lines. It does **not** accept re-labelled modern Insights JSON or an
invented daily price index.

The `unique_only` mode rejects all duplicate target keys or inactive
records. The explicitly chosen `active_flag` mode requires Y/N on every
target-provider row, excludes N rows and rejects duplicate active rows.
Neither mode establishes a historical release-vintage contract. Every
settlement period is mapped through the Europe/London calendar rather than
assuming 48 periods per local day. The spring and autumn DST days require
46 and 50 periods, respectively. The audit rejects malformed dates,
nonfinite prices, negative volumes, duplicate active records and mismatched
legacy trailer counts. Negative prices remain valid; zero trading volume
is *not* a usable market-price target.

Example when the researcher has a legitimate, locally stored archive:

```bash
uv run --locked python scripts/audit_legacy_mid_archive.py data/raw/legacy-mid.csv \
  --year 2017 \
  --source-url "https://SOURCE-PUBLISHER.example/original.csv" \
  --licence "Publisher rights/license note — verify original terms" \
  --retrieved-at-utc "2026-10-26T19:00:00Z" \
  --revision-rule unique_only \
  --output runs/mid-2017-archive-audit.json
```

The example URL is a placeholder, **not** evidence of an accessible archive.
The original file stays local; the JSON summary contains a SHA-256 of raw
bytes, calendar coverage, known source assertions and explicit `S2_complete:
false`. A complete calendar does not yet admit a historical price target.
Do not commit unlicensed source data.

For archive admission, obtain and check (a) original publisher/rights and
file identity, (b) date/SP/active and revision vintage, (c) overlap with
existing hashed Elexon MID observations, (d) nominal price units and
volume semantics, and (e) phase-appropriate publication timing. Other S2
roles — fuel/carbon, fleet, money index, costs, policy and weather-derived
availability — remain required by the historical bundle.

## Investor response audit

```bash
uv run --locked python scripts/audit_investor_response.py \
  docs/reference/experiment --output runs/reference-investor-entry.json
```

The script first verifies the archived synthetic run and existing paired
payment identification. It then independently recomputes, for every
seed/year/investor/payment observation:

- Expected-energy-margin to NPV score under the recorded
  investor/technology rules, with construction and finite-budget limits.
- Requested MW including terminal-year suppression, and `accepted <=
  requested` checks, with technology matching and construction timing.
- The analytical zero-payment entry frontier, classifying common-expectation
  paired rows as already profitable, below payment threshold, budget blocked,
  terminal-year blocked, or threshold crossing.
- Pairs where expectations change endogenously are separated, **not**
  assigned an isolated treatment mechanism.

It is a **code consistency and attribution diagnostic**, not validation of
investor preferences, bank behaviour, auctions, historical costs, or observed
GB investment. Original MX01 results are preserved unchanged.

## Guardrails, tests and decision gate

- The archive tests use invented 2016 prices for a complete synthetic
  17,568-interval calendar, including both DST transitions, duplicates,
  inactive rows, zero volume, missing observations, provenance and
  tamper rejection. This does **not** represent an acquired 2016 archive.
- The investor-response tests compare the original committed 20-seed
  reference experiment against the live source request rule and reject
  modified/corrupt decision evidence.
- Existing 2013–2018 APXMIDP missingness remains as recorded. The
  previous 2024 data exposure remains on the draft protocol.
- No new S2 role is marked ready, no parameter lock is issued, and no
  new historical market data or external scholarly review is claimed.

### Primary source identity

- [Elexon BMRS API/Data Push User Guide, 2018](https://assets.elexon.co.uk/wp-content/uploads/2018/09/28160411/BMRS-API-Data-Push-User-Guide.pdf).
- [Elexon Insights Market Index Data (MID)](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/MID).
- [Project historical source recovery assessment](HISTORICAL_GB_SOURCE_RECOVERY_2026-10-26.md).

**Next decision:** the first authentic source-backed archive with a
complete/partial admissibility report and matching publisher licence
should be reconciled to the modern audit and submitted for source review.
Without that, no claimed fitted GB investor or price target should proceed.
