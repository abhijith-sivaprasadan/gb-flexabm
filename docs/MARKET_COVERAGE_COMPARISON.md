# Original versus alternative price and generation products

The historical 2013–2018 GB study currently cannot pass its source-admission
requirements. This comparison is derived **only from previously archived
publisher-API audit records**, not new observations. Run:

```sh
python scripts/compare_product_coverage.py
python -m pytest -q tests/test_product_coverage.py
```

- Elexon APXMIDP half-hourly price target: 0 complete, usable study years.
- Elexon FUELHH fuel-category generation: 0 fully complete study years.
- LCCC IMRP native hourly administrative product: zero rows 2013–2015,
  4,441 native period rows in 2016, 8,760 each 2017 and 2018.
  **IMRP is not an interchangeable Elexon wholesale price**. Native 23/25
  period-day interpretation, original publisher vintage and price definition
  require review.
- Old acquisition audits are pinned to an earlier protocol fingerprint.
- Full fleet vintage, technology cost basis, GB demand boundary, weather-to-
  availability conversion and policy coverage also require admission.

No target has been replaced, no missing observations imputed, no new licensed
historical records obtained, and **no historical investor fit or held-out
validation has been run**. Advancing this study requires newly sourced, dated
original price and generation evidence or a separate prospective reviewed
revision of the estimand, training period and data product. The 2024 prior
data exposure remains disclosed.
