# EventRisk Factor — Institutional Factor and Beta Methodology v1.0 (research specification)

**Status: DRAFT, NOT MODEL-RISK APPROVED.** Owner: sanga4/event_risk. Governs the separate MotherDuck `eventrisk_factor_lab` and isolated Railway Factor Lab; it does **not** alter huimarco/event_risk. No trading, portfolio risk forecasts or point-in-time backtest release are authorized.

## 1. Different objects — never conflate them

| Object | Meaning | Estimator/status |
|---|---|---|
| Factor taxonomy | 108 named economic / market / style risk factors in `seeds/factors.json` | Qualitative definitions, **not** calibrated risk-factor returns |
| Economic transmission link | A particular event may influence growth, inflation, supply chains, policy, cash flows, risk appetite | Rule-supported candidate or independently evidence-reviewed relationship, not a statistical beta |
| Factor level | Observed yield, spread, FX, commodity or style portfolio level at timestamp `t` | Requires a documented unit, source and observation vintage |
| Factor shock `ΔF` | Unit-consistent change in a **measurable** factor over a predefined horizon | Yield 100 × difference in percentage points = basis points; spread in bps; log-price changes in decimal or percentage; research styles as return spreads |
| Security beta `β_(i,k)` | Conditional sensitivity of asset i's return to factor shock k | Multivariate, exposure-specific beta requiring *asset return observations*, as-of investable factor series and controls |
| Event-to-factor response `θ_(e,k,h)` | Response of factor k over horizon h to an **identified event innovation** e | Requires an observed shock, credible counterfactual and identified announcement time; **not** the same as security beta |
| Event probability innovation `Δp` | Change in forecast probability on comparable contract definitions | Percent-points for interpretability, but cannot by itself establish a structural surprise, causal intervention or asset return |
| Portfolio factor exposure | Sum of holding-level risk exposures to defined factor shocks | Requires approved security mappings, positions, currency, dates and sign/units; not inferred from candidate event links |

A causal chain requires separately validated links: **event information innovation → economic channel → factor response → security beta → portfolio impact**. If one link is unavailable, report **UNKNOWN/UNESTIMATED**, never fabricate zero or a numerical beta.

## 2. Required source-and-data contract

A source observation has: `source_id`, `entity_id`, `factor_id/contract_id`, `observation_timestamp` (effective economic or exchange quote time), `source_published_at` (original public release, if verifiable), `retrieved_at`, `warehouse_ingested_at`, `first_available_to_model_at`, `revision/vintage_id`, `source_hash`, `license_class`, `source_timezone`, `source_status`, and `asof_eligibility`.

- **Historical backfill** may populate a retrospective fact table, never rewrite a historical `first_available_to_model_at` timestamp from an October 2026 ingestion as 2024 vintage eligibility.
- **Live captures** provide defensible API response receipt time; provider quote publication time remains **uncertified** until independently sourced.
- **Warehouse-as-of** requires `factor.ingested_at <= event.capture_received_at` **and** `factor.availability_at <= event.capture_received_at`. It proves only this internal warehouse timing, not independent provider release/vintage time.
- For truly PIT research, require validated source publication/release timestamp, first-seen capture time, revisions separately versioned, historical contract mapping known before event, and all covariates available before the model cutoff. No revised-future vintages in historical model fitting.
- Raw payload archive should include actual **response bytes**, SHA256, URL and retrieval metadata. Existing digests without archived original bytes are insufficient for independent source replay.
- Join on venue market + stable contract version, not just question text; persist cancellation, market resolution, missingness, carry-forward and stale quote flags.
- Enforce source licenses. Existing restricted ICE/BofA credit catalog entries stay inactive; `T10YIE` with unresolved terms stays excluded from the prospective licensed allowlist. Derived Treasury nominal-real yield differences are **not** market inflation breakevens.

## 3. Factor catalog build priorities

**Tier 0 — currently materialized quantitative observations:** 11 nominal Treasury yields + 5 real Treasury yields + 2 nominal-minus-real yield proxies, 2024-01-02 through 2026-10-22, 12,656 observations. All are warehouse-known only, not independently publication-vintage verified. There are zero observations for the 2 restricted ICE/BofA spreads, NFCI, or the `T10YIE` catalog item in the current factor observation table.

**Tier 1 — complete controlled market-factor data:** independently sourced Treasury nominal/real curves, risk-free short rates, inflation releases / inflation swaps or verified breakevens, liquid FX rates, WTI/Brent, gold, benchmark equities, realized/implied vol, and *licensed* credit proxies. Each has a defined daily/announcement/higher-frequency return convention, calendar, timezone, holiday policy, numerator/denominator, vintage and source. Do not apply a single price-difference formula to all factors.

