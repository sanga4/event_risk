# Walk-Forward Cross-Asset Covariance and Security-Return Robustness — Phase I

**Run completed:** 2026-10-25 UTC / 2026-10-24 America/Los_Angeles. **Scope:** retrospective internal research only, **NOT** independently publication-time point-in-time, source-redistribution certified, investable covariance, portfolio VaR, identified event effect, or institutionally approved beta.

## 1. Four precommitted walk-forward covariance forecasts

Executable producer: `lab/phase1_regime_cov_walkforward.py`, MotherDuck Flight `eventrisk-lab-walkforward-regime-covariance` (`a40edf13-4f47-47f1-bd3c-502ddf670539`). Source is the exact **655-date common calendar** of previously loaded three nominal Treasury curve shocks, two informational quote-currency-per-EUR ECB reference-rate logarithmic changes and two US French simple daily portfolio return factors. Factor source documents and SHA references remain in each original warehouse.

**Method**: For each chronological date in the **last 25%** (164 dates), use strictly previous **252** common observation days to compute a training-only historical mean and standard deviation per factor. Fit one full seven-factor standardized covariance per precommitted method. Evaluate the next observed seven-dimensional factor vector with Gaussian covariance-only `loss = logdet(C) + ((x−mu)/sd)' C^{-1} ((x−mu)/sd)`. The factor mean (`mu`) and standardization (`sd`) always come from trailing training data and are **identical across methods at a given date**; none can use the evaluation day's data.

Precommitted methods: equal-weight historical 252-day sample covariance with 10% diagonal shrink (BASELINE), equal-weight with 50% diagonal shrink, EWMA daily decay 0.94 with 10% diagonal shrink, and EWMA decay 0.97 with 10% diagonal shrink. For EWMA, normalized exponential weights are applied to trailing training-residual outer products around the common unweighted 252-day train mean. No holdout-based optimizer. We also calculate a deterministic seed-20261025 **500-resample circular 10-observation moving-block bootstrap** confidence interval for the *paired same-date mean loss difference* versus baseline; these intervals are exploratory and overlap in time/cross-asset correlations.

| Candidate | Mean covariance pseudo-log loss | Difference vs. baseline (lower is better) | Moving-block exploratory 95% CI for paired mean difference |
|---|---:|---:|---|
| Equal-weight 252d + 10% diagonal shrink (baseline) | **6.6076** | 0.0000 | [0.0000, 0.0000] |
| Equal-weight 252d + 50% diagonal shrink | **6.7025** | +0.0948 | [+0.0002, +0.1860] |
| EWMA 0.94 + 10% shrink | **7.4515** | +0.8439 | [−0.0318, +1.8097] |
| EWMA 0.97 + 10% shrink | **6.6544** | +0.0467 | [−0.3995, +0.5267] |

**Measured result:** **656** dated one-day model evaluations (4 methods × 164 dates) stored; **zero** alternatives outperform the 10%-shrink baseline by average retrospective loss; zero holdout block-bootstrap superiority flags. This is a negative research result, and the baseline is **NOT** selected/approved for real portfolio risk. Some standardized reference FX values are informational and could not be traded. True historical provider revision and initial availability cannot be deduced from current warehouse retrieval.

Research tables: `lab_regime_cov_daily_scores_v1` (each one-day training window, loss, quadratic shock and condition), `lab_regime_cov_model_comparisons_v1` (four paired block-bootstrap summary results), `lab_regime_cov_research_builds_v1` (pinned source-code SHA, dates, source coverage, explicit fail-closed model and licensed-use flags). The API returns summary statistics only, never original vendor observations or matrix cells.

**Limitations beyond PIT and licenses:** Gaussian covariance loss is sensitive to very large return observations and non-normal tails; 10-day blocks/500 bootstrap samples do not remove sample selection, multiple-model dependence or cross-asset asset-level calendar/revision problems. Next independent validation should use a future true-as-known source window, issuer/security master, approved stress and tail-risk estimates, regime segmentation and portfolio dollar exposures, before VaR/backtest/committee approval.

