# Corporate Action Reconciliation and Cross-Asset Covariance Sensitivity

**Executed October 25, 2026 UTC** in `eventrisk_factor_lab`, targeting only `sanga4/event_risk`. All source first-published dates, issuer action data, external usage rights and independent risk-model approvals remain UNVERIFIED. The analytics are research triage, not vendor reconciliation certification or institutional VaR.

## 1. Corporate-action source-candidate reconciliation

Producer `lab/phase1_adjusted_price_reconciliation.py`, MotherDuck Flight `eventrisk-lab-security-adjustment-factor-reconciliation` (bd5640d1-9bdd-48b1-8b87-f8aa312fb3f9). Output source warehouse tables: `lab_security_adjustment_ratio_changes_v1`, `lab_security_exception_adjustment_joins_v1`, `lab_security_adjustment_audit_builds_v1`.

Read Yahoo-sourced daily original-vendor `close` and `adj_close` fields, grouped by symbol/source observation date. Explicitly **exclude all duplicated ticker/date groups** rather than choosing one conflicting FX snapshot. The retained source observations remain original read-only; no prices were fixed or overwritten.

Let the vendor adjustment ratio `A_t = adjusted_close_t / close_t`. The adjustment-ratio discontinuity is `dlogA_bp = 10000 × [ln(A_t) – ln(A_t−1)]`. For source daily closes, the exact identity is `adjusted_close_log_return_bp – unadjusted_close_log_return_bp = dlogA_bp`. The pipeline enforces max identity residual <=0.000001 bps and rejects invalid prices. Flag discontinuities at **50 bps** as triage candidates; a separate **200 bps** flag indicates a larger source adjustment-ratio step. A ratio change by itself does not identify a split, dividend, return correction or published-at vintage.

| Independently executed measure | Count/result |
|---|---:|
| Unique valid source price rows | **107,149** across **63** tickers |
| Duplicated original ticker/date groups excluded | **4** |
| Vendor adjustment-ratio jumps ≥50 bps (absolute) | **369** |
| Larger jumps ≥200 bps (absolute) | **51** |
| Existing large security-price return cases reconstructed | **12** |
| Existing large security-price cases coinciding with ≥200 bp adjustment-ratio jump | **0** |
| Maximum reconstruction equation residual | **<0.000001 bps** |
| Original corporate-action, vendor revision or distribution-rights approvals | **0** |

The 12 exceptional adjusted-return days include independently plausible event-related market moves. An absence of material vendor adjustment-ratio steps on those exact dates argues against a major *same-day adjustment factor discontinuity* as an explanation; it does **not** establish genuine exchange original prices or their first-known timing, nor rule out corporate-action issues elsewhere.

**Acceptance owner:** licensed corporate-action source vendor, stable security/issuer master, exchange original-close specialist, independent data steward and model-risk signoff. Required security permanent IDs, originals of split/dividend notices and ex dates, raw exchange close, first provider publication and original adjustment revision history are still missing. All row-level evidence/approval flags FALSE.

## 2. Six-model covariance shrinkage stress

Producer `lab/phase1_covariance_shrinkage_sensitivity.py`, MotherDuck Flight `eventrisk-lab-crossasset-covariance-shrinkage-stress` (272c16c8-d8ff-4dcb-8b98-06a03d64c107). Source: already built **7×7** standardized Treasury curve, EUR FX informational reference and US French style covariance over **458 train and 197 chronological heldout** observations (655 exact common days). Inputs retain source SHA/provenance in respective factor research tables.

Six **predeclared** diagonal shrinkage proportions **0%, 10%, 25%, 50%, 75%, 100%** applied to the *same original training covariance*. Each variant is judged on the same retrospective holdout covariance. The scores below are model sensitivity diagnostics; selecting the hindsight-winning proportion from this holdout to advertise production skill is prohibited. Gaussian covariance-only pseudo-log score is `logdet(C) + trace(C⁻¹ × heldout_cov)`. It is not a daily predictive portfolio loss, normality test, or VaR backtest.

| Training diagonal shrinkage | Train condition | Holdout relative covariance difference | Holdout Gaussian pseudo-score |
|---|---:|---:|---:|
| 0% | 3.852 | 69.94% | 5.7022 |
| 10% | 3.259 | 69.94% | 5.7188 |
| 25% | 2.596 | 70.11% | 5.7562 |
| 50% | 1.848 | 70.86% | 5.8343 |
| 75% | 1.353 | 72.21% | 5.9235 |
| 100% | 1.000 | 74.11% | 6.0255 |

**Finding:** increasing diagonal shrinkage improves numerical conditioning, but **all six candidates breach 50% holdout drift**. More shrinkage is *not* an institutional acceptance solution for the observed regime instability. The 0% candidate has the lowest *exploratory in-sample-selected holdout score*, but must NOT be promoted into an approved model on that basis. Future stress work needs genuinely independent point-in-time historical data, regime segmentation, multiple heldout periods, liquidity/contract term conventions, tail calibration, portfolio holdings and independent review.

Output tables: `lab_factor_covariance_shrinkage_tests_v1`, `lab_factor_covariance_shrinkage_builds_v1`; all hindsight-selected/production-approved/license flags remain FALSE.

## 3. Institutional release gates, owner requirements and next steps

The institutionally blocked model requirements are **not** cleared by candidate source calculations: as-of adjustment/corporate-action originals and licensed data rights are missing; no covariance candidate satisfies the >50% drift gate. New quantitative construction/QA gates can pass without overriding those independent blockers.

Gate version **v2.1** ran successfully: **21/43 automatic checks PASS (48.8%)**, 22 BLOCKED, **4 separate manual approvals**. Production risk release remains FALSE. The action-owner register is rerun separately and includes new source and risk-review tasks.

Next high-value engineering tasks are (1) legally authorized corporate-action and delisted issuer master import with actual historical provider revisions and immutable raw payloads, (2) event-time quote/consensus provenance, (3) regime-dependent covariance/conditional risk tests with independent untouched validation periods, (4) independent original evidence and dual approvals, and (5) working authenticated production data/operations with least-privilege credentials.

[Status dashboard](PROJECT_STATUS.md) · [Institutional methodology](INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md) · [Phase I closeout roadmap](PHASE1_CLOSEOUT_ROADMAP.md) · [Original security and event evidence](ROLLING_SECURITY_BETA_AND_EVIDENCE_METHODOLOGY.md)