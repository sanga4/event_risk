# Official NY Fed full-history reference-rate source QA

## Live base facts, October 25, 2026 UTC

The source-controlled and Flight-executed NY Fed v1.1 importer retrieved **2,138 distinct SOFR effective dates** and **2,150 distinct EFFR effective dates** from April 2, 2018 through October 22, 2026. It appended **4,288** original issuer rate observations to the prior **500** observations captured via the last-250 endpoint, giving **4,788 raw versioned rows** but just **4,288 distinct (series,effectiveDate) combinations**. It computed **4,286** descriptive consecutive-rate changes in basis points.

A second run against the identical response hashes produced **zero newly inserted original rate rows and zero new raw payload hashes**. Both 250-date overlaps match the newly retrieved official rate *levels* exactly; this is an agreement between two retrievals of the issuer's currently accessible history, **not proof of independently attested as-published historical vintages**.

## Why the quality-control and latest-history view are needed

A naïve `COUNT(*)`, return calculation or factor-beta regression from `lab_nyfed_rate_observations_retro_v1` would double-count the overlapping 250 dates per series. The new source-controlled `lab/phase1_nyfed_rate_source_quality.py` materializes a read-only **`lab_nyfed_rate_levels_latest_retro_v1`** view with exactly one latest *warehouse-retrieved* record per series/effective date and intact original JSON SHA-256, source response receive time and upstream FALSE licensing/PIT flags.

The audit also creates append-only `lab_nyfed_rate_source_quality_builds_v1` and two per-series rows per run in `lab_nyfed_rate_source_quality_series_v1`. A source-data-first validation requires each series to have ≥1,500 unique effective dates from no later than 2018, correct source identity without duplicate (series,date,source JSON hash), no original publisher-time or redistribution/reuse approval claims, finite plausible native annualized rate percentages and no future effective days. Overlapping retrieved levels that disagree would be listed as candidates for review, **not used to silently rewrite earlier raw archives**.

## Funding market tail behavior, not policy-factor surprises

The loaded native source contains an unusually large SOFR jump of **+282 bps on September 17, 2019**, followed by **−270 bps on September 18, 2019**. These are *overnight funding-rate level changes*, not identified Federal Reserve policy surprise shocks, default events or evidence that a named event caused bond/credit beta repricing. The quality audit retains and counts daily rate changes whose absolute value reaches 50 bps without automatically deleting real tail events. The 2019 spike is meaningful for funding-market stress diagnostics and robust beta sensitivity studies, but an institution would require original release-time clocks, a time-aligned market risk response, model identification and source rights before treating it as a tradable event-driven factor.

No original provider publication or independent revision clocks, externally redistributable license, causal event mapping or production-rate beta approval is created by these technical checks. New source families remain missing, FRED key requirements unchanged and formal institutional release remains blocked.