## 2. Separate train-only counterfactual for flagged large adjusted-price days

Executable producer: `lab/phase1_ff6_extreme_return_sensitivity.py`, Flight `eventrisk-lab-ff6-outlier-beta-sensitivity` (`f089a800-1d08-41d0-a491-b04692e83500`). This is a separate research sensitivity experiment using 48 previously sourced US-dollar securities and exactly the same *historical*, retrospectively adjusted security daily log returns and US French Mkt–RF, SMB, HML, RMW, CMA, Mom plus risk-free return.

**Return units:** convert historic vendor security log-return bps to **simple** return bps as `10000*(exp(log_return_bps/10000)−1)`, subtract research RF daily simple return bps, and regress on six Fama–French/Momentum source **simple-return** bps. Never treat a macro yield change or an ECB reference rate as a simple stock return.

**Frozen fairness rule:** first 70% of each security’s matched original observation dates is TRAIN, final 30% untouched evaluation. Fit baseline OLS on all TRAIN dates; fit a counterfactual OLS excluding **only** historical security-return source flag days with >25% absolute log return FROM TRAIN. Compare the two fitted six-dimensional coefficients and score BOTH against the *identical heldout rows* (including any flagged holdout observations). This simulates source-quality sensitivity; it does not actually delete, correct or license any vendor prices. Reject poorly conditioned/rank-deficient designs.

| Confirmed result | Actual output |
|---|---:|
| Eligible USD security models | **48** |
| Six-factor beta pairs (baseline and counterfactual) | **288** |
| Securities with flagged days inside training | **8** |
| Securities with flagged days inside the untouched holdout | **2** |
| Relative six-factor beta-vector movement >=10% | **2** |
| Excluding flagged training observations improved same-heldout SSE | **6** |
| Largest six-dimensional relative beta movement | **11.31%** |
| Original source prices altered or new corporate actions independently verified | **0** |
| Model-risk, first-publication PIT or external commercial beta release approvals | **0** |

Interpretation: a flagged daily adjusted price is not automatically a bad source quote. Removing flagged dates can reduce or increase ex-post holdout error. The two material beta-sensitive cases remain unapproved and must be reconstructed using actual original exchange prices, issuer corporate-action records, permanent identifiers, source revisions, and independent data stewards. This sensitivity is not justification for generalized winsorization or overwriting those 12 earlier anomalous-return cases.

Research tables: `lab_ff6_price_extreme_sensitivity_v1`, `lab_ff6_price_extreme_beta_components_v1`, `lab_ff6_price_extreme_builds_v1`. Coefficients are not externally served; the API exposes only aggregate counts and source-approval warnings.

## 3. Institutional acceptance and owner evidence

Last gate build **v2.2.0** succeeded: **23/47 automatic controls passing (48.9%)**, **24 blocked**, and **four independent manual conditions**. Last owner remediation register **v1.7.0** succeeded: **51 tracked acceptance requirements across nine workstreams**, **zero approved production release**. Research availability gates for new datasets pass; source rights/real historical as-known vintages and independent model-risk/beta stability remain blocked.

The largest release blockers still require real documents and a human reviewer: licensed original market/issuer corporate-action history, venue original publication/quote clocks, attributable macro consensus and factor surprises, permission to use French/CRSP and source FX/credit, true authorized holdings, credentials/scoped secrets in Railway/GitHub, repeated source feed scheduling and independent model committee decisions. Without those inputs, no number of retrospective computations can certify institutional as-of production.

[Current project status](PROJECT_STATUS.md) · [Original issuer adjustment evidence](SECURITY_ADJUSTMENTS_AND_COVARIANCE_STRESS.md) · [Phase I closeout roadmap](PHASE1_CLOSEOUT_ROADMAP.md)