# EventRisk Phase I — Security source exceptions and beta sensitivity

Date: October 24, 2026. **Internal historical research only.** Companion to the Institutional Factor and Beta Methodology and Data Dictionary. No security source prices or rates were altered.

## Materialized exception records

The source-controlled pipeline is lab/phase1_price_exception_audit.py. MotherDuck Flight: eventrisk-factor-lab-security-price-exception-beta-sensitivity. The first successful build created:

| New database table | Records | Meaning |
|---|---:|---|
| lab_security_price_exception_cases_v1 | 12 | Security/day returns with abs(daily log-return) >0.25 |
| lab_security_duplicate_quote_cases_v1 | 4 | Duplicate ticker/date source quotation groups |
| lab_beta_price_exception_sensitivity_v1 | 72 | Affected ticker/rate factor baseline-versus-flag-exclusion fits |
| lab_security_price_exception_builds_v1 | 1 build | Source commit and SHA256, exception counts and unresolved status |

All 12 flagged historical security-price observations were fetched on October 17, 2026. Five share March 16, 2022: BABA, BIDU, JD, KWEB and PDD. These may reflect real market-wide shocks, but **not a single source quote, corporate action, independent venue release timestamp or vendor error has been verified**. The four duplicate FX source date keys are CNY=X, JPY=X, KRW=X and TWD=X on October 16, 2026; they show different close values within one run and must remain uncertified until the venue/FX rate convention is reconciled.

Among 864 security-minus-market rate sensitivity models, 72 correspond to INTC, MP, MRVL or PDD and contain a flagged price-return observation in the overlapping sample. The diagnostic recomputed each model with the original observations and then calculated a separate sensitivity test without flagged observations. Baseline coefficients reproduce the original 72 stored models within numerical precision. **30/72** beta sensitivity comparisons have a coefficient change >=20% of the original coefficient scale (with a minimum absolute denominator of 0.1). Small original coefficients can create large relative shifts; relative change is not proof of data error or a model approval test. All 72 sensitivity records explicitly prohibit PIT and production beta approval.

## Required independent source verification for each flagged move

- Permanent security ID, exchange MIC, ticker/issuer, original native currency and security history at date.
- Exact original source close, retrieval/publication clock and archived bytes or vendor-approved original recording.
- Adjusted-close methodology, split/dividend/distribution and ex-date, original corporate-action adjustment factors and revision vintages as known at date.
- Separately sourced market event/news or corporate announcements; look for common shocks but do not assume them.
- Source commercial license / processing and redistribution rights.
- Attributed reviewer, archived evidence, reviewer disposition (true observed shock, revised adjusted value, source/currency convention mismatch, unresolved), second-review approval and independent model-risk sign-off.

## Model governance

The primary exploratory regressions must retain recorded observations unless an independent and documented correction is made. An outlier-filtered comparison is an auxiliary robustness diagnostic, not permission to cherry-pick performance-improving observations. Predeclare robust estimators, training-only fitting, model selection and temporal holdouts. Keep correlated rate maturity and derived nominal-minus-real proxies identified and regularized by a separate approved factor methodology. The existing outlier production gate remains blocked until every flagged case is independently reconciled. No source timing, rights, security beta or event impact is approved merely because the QA pipeline runs.

**Further reading:** [Institutional data dictionary](INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md) · [Institutional factor/beta methodology](INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md).