**Tier 2 — equity styles and portfolio:** Fama–French factors (official portfolio-return series, documented regions, library methodology), market, size, value, profitability, investment, momentum, sector, country and optional liquidity indices. A style factor definition requires provider ID, universe, weighting/rebalance, lagged constituents and revisions; 108 taxonomy rows alone do not produce 108 quantitative return series.

**Coverage policy:** report separately **catalog size, active permitted catalog factors, factor IDs with any observations, factor IDs with sufficient PIT data, and factor IDs with estimable validated betas**. Do not treat duplicate vintages or a 190,008-row cross-product as 190,008 independent economic observations.

## 4. Model identification and equations

### 4A. Descriptive market-event comovement (research only)

For market m at date t, `Δp_(m,t)=100*(p_(m,t)-p_(m,t-1))` in percentage points, only if contract terms match and comparable verified observations exist. Per venue, an average absolute `Δp` is a **venue volatility proxy**, not an identified event shock. A same-day association:

`ΔF_(k,t) = α + b_(k,v)*mean_m |Δp_(m,t)| + ε_(k,t)`

is a historical comovement diagnostic, **not an event beta**. The current 36 OLS + 72 HAC/holdout exploratory fits use backfilled markets and revised/final factor values. Initial 72-model result: none passed BH 5% FDR, only 19/72 positive chronological test R². Retain them as labeled negative/weak baseline.

### 4B. Factor return exposures / security betas

On eligible as-of risk/return panel and **only when security prices/returns and correctly computed factors exist**, estimate:

`r_(i,t)-r_(f,t) = α_i + Σ_k β_(i,k) x_(k,t) + Γ'Z_t + ε_(i,t)`

where `x_k` are predefined **returns or shocks with explicit units** (Treasury yield *bps*, not yield percentage masquerading as equity factor returns). Use robust regression or regularized estimators only under a predeclared specification, with vintage-stable factor standardization fit on training data exclusively. Report factor universe, loadings, signs, training window, observation counts, conditioning / multicollinearity, stability/roll behavior, HAC or clustered uncertainty, holdout error, uncertainty intervals and exposure-vs-valuation interpretation.

Never interpret a raw Treasury yield-change regression slope as a security beta without an actual security return dependent variable. Distinguish equity-style returns, FX log returns and yield/spread changes.

### 4C. Event innovation and factor impact

Define `u_(e,t) = Δp_(e,t) - E[Δp_(e,t)| pre-event information]` where the expectation model is trained **ex ante** using only historically available covariates; alternatively use predeclared event surprise from official release vs timestamped consensus. With validated event announcement time `τ`, factor response:

`Δ_h F_(k,τ) = α_h + θ_(k,h)u_(e,τ) + Γ_h'Z_(τ−) + market/calendar controls + ε_(τ,h)`.

Predeclare horizons e.g. **1h/1d/5d** and only estimate those for which **both event and factor observations are genuinely available at required frequencies**; otherwise mark N/A. Overlapping horizons/market clustering require HAC or clustered uncertainty; intraday announcements require intraday factor prices, not daily end-of-day surrogates. Evaluate controls for coincident monetary releases, cross-market event overlap, and structural timing. Calendar-day same-date joins without announcement-order checks are not identification.

Only after event→factor response and security beta independently pass release gates may scenario impact be *hypothetically* approximated as `Σ_k β_(i,k) × θ_(e,k,h) × u_e`; include nonlinearities, factor covariance, uncertainty propagation and scenario conditioning. Not an expected P&L forecast by default.

## 5. Statistical and temporal validation

- Pre-register target, sign, horizon, event universe, factor list and treatment/control assignment before seeing held-out data; no hindsight selection of favorable paths.
- Train/validation/test **chronologically**, purged and embargoed for overlapping event horizons. Min span and effective independent clusters, not merely cross-product row count; report sparsity and factor availability by year.
- Null events, unrelated control factors, placebo timestamps, pre-trend and reverse-causality checks; country/region calendar and venue heterogeneity.
- Heteroskedasticity/autocorrelation-robust SE; cluster by event/question and calendar where needed; block bootstrap and covariance robustness.
- BH/FDR across **all pre-specified tested factors and horizons**, including non-significant trials; minimum effect size and stable out-of-sample directional error / calibration, not p-value alone.
- Historical PIT leakage test on **every** joined source and mapping timestamp; unit conversion and day/holiday carries; survivorship/delist and quote age; hash/replay duplicates; licensed data rights.
- A significant coefficient without independent source timing, mapping reviews or reliable OOS behavior remains **RESEARCH ONLY**. Conversely lack of significance does not imply zero risk.

## 6. Institutional release gates

1. **Data contracts and legal:** timestamped original or sufficiently independently verifiable source vintages, rights/redistribution cleared, full archive and source hashes.
2. **Economic labels:** ontology linkage with reviewer identity, evidence, source publication time, rejection control, historical known-at of the mapping, peer review.
3. **Quantitative completeness:** at least one real factor shock/return panel and actual asset return series with sufficient point-in-time history; factor family/unit/calendar approvals. Distinct eligibility by strategy and horizon.
4. **Valid identification:** event shock definition, factor response horizons, confounder protocol and independent evidence-backed causal rationale.
5. **Validation:** pre-specified temporal test and multiple-testing control, uncertainty, risk limits, known vulnerabilities, model card, independent model-risk signoff.
6. **Operation:** active scheduled ingestion with freshness alerts, scoped API credentials, access log, backups/rollback, reproducible pinned source SHAs and human production authorization.

Production exposure outputs must carry `estimation_status` = `unestimated|retrospective_research|pit_candidate|independently_validated|approved`; show full confidence/coverage rather than inventing coefficients. Existing MotherDuck institutional status **8/16 automatic gates pass**, **8 block**, **4 manual conditions outstanding** as of the last stored v1.3 run, not an institutional approval.

## 7. Backfill plan, prioritized

1. **Snapshot/archive:** preserve existing 11,101,967 historical market snapshots, 565,695 market-day observations and 2,979 venue-day features *as retrospective*, with source coverage by year/venue, missing contracts, capture source and denominators.
2. **Factor timeseries:** backfill permitted high-quality rate yields into a separate retrospective factor store with source metadata; validate row counts/dates/units against official provider, preserve revisions rather than overwrite. Inventory missing NFCI and other inactive/no-observation catalog members.
3. **Asset returns:** add versioned adjusted-close/total-return security returns, FX and commodity prices with corporate actions, trade calendar and capitalized metadata, and licensed style portfolio returns. **No numerical security betas until these exist**.
4. **Official release calendar:** ingest original release/published-at and revision vintages for Treasury/FRED/macroeconomic series, and venue quote source timestamps. Existing backfills cannot magically become contemporaneously known.
5. **Daily pipeline:** capture and reconcile new observations, join as-of, produce review queue and quality report, generate event shocks and betas only once minimum PIT and governance gates pass.

## 8. Deliverable ownership and review

Methodology version and model changes are Git SHA pinned under **sanga4**. The separate qualitative `FACTORS_METHODOLOGY.md` remains the 108-factor graph taxonomy contract; this document governs quantitative research, betas and institutional interpretation. No edits to huimarco or its production MVP. Any transition from research estimate to institutional beta requires a documented independent approval and release commit, never a script setting an approval bit.


## October 24, 2026 — security-price inventory correction and retrospective rate-beta pilot

A live MotherDuck audit found **107,157 already loaded security_prices observations for 63 symbols**, fetched on October 17, 2026, contrary to the earlier assumption that there were no security prices. A new [research pilot](SECURITY_RATE_BETA_RESEARCH_METHOD.md) has now backfilled 83,427 USD security adjusted-price daily log returns, 12,618 daily rate-factor shocks and 864 SPY-controlled *retrospective* rate sensitivities. There are 130 BH q<0.05 coefficients, 414 positive same-day holdout relative to market-only, and 49 satisfying both exploratory screens. **Zero are PIT/rights-verified, model-risk-approved or released**. This does not invalidate the original distinction between *security rate sensitivity* and *identified event-to-factor impact*.

The exercise does **not** validate original vendor publication timestamps, `yahoo` license rights, adjustment vintages, historical constituent survivorship or return-currency conventions. Four duplicate ticker-days were deterministically collapsed; 12 large-return events are flagged for review. It deliberately excludes FX-only/non-USD instruments and the SPY benchmark as its own response. Same-date factor changes and SPY returns in a test set are contemporaneously known ex post, **not a tradable ex-ante forecast**. Multivariate licensed factor models and genuine asset total-return/PIT validation remain mandatory for production.


## October 24, 2026 — U.S. six-factor equities research extension

For style factors **do not use the Treasury yield difference formula**. We now have official U.S. Kenneth French daily five-factor + RF and momentum historical research snapshots (seven IDs / 121,598 values through 2026-08-31) ingested with source file checksums, dated retrieval and all rights/PIT flags FALSE. A separate six-loading security model matches dollar-adjusted security price data, uses **simple USD security excess return**, as-of-unverified *same-day* style returns, multivariate HAC(5), original-unit exposures and global BH correction over all 288 tested coefficients. First fit: 48 securities; 151 exploratory slopes pass q<.05, 27 models improve on market-only *contemporaneous* holdout, 9 model samples contain outlier flags. These **are not source-time-vintage verified, legally cleared, independent security risk betas or event responses**. The official source documents a CRSP FIZ→CIZ transition and historical revised data; archive retrieval cannot attest true past value publication time. See [Style Source and Beta Method](STYLE_FACTOR_SOURCE_AND_BETA_METHOD.md).
