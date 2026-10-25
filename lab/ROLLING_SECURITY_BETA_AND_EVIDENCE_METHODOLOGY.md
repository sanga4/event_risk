# EventRisk Institutional Phase I — Rolling Security Betas and Original Source-Evidence Governance

**Executed:** 2026-10-25 UTC, internal retrospective research only. **Institutional beta/event impact approval remains BLOCKED.** Independent source publication time, historic security corporate-action revisions, attribution, usage rights and signed dual reviews remain outstanding.

## Rolling US six-factor security sensitivities

Producer: `lab/phase1_ff6_beta_rolling_stability.py`; MotherDuck Flight `eventrisk-lab-rolling-ff6-security-betas` (`4d530240-a96b-4b37-a152-8ac1968574d3`). The model reuses the separately backfilled US French daily six risky factor portfolio returns (Mkt–RF, SMB, HML, RMW, CMA, Momentum) plus RF for USD-security excess return.

**Dependent/independent units:** the historical Yahoo adjusted-close security return is originally a logarithmic daily basis-point return. Convert to daily **simple** security return `10000 × (exp(log_return_bps / 10000) − 1)`, then subtract `10000 × FamaFrench_RF_daily_simple_decimal`. Six independent factor simple returns are each multiplied by `10000` and never differenced as Treasury yield levels. Do not include RF as a seventh risky factor.

**Joint model:** `r_asset_simple_bps – RF_bps = intercept + β_mkt × (Mkt–RF)_bps + β_smb × SMB_bps + β_hml × HML_bps + β_rmw × RMW_bps + β_cma × CMA_bps + β_mom × Mom_bps + error`. The six slopes are dimensionless return-bps-per-factor-return-bp descriptive exposures, NOT identified economic event-shock effects.

**Frozen rolling design:** 378 matched historical observations per training window; 63 subsequent dates held out; advance 63 observed days per iteration. Always match exact source observed dates. A full seven-regressor multivariate OLS (intercept + 6 factors) with Newey-West HAC(5) sandwich training-only uncertainty. Normalize only the training data for numerical design condition screening, with maximum condition 1000; calculate slopes in raw economic units. Reject incomplete or singular windows. Fit a separate training-only market-factor/intercept baseline and compute `heldout_r2_vs_market = 1 – full_holdout_squared_error / market_only_holdout_squared_error`. This comparison uses **contemporaneous observed factor values** and retrospective source histories; it is **not** a tradable predictive or original historical PIT investment backtest.

**Stability flags** are prespecified research triage, not permission to delete observation dates:

- Adjacent exposure instability: Euclidean change of all six beta slopes / `max(previous beta norm,0.25)` exceeds `0.5`; flags a potentially material change in style/market sensitivity.
- Poor comparative holdout: full six-factor held-out squared error is >`1.25` times the training-fitted market-only comparator on identical dates. The metric does not validate tomorrow's returns or real-time event impacts.
- Historic adjusted-close daily move flags: count source observations with >0.25 absolute log-return; **do not** automatically discard or winsorize them without independent original-price and corporate-action evidence.

### Actual first backfill results

| Measured research output | Count/measure |
|---|---:|
| USD securities with fitted rolling regressions | **48** |
| Independent 378-train/63-heldout security-window models | **958** |
| Multivariate factor coefficients (6/window) | **5,748** |
| Windows showing material adjacent factor-beta movement | **59** |
| Windows with poor relative holdout error | **36** |
| Windows containing source-flagged large security move | **65** |
| Median heldout R² vs contemporaneous market-only | **0.01815** |
| Duplicate ticker/window or ticker/window/factor keys | **0** |
| Independent original PIT or released institutional risk betas | **0** |

These results are useful for **risk-estimator instability triage**, not a model committee approval. Overlap of instability, outlier and poor holdout windows is possible; counts must not be added as distinct model failures. The selected 48-security universe is not survivorship-corrected and the retrospective source files may contain hindsight adjusted prices and revised factor portfolios. A structural-break estimator, liquidity state, asset classifications and independently validated model basis must be predeclared before any production gate can clear.

MotherDuck versioned tables: `lab_ff6_rolling_beta_windows_v1`, `lab_ff6_rolling_beta_coefficients_v1`, `lab_ff6_rolling_beta_builds_v1`. Original price and FF input tables, and the earlier 288 whole-sample FF6 coefficients, are not overwritten. Provenance: pinned source Git SHA, script SHA256, build_id and per-window training and heldout dates.

## Original price, duplicate FX and event–economic evidence

Producer: `lab/phase1_independent_evidence_requirements.py`; MotherDuck Flight `eventrisk-lab-original-source-evidence-requirements` (`2b914d71-a9ef-436f-98e0-dba961f16c49`). Immutable requirements table explicitly leaves evidence_uri, content SHA256, publication/version clock, permitted-use documentation, analyst identity, independent second reviewer, approvals and certification values **NULL/FALSE** until actually provided by authorized independent professionals.

| Case category | Cases | Specific requirements |
|---|---:|---:|
| Abnormal historical adjusted-security-price moves | **12** | **48** (four per case) |
| Conflicting original FX quote source records | **4** | **12** (three per case) |
| Proposed event → economic channel → factor review cases | **97** | **388** (four per case) |
| **Total** | **113** | **448** |

**Independent price reconstruction:** obtain security permanent ID/primary exchange/currency, original trade/day-close and original first-source timestamp, as-of corporate-action split/dividend history and adjustment methodology, second licensed independent quote and first reviewer/second reviewer signoff. A historical 25% price move may be a genuine economic event rather than a split or bad value; the collection stage makes no inference.

**Independent economic pathway:** obtain first-published event article/regulatory/agency record and checksum, mechanism and sign with dated analytical citations, factor original rate/price observed and first-published times, contemporaneous expectation/consensus if a surprise effect is asserted, alternative explanations, vendor usage rights and two independent signed decisions. A proposed mapping or quote timestamp from a warehouse receipt is not permission to release a causal effect.

Source requirements table: `lab_independent_evidence_requirements_v1`; manifest: `lab_independent_evidence_builds_v1`. There are **zero** complete reviewed source records and **zero** approved event impacts in this first version. The authenticated research API serves only missing requirement descriptions and aggregate counts; not original copyrighted vendor documents or unapproved betas.

## What clears release gates

Research-completeness checks (958 rolling windows and 448 evidence requirements) may pass, but two newly separate institutional requirements still block: (i) no unresolved materially unstable rolling beta/holdout models under an independently approved selection and regime methodology; (ii) signed original evidence records with preserved source bytes/content hash, actual first-published clocks, usage rights and dual analyst/model-risk review. **These gates must remain blocked until the required evidence exists**, not until scripts populate superficial review-state strings.

[Overall Phase I status](PROJECT_STATUS.md) · [Closeout roadmap](PHASE1_CLOSEOUT_ROADMAP.md) · [Production unblocking plan](PHASE1_PRODUCTION_UNBLOCK_PLAN.md) · [Style Factor and Beta Method](STYLE_FACTOR_SOURCE_AND_BETA_METHOD.md)