# Phase I: Security–Treasury Rate Sensitivity Research v1.0

**Status:** EX POST RESEARCH ONLY — not a security risk-model release, causal event response, predictive signal or licensed commercial beta. Source repository: `sanga4/event_risk` only. The `huimarco/event_risk` MVP is not changed.

## Data found and loaded

The `eventrisk_factor_lab.main.security_prices` table **already** held 107,157 security-price observations for 63 symbols from 2020-01-01 through 2026-10-16. All were collected in one Yahoo historical backfill on 2026-10-17; four duplicate ticker×date rows were found. This existing source corrects an earlier assumption that security prices had not been loaded. They are **not exchange/PIT-certified prices**, and Yahoo adjusted-close corporate-action revision and redistribution rights are not validated.

The first pipeline build on 2026-10-24 produced:
- `lab_security_returns_retro_v1`: **83,427** positive-USD-adjusted-price daily *log-return proxy* rows across **49** USD instruments. All 63 raw symbols were inventoried; non-USD FX quote-convention rows, unbounded gaps, missing/invalid prices, and first observations do not enter this USD regression universe.
- `lab_rate_shocks_retro_v1`: **12,618** percent-quoted Treasury nominal/real plus clearly labeled derived nominal-real proxy changes across **18** series. Basis-point shock = `100 × [yield_percent_t - yield_percent_(t-1)]` with a 1-to-7-calendar-day gap. No forward fill, no credit or ambiguous-license factor.
- `lab_security_rate_betas_retro_v1`: **864** asset×factor bivariate-with-market-control regressions (48 USD instruments other than `SPY` × 18 rate factors), each with **694 matched daily observations**. Data overlap is broadly 2024–2026. There are **130** FDR-q<0.05 retrospective coefficients, **414** with positive out-of-sample R² against the `SPY`-only contemporaneous baseline, **49** passing both *exploratory* screens. **ZERO** are licensed, point-in-time approved or cleared for institutional decision use.
- `lab_security_beta_builds_retro_v1`: immutable full-Git-SHA and code SHA256 build manifests, raw counts, deduplication, outlier counts, model counts and release status.
- **12** unusually large daily adjusted-price log returns (absolute log move over 25%) remain explicitly flagged, with no invented explanation or automated deletion.

### Estimator and exact units

For ticker `i`, observed calendar day `t`, rate factor `k`, and SPY:

`y_it = 10,000 × ln(adjusted_close_it / adjusted_close_i,t-1)` **basis points** of daily security adjusted-price log return.

`m_t = 10,000 × ln(SPY_adjusted_close_t / SPY_adjusted_close_t-1)` **basis points** of benchmark daily adjusted-price log return.

`x_kt = 100 × [yield_pct_kt − yield_pct_k,t-1]` **basis points** of yield change.

Estimate **separately for each ticker×rate factor**:

`y_it = α_ik + β_market,ik m_t + β_rate,ik x_kt + ε_it`.

`β_rate` is **security-return basis points per 1bp of yield change**, not a factor *return* beta, and not the effect of an event-probability move. This bivariate SPY-plus-one-rate specification does not disentangle multiple correlated yield-curve/real-rate factors. It is not a full multifactor risk engine or equity-style-factor regression. A daily `GLD` versus `DGS10` association, for example, must not be converted into a geopolitical-event P&L forecast.

### Fitting and validation

- Align only matching calendar dates with independently valid price/yield observations; deduplicate ticker-date records deterministically by `fetched_at` and `run_id`. No extrapolation across gaps over seven calendar days; use **SPY as a market return control** only when SPY's own return date is available.
- Minimum 250 matched days, at least 18 months, and sufficient benchmark/factor variance. Fit the first chronological **70%** of observations, reserve the last 30% as untouched holdout **for model fitting**.
- Use Frisch–Waugh–Lovell residualization of the factor relative to market control, ordinary least squares for the factor slope, five-lag Bartlett/Newey–West sandwich standard error with `n/(n-3)` small-sample scaling; normal-approximate two-sided p and 95% intervals. BH/FDR correction applies **across all 864 tested slopes**; no posthoc selective exclusion.
- Report in-sample R² and **same-day contemporaneous** test error compared with a market-only model trained on the same training dates. **Positive test R² is NOT a forward tradable forecast**: same-day observed factor shocks and SPY returns are unavailable ex ante.
- Retain all price moves, including 12 large-return flags. Investigate their original vendor corporate-action adjustments and securities' market events before permitting release. Do not winsorize or truncate without a pre-registered independent policy.
- Inspect coefficient stability by rolling regimes, correlated factor basis/multicollinearity, source changes, survivorship bias, and asset/factor calendar mismatch. The historical universe is an October 2026 ticker selection, not an as-of historical investable universe.

### Unresolved risk and limitations

Every input record in this study was obtained via **retrospective** collection; the original historical source availability, corporate-action-adjustment and Treasury/FRED publication/revision vintages have **not been independently verified**. Source `source='yahoo'` requires license/data-rights clearance for external API redistribution or use. Some instrument symbols identify ETFs rather than ordinary-company equity; the taxonomy needs proper asset classes and benchmark mapping. SPY itself is excluded as the dependent variable to avoid a tautological control.

These results are **not** event beta estimates. The required institutional path remains: (1) acquire/verify provider-specific timestamped factor and investable adjusted-return vintages, (2) validate source and holdings rights, (3) identify event surprises and economic mechanisms independently, (4) test predeclared event-time horizons and confounders, (5) estimate a licensed multifactor model with covariance, missingness and economic sign conventions, (6) independent model-risk committee and operations approval.

### Code and independent gates

Source: `lab/phase1_security_rate_beta_backfill.py`.
Run using only `LAB_RESEARCH_SCOPE=internal-only`, immutable 40-char `LAB_PIPELINE_COMMIT`, and a narrowly scoped MotherDuck token. Outputs overwrite **only** versioned `*_retro_v1` current snapshot tables in an atomic transaction; build manifests append for each run. Historical underlying market and factor source tables are never modified. API `/v1/research/security-betas/retrospective` is **disabled by default** and requires an authenticated internal research-only switch. The gate report checks that model rows exist, source price vintages/corporate actions are independently verified, anomalous price moves are resolved, and *no unapproved betas are released*.
