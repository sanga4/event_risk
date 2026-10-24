# Institutional Treasury Curve Model — Research Methodology v1.0

**Model class:** Retrospective *descriptive* security/yield sensitivities, NOT independently validated security betas or identified event responses. **As of October 24, 2026.**

## Why a separate curve model

The 18 series in the Treasury rate laboratory include correlated nominal and real yield maturities plus mechanically constructed nominal-minus-real gap proxies. A multivariate regression with all 18 as independent factors is economically and statistically ill-posed without selecting an identified, full-rank factor basis. The exploratory model instead uses **three nominal Treasury key rates only**: DGS2, DGS5 and DGS10, with constant weight combinations defined ex ante.

For daily changes in Treasury yield measured in basis points, let `Y2_t`, `Y5_t`, `Y10_t` be changes in 2-, 5- and 10-year par yields. Each source change is `100 × (yield_percent_today − yield_percent_previous)` with documented date-gap restrictions.

- **Level:** `L_t=(Y2_t+Y5_t+Y10_t)/3`, in yield basis points.
- **Slope:** `S_t=Y10_t−Y2_t`, in basis points of ten-year minus two-year yield-curve change.
- **Curvature:** `C_t=2×Y5_t−Y2_t−Y10_t`, in yield basis points.

These are a fixed invertible 3-dimensional coordinate system for these three nominal tenors. They are **not guaranteed orthogonal PCA factors, tradable Treasury portfolios, complete key-rate durations, zero-coupon Treasury bond returns or independent macroeconomic shocks**. The source spread of nominal Treasury maturities to inflation/credit regimes remains unmodeled.

For each security `i`, fit:

`r_i,t = a_i + b_M,i × r_SPY,t + b_L,i × L_t + b_S,i × S_t + b_C,i × C_t + e_i,t`

Here `r_i,t` and `r_SPY,t` are daily adjusted-close **log returns in basis points**. The three curve exposures have **security-return bps per +1 yield-curve-shock bp**; SPY beta is return-bps per return-bp. This is a joint factor **association** conditional on same-day broad-market returns, not a causal exposure, advance return prediction, bond modified duration or event-induced shock response.

## Estimation and guarded model evaluation

- Input is the existing October 2026 backfilled Yahoo adjusted-close USD prices and historical Treasury yield observations, both retrospective. Genuine historical first-available source timestamps, corporate-action adjustment vintages, licensed commercial data use and delisted universe membership remain uncertified.
- Merge 2-year, 5-year and 10-year yields only on **exactly matching observation dates** with valid SPY and security returns, no indefinite carry-forward and no same-day intra-event response inference.
- Require at least 300 matched observations, 18 distinct calendar months, an initial chronological **70% training / final 30% held-out** split, at least 210 training observations and 80 held-out observations.
- Standardize all four non-intercept predictors **only on training data for a numerical condition-number test**; reject singular or materially ill-conditioned design (upper bound 1000). Coefficients are fitted in original economic units, not standardized units.
- Multivariate ordinary least squares, Newey–West five-lag Bartlett **sandwich covariance on all five coefficients** (with a finite-sample degrees-of-freedom correction). Normal-approximate two-sided confidence intervals; hypothesis test family is every ticker × three curve slopes, with BH FDR calculated across all candidate coefficients.
- Holdout diagnostic: squared prediction error using *same-day observed* SPY and rate moves, compared with a **training-fitted SPY-only model** on exactly the same dates. It is not a tradable next-day return forecast, and historical out-of-sample comparisons still use retrospectively downloaded price and rate revisions.
- Report source days, actual security dates, training cutoff and held-out start, lag choice, standardized train condition number, train R², held-out R² vs SPY baseline, RMSE, large daily adjusted-price moves, per-factor coefficient, robust SE, BH q and approximate CI. A positive held-out R² does **not** establish that an individual factor or portfolio strategy creates positive economic value.
- **Do not discard anomalous days silently.** Join flagged issuer-days from the separate immutable price-QA register, and leave their original records untouched. Future source-verified adjustment fixes and approved robust estimators must be studied independently, including instability from large price jumps.

## First executed MotherDuck build

Producer: `lab/phase1_curve_factor_research.py`. MotherDuck Flight: `eventrisk-factor-lab-treasury-curve-research-betas`. Successful on October 24, 2026.

| Output | Actual rows/measure |
|---|---:|
| Materialized three-component nominal Treasury rate-shock dates | 701 |
| Security curve models excluding SPY as its own dependent | 48 |
| Joint curve components (3 per security) | 144 |
| Global BH-FDR q values under 5% | 6 |
| Models improving same-day holdout over SPY-only | 17 |
| Model fits containing a flagged >25% price move within matching data | 4 |
| Largest standardized predictor-design condition number | 1.7616 |
| Zero duplicate coefficient keys | Confirmed |
| Independently PIT-certified / licensed / MRM-approved risk betas | **0** |

This is a **covariance-aware methodology step**. The small training condition number helps rule out numerical near-singularity for the fitted four regressors in this sample, but says nothing about omitted variables, historic revisions, confidence interval calibration under event clustering, factor/exposure stability by era, or asset universe representativeness. 6 significant slopes are research findings, not six approved investment signals.

Source tables added without altering any existing market, factor or 864 baseline betas:

- `lab_curve_factor_retro_v1`: source rate changes and level/slope/curvature definitions; all source rights/PIT flags false.
- `lab_security_curve_model_retro_v1`: per-security model, training/holdout quality and conditioning diagnostics; all institutional release/rights flags false.
- `lab_security_curve_coefficients_retro_v1`: model coefficients, robust intervals, global BH q family; all independent validation/release flags false.
- `lab_security_curve_builds_retro_v1`: source SHA256, immutable pinned Git SHA, observed row counts and release declaration.

## Remaining requirements to become institutionally acceptable

Original Treasury observation publication-vintage and accurate exchange calendar and Treasury par-yield model, original adjusted-security data and corporate actions, as-of ticker/issuer identities and dividend reinvestment rights; a separately licensed source for portfolio exposure, factor family portfolio-return benchmarks and credit/FX/commodity/style/vol; a robust multivariate conditional covariance and beta stability analysis; true shock/announcement-time event identification and approved economic evidence; legal data rights, API auth/monitoring and model-risk committee review. No generated script may bypass this acceptance process.

This pilot is deliberately not an **event-factor beta**. Even perfectly valid security rate sensitivity cannot be multiplied by an unreviewed forecast probability move to obtain institutional event-risk impact.

[Institutional factor/beta methodology](INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md) · [Corporate-action QA evidence](SECURITY_SOURCE_QA_AND_BETA_SENSITIVITY.md) · [Project status](PROJECT_STATUS.md).
