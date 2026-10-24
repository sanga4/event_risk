# Institutional Cross-Asset Research — ECB FX, U.S. Macro and Covariance

**As-of:** October 24, 2026. **Status:** retrospective INTERNAL RESEARCH ONLY. Source owner: sanga4/event_risk. The huimarco MVP is unchanged.

## Official ECB EUR reference FX — source loaded and verified

ECB SDMX reference: https://data-api.ecb.europa.eu/service/data/EXR/ . Official ECB quote method: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html .

The source-controlled importer is lab/phase1_ecb_fx_references.py. MotherDuck Flight ID: dbdfe81f-ef4a-4b6a-9a6b-633f003b7ddb. Two full runs SUCCEEDED; the second inserted **0 new source records and 0 new source versions**. Data source: EUR-base quote reference pairs USD, JPY, GBP, CHF, CAD, AUD and CNY, all quoted in local currency units PER 1 EUR. Example on 2026-10-23: 1 EUR = 1.1193 USD = 175.51 JPY. Historical dates: 2005-01-03 to 2026-10-23.

- Source-hashed reference-price rows: **39,088** (7 × 5,584). Raw provider SHA-256 per currency; retrieval time and original HTTP metadata recorded.
- Derived reference log changes: **39,081** rows per build, in 10,000 × ln(quote_per_EUR_today / quote_per_EUR_previous) basis points; do not interpret as executable returns. Do not forward-fill stale exchange dates.
- Tables: lab_fx_source_snapshots_v1, lab_fx_reference_rates_retro_v1, lab_fx_returns_retro_v1, lab_fx_backfill_builds_v1.
- ECB daily EUR reference rates usually publish around 16:00 CET on TARGET working days, but that is NOT an independently proven exact publication time for each historic row. The ECB publishes the rates for INFORMATION PURPOSES ONLY and discourages their use for trading.
- All provider-original-PIT, trading-execution, distribution rights and institutional-risk release flags remain FALSE. Source date is not actual first-available date.

## Official FRED macroeconomic inputs — loader ready, source download BLOCKED

Source-controlled importer lab/phase1_fred_macro_research.py. MotherDuck Flight ID: 52c049f8-fa3d-42eb-939a-442c0ad28f2f. The FRED graph CSV official endpoint timed out on two actual Flight runs, including a 2018-onward limited-window retry. **ZERO source values loaded by this importer.** Do not report this as a macroeconomic backfill.

| Required series | Original frequency | Native source unit | Permitted descriptive transform (not an event surprise) |
|---|---|---|---|
| DFF effective Fed funds | daily | annualized rate % | daily change in rate bps |
| SOFR | daily | annualized rate % | daily change in rate bps |
| NFCI financial conditions | weekly | index level | weekly index point change |
| CPIAUCSL | monthly | seasonally adjusted CPI index | trailing 12-month percentage change |
| UNRATE | monthly | unemployment rate % | monthly percentage-point change |
| WALCL | weekly | Fed assets in millions USD | weekly change in log bps |

These are latest/revised FRED observations, not original ALFRED publication vintages. Never equate reference month with source announcement date or policy-rate difference with a consensus surprise. Independent source/API access approval and official history/revision evidence remain required. Source documentation: https://fred.stlouisfed.org/docs/api/fred/ .

## Seven-factor cross-asset covariance research — SUCCEEDED

Code lab/phase1_cross_asset_covariance_research.py. MotherDuck Flight ID: 37b7088d-ee75-4d75-9157-2e7a7ccd7b18. Data families are **three fixed nominal Treasury curve shocks** (level/slope/curvature, yield bps), **two ECB EUR-base FX quote changes** (USD and JPY per EUR log change bps), and **two U.S. Kenneth French simple portfolio return factors** (market excess and momentum, simple return bps).

Exact date intersection only, no weekly-monthly forward fill. Estimate a full 7×7 covariance of factor movements after **training-only** centering/scaling. Predeclared 10% diagonal covariance shrinkage; all native-source units retained for traceability. This is a dimensionless standardized *research covariance*, not tradable factor returns or portfolio risk.

| Executed measure | Real result |
|---|---:|
| Strict jointly matched dates | **655** |
| Chronological training dates | **458** |
| Chronological holdout dates | **197** |
| Covariance matrix cells | **49** |
| Minimum shrunk eigenvalue | **0.4810** |
| Train covariance condition number | **3.259** |
| Holdout vs train shrunk covariance Frobenius difference (relative) | **69.94%** |
| Largest holdout-to-train or inverse factor variance ratio | **2.382** |

Data: lab_cross_asset_factor_covariance_v1, lab_cross_asset_risk_diagnostics_v1. This high historical holdout drift demands regime-stability testing and independent validation. Covariance entries cannot be converted into VaR, tradable signals, causal event-to-factor betas or portfolio P&L without actual positions, stable exposures, source rights and source timing.

## Production acceptance boundaries

1. Clear original per-record source publication time and vendor/ECB rights, not simply warehouse ingestion times.
2. Restore official FRED source access with an approved API key or permitted delivery channel; no secrets in chat. Ensure ALFRED first-release/revision clocks and source data calendars are genuinely verified.
3. Acquire market/executable FX quotes for any trading model; never substitute informational ECB fixes.
4. Cross-asset model-risk review must test factor regime stability, covariance condition, parameter estimates, missingness, currency/market holidays, source-time as-of and backtest results.
5. Event-to-factor causality remains unapproved and requires dated source evidence, analyst review and identifiable information surprises. Legal redistribution and Rails API credentials remain outstanding.

**Research assets do not imply production rights or release.** This entire milestone intentionally keeps model release approvals FALSE.

[Project Status](PROJECT_STATUS.md) | [Release Unblock Plan](PHASE1_PRODUCTION_UNBLOCK_PLAN.md) | [Institutional Data Dictionary](INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md)