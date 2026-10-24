# EventRisk Factor Lab — U.S. Equity Style Return Backfill and Six-Factor Sensitivity Methodology

**Date:** 2026-10-24 · **Status:** retrospective INTERNAL RESEARCH ONLY, **not approved for redistribution, independent historical PIT backtests, institutional portfolio risk, investment signals or causal event analysis**.

## 1. Original source and its limitations

Official reference: Kenneth R. French, [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html). Only *official* downloadable, daily files were used:

| Source | Provider archive file | Native date coverage | SHA-256 verified on ingestion |
|---|---|---|---|
| U.S. Fama/French five factors, daily + daily RF | `F-F_Research_Data_5_Factors_2x3_daily_CSV.zip` | 1963-07-01 through 2026-08-31 | `7881223b51929ee0d6d23b8a28524aaec478a2c3d4eeca47224955cc845c5186` |
| U.S. Momentum daily | `F-F_Momentum_Factor_daily_CSV.zip` | 1926-11-03 through 2026-08-31 | `ecf82b116e6ec56d2b79a2f27bd1d1598c217b5c6c25caa55b945bdd8a2c0b78` |

Both files had Last-Modified HTTP header `2026-09-25 21:55:02 UTC` when retrieved **2026-10-24**. That header is *not* evidence of any original historical publication timestamp for an individual 1963 or 2025 factor return. The newest source observation is **2026-08-31**, so this historical source is not a daily live feed for October 2026. The Library documents a switch to the new CRSP CIZ format beginning with the January 2025 release, with adjustments to historical returns. A currently downloaded file is **a revised historical snapshot**, not an original as-known-at-each-date archive.

Data reuse, research licensing, CRSP-linked vendor terms and any external/API redistribution **have not been signed off**. Source-level `redistribution_rights_verified=FALSE`. Raw factor values or security beta coefficients **must not be served on public APIs** until independent authorization. Source ZIP bytes are not yet preserved in a separately licensed replay archive; SHA-256 and downloaded source URL are persisted, but a future changed provider file would require a securely licensed byte archive for exact historical replay.

## 2. Exact data schema and semantic units

MotherDuck lab database `eventrisk_factor_lab`:

- `lab_style_factor_source_archives_v1`: versioned SHA-256 of exact official ZIP bytes, provider/source URL, HTTP Last-Modified header, compressed archive size, **first warehouse retrieval** timestamp and rights/PIT flags.
- `lab_style_factor_returns_v1`: content-addressed source ZIP factor/date version, region `US`, daily factor **simple return in decimal units** (published percent value / 100), native source percent, currency `USD`, portfolio-construction class and build ID. The `vintage_date` is the **internal retrieval-snapshot date**, NOT the factor's historical first-publication date. Every original-provider-PIT, right-to-distribute and institutional-risk approval flag FALSE.
- `lab_style_factor_ingest_builds_v1`: append-only immutable Git SHA + source-script SHA, two archive versions, record counts, per-run inserts and source date range.
- `lab_ff6_security_models_retro_v1`, `lab_ff6_security_coefficients_retro_v1`, `lab_ff6_research_builds_v1`: statistical results with full source and no-release metadata.

Factor IDs and their economic interpretation:

| Factor | Factor ID | Meaning | Unit |
|---|---|---|---|
| `Mkt-RF` | `FF_US_MKT_RF` | U.S. stock market excess over source daily RF | Daily simple return decimal |
| SMB | `FF_US_SMB` | Small minus big size return spread | Daily simple return decimal |
| HML | `FF_US_HML` | High-minus-low book/market value spread | Daily simple return decimal |
| RMW | `FF_US_RMW` | Robust-minus-weak profitability spread | Daily simple return decimal |
| CMA | `FF_US_CMA` | Conservative-minus-aggressive investment spread | Daily simple return decimal |
| Mom | `FF_US_MOM` | Momentum portfolio spread, separately sourced | Daily simple return decimal |
| RF | `FF_US_RF` | Source research risk-free return used in excess-return construction, **not a risky asset loading** | Daily simple return decimal |

**Never difference factor returns as if they were Treasury yields.** Percent provider values are converted once: `simple_return_decimal = published_percent / 100`. For regression, multiply by 10,000 to produce return **basis points**. Source sentinels -99/-99.99/-999 are not zeros; nonfinite values, wrong daily header, repeated/nonascending source dates and accidental monthly `YYYYMM` blocks trigger skip or fail-fast rules. Daily factor source file SHA changes create *additional* versions rather than overwriting old versions. An unchanged source file yields **0 inserted rows** on a repeat run, verified.

### First backfill and as-of field audit

- **121,598** style/risk-free daily return observations across seven separate factor IDs.
- Daily 5-factor plus RF file contributed 95,382 rows (6 × 15,897 dates); momentum 26,216 rows. All rows unique by factor ID/date/exact source-file checksum.
- Zero source series falsely marked independently PIT- or rights-cleared, and zero duplicated factor/day/file keys.
- Re-running the Flight against unchanged source archives inserted **zero** extra observation rows and **zero** new archive manifests.
- The 16-domain canonical institutional data contract re-audit improved from **146 to 135 missing mandatory fields** (out of 255); one required provider original market quote timestamp remains entirely unpopulated. Structural field presence is **119/255 = ~46.7%**, not independent certification.
- On-demand processing is available via the MotherDuck Flight `eventrisk-factor-lab-us-french-research-styles`, UUID `c595b802-8114-4c9a-a875-9650e7c36cb9`, without automatic refresh/scheduling.

