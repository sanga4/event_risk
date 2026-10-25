# Phase I — Chronological seven-factor covariance tail calibration

This source-controlled research control extends the previously executed four-method walk-forward covariance study. For each held-out factor date, it checks a fixed 7-dimensional squared Mahalanobis shock against prespecified reference chi-square(7) quantiles: 95% = 14.0671404493 and 99% = 18.4753069066. The scores are from *strictly preceding* 252-observation training windows, but all underlying source values are historically revised ex-post snapshots.

The 99% and 95% benchmarks are **Gaussian reference diagnostics only**, NOT validated portfolio VaR exceedances: unknown distribution tails, estimation uncertainty, serial dependence, informational (not tradable) ECB FX fixings, source revisions, missing licensed holdings and independent model-risk approvals prevent that inference. An exact upper-tail binomial probability is shown strictly as an **iid approximation**, not a statistically valid approval test when windows/time-varying returns are correlated. A prespecified deterministic 10-day circular block bootstrap with 1000 resamples describes clustered exceedance-rate uncertainty, without magically correcting ex-post sample selection or certifying true coverage.

The builder verifies that all four predeclared methods use exactly the same 164 untouched chronological dates and exactly 252 training observations, with every train_end before its evaluation day. Missing/duplicated/future-conditioned scores or any source approval claim fail closed. Research-only append tables: lab_cov_tail_calibration_builds_v1, lab_cov_tail_calibration_summary_v1, lab_cov_tail_calibration_daily_v1, pinned by source model build ID, execution Git SHA and SHA-256 of the script.

**Observed pre-audit warehouse baseline:** 12/164 (7.3%) 99%-reference hits under eq252_shrink10, and 11/164, 18/164 and 15/164 under the three alternatives. A calibrated Gaussian benchmark would nominally produce about 1.64 hits in 164 periods, though independence and source PIT assumptions are not established. Do not choose a 'winning' method after observing these days, tune a shrink parameter on this holdout, or label this experiment an approved VaR backtest. Independent validation requires future first-known-at source releases, licensed risk factors, documented units, independent portfolios, prespecified stress and tail measures, rolling regime segmentation and untouched holdouts.

A successful audit cannot increase the institutional production gate percentage or certify portfolio VaR. All original_source_pit, independent model approval, rights and institutional release flags remain FALSE.

## Executed MotherDuck evidence — October 25, 2026 UTC

On-demand MotherDuck Flight `eventrisk-lab-covariance-heldout-tail-calibration` UUID `9d9150b3-f26d-4dc8-8e68-f7c2e0686c7b` run 1 completed successfully (exit 0). Producer Git SHA `493b1e6aba446a8d9aa7b0ee6555c352ef5a2590`; source build `phase1-walk-forward-regime-cov-v1.0.0-20261025T004008412896Z`; audit build `phase1-covariance-tail-audit-v1.0.0-20261025T033407091437Z`. Pinned Flight dependencies: duckdb==1.5.6, pytz==2025.2. The Lab offline suite passed 162 tests, including ten new covariance-tail controls.

| Predeclared covariance method | 99% hits /164 | Descriptive 10d block-bootstrap 95% interval | Longest consecutive hit run | iid-only upper-binomial diagnostic |
|---|---:|---:|---:|---:|
| eq252_shrink10 baseline | 12 | 3.05%–12.20% | 2 | 1.28626e-7 |
| eq252_shrink50 | 11 | 2.44%–12.20% | 2 | 1.01059e-6 |
| ewma094_shrink10 | 18 | 5.49%–16.46% | 2 | 1.09171e-13 |
| ewma097_shrink10 | 15 | 4.27%–14.63% | 2 | 1.62846e-10 |

The base Gaussian reference expectation is ~1.64 hits per 164 dates. All four models have three recorded >4-training-standardized-factor-shock days, each also above the 99% Mahalanobis threshold. The model-specific 99% hit counts sum to 56 across four *correlated* evaluations, not 56 independent calendar-day exceedances. The exact nominal iid p-values are not institutional acceptance tests given serial dependence and fitted covariance uncertainty. The source's retrospective revision clock, provider rights and portfolio basis remain unverified. No original source was corrected and zero approved portfolio VaR or institutional model release claims were written.