## 3. Retrospective six-factor security exposure research

Producer: `lab/phase1_ff6_security_research.py`, Flight `eventrisk-factor-lab-us-six-factor-security-exposures`, UUID `3b6312ca-9c61-4a48-9d67-543537246093`.

For each USD security, use the **already loaded retrospective** Yahoo adjusted-close daily log-return observation `log_r_bps`. Convert to **daily simple return** in basis points (do NOT mix log-asset and simple-factor units):

`asset_daily_simple_return_bps = 10000 × (exp(log_r_bps / 10000) − 1)`.

Then form dependent daily simple excess return with Kenneth French source RF:

`y_t = asset_daily_simple_return_bps − 10000 × FF_US_RF_t`.

For source US style returns `x_k,t = 10000 × factor_daily_simple_decimal`, estimate **jointly**:

`y_t = α + β_M (Mkt−RF)_t + β_S SMB_t + β_H HML_t + β_R RMW_t + β_C CMA_t + β_Mom Mom_t + ε_t`.

Slopes are security *simple excess-return bps per one factor simple-return bp*; market and style risk loadings are **descriptive regression coefficients**, not true investable positions or sources of causally identified shocks. Because provider source values were retrieved in 2026 and security prices are adjusted ex post, this is NOT a valid historical backtest of information available at time `t`.

Model fitting:
- Join factor data and security returns on equal **daily source observation dates**, requiring all six factors plus RF; select the latest retrieved source-version in the lab for each daily factor, *only as an explicit retrospective version*.
- Minimum 280 matched days, 18 distinct months, first chronological 70% fit, final 30% as same-day held-out explanatory diagnostic; >=195 training and >=80 holdout observations.
- OLS with seven columns (constant + six returns) and **full multivariate HAC(5)** Bartlett sandwich covariance. Standardize predictors on training data **only for rank/condition screening**, refuse singular or condition number above 1,000; fit original-unit coefficients.
- Normal approximate two-sided p values and 95% confidence intervals; global Benjamini–Hochberg multiple-testing correction over the *entire* 48×6 coefficient family (288 hypotheses). Do not cherry-pick a subset or infer security risk contribution solely from p-values.
- Compare same-day holdout errors with a **market-only** model trained on identical training dates, not a trading forecast. Report market benchmark, days, calendar split, factor condition number, 6 betas, HAC SE, global q, outlier flags and source rights.
- The 12 separately flagged historical adjusted-close source moves are not modified or automatically excluded; retain case provenance and build separate independent vendor-event review decisions.

First successfully executed build, on existing data:

| Computation | Result |
|---|---:|
| Seven-factor joint source calendar days | 15,897 |
| Historical USD security six-factor regressions | 48 |
| Fitted coefficient rows (6/security) | 288 |
| BH FDR 5% research coefficients | 151 |
| Models better than contemporaneous market-only held-out comparator | 27 |
| Models exposed to prior flagged large adjusted-price move | 9 |
| Worst standardized training design condition | 3.1352 |
| Minimum / maximum matched dates per fitted security | 1,555 / 1,673 |
| Duplicate coefficient keys / unauthorized beta releases | 0 / 0 |
| Independent point-in-time/security adjustments/vendor rights/model risk approvals | **0** |

**Interpretation:** Because the factors directly span securities' risk exposures, many historical associations can be statistically strong; this is not evidence of alpha, tradeable foreknowledge or an event-factor response. Global FDR on selected 2026-survivor tickers also does not correct for having chosen the universe with hindsight, the asset-return vendor's retroactive split/dividend adjustments, correlated security errors, or regime/event heterogeneity.

## 4. Institutional release blockers and next tests

For source timing: preserve actual original-provider publication-vintage history, content-addressed source bytes under an authorized license and as-of security-price/corporate-action versions. Validate provider change to CIZ source mechanics and research portfolio formation/reconstitution/constituent/region. Document whether local corporate security returns vs US RF and USD conversions are compatible for each instrument.

For methodology: obtain approved security master and listing/delisting membership, macro/credit/commodity/FX/vol factors and factor covariance, evaluate multicollinearity/sector concentration, rolling/recursive beta stability, purged temporal event validation, two-way clustered uncertainty and independent model risk. For investment event transmission: independently verify event probability surprise and release clock, economic mechanism reviewer and linked factor responses before any joint event→financial portfolio scenario.

For rights/production: confirm French/CRSP permissible internal/commercial/redistribution usage. Only metadata summary may be served via the authenticated Factor Lab API while raw source-factor data and derived security betas are withheld. Railway production database/API credentials are separately outstanding.

**Formal release gate build v1.6:** 12/26 automatic PASS, 14 BLOCKED, and four manual requirements outstanding. A successful factor import earns one research-availability pass; it does NOT clear independent source-vintage and rights certification. This model is not part of the institutional approved security beta pool.
