# Phase I — Security response to secured/unsecured funding-basis changes (retrospective research)

This project has now loaded the 2018–2026 official NY Fed SOFR/EFFR rates, deduplicated to 2,138 dates with both rates and a funding basis `basis_change_bps` source family. It has also loaded 83,427 retrospectively collected Yahoo USD adjusted-price security log-return observations across 49 instruments (SPY plus 48 research assets). Their original Yahoo corporate-action-adjustment vintages, venue publication clocks and redistribution rights have **not** been independently verified.

The new source-native `lab/phase1_security_funding_exposure_retro.py` evaluates whether the *contemporaneous* daily change in the SOFR–EFFR rate spread (in basis points) explains residual USD security adjusted-price log returns beyond a same-day SPY-market benchmark. **This is not a forecast, a monetary policy event surprise, a structural causal exposure, an approved asset beta, or a portfolio risk value.**

## Exact estimand and controls

Dependent `y_i,t`: existing USD adjusted-close **log return × 10,000**, in security log-return bps. Control `m_t`: SPY USD adjusted-close log return × 10,000. Feature `x_t`: `basis_change_bps` = day-on-day change of `100 × (SOFR_percent − EFFR_percent)`, source effective date matched to security observation calendar date. SOFR/EFFR rate levels are annualized percent quoted, not daily total returns.

Fit by Frisch–Waugh–Lovell algebra on training dates only:

`y_i,t = intercept_i + beta_market_i × m_t + theta_funding_i × x_t + residual_i,t`.

`theta_funding` has units **security log-return bps per 1 basis-point daily funding-basis change**. It does not describe an event probability innovation, macro surprise, asset return factor price, or identified policy impulse. The market-only model is fit separately on the identical training dates and used as a fixed held-out square-error comparator.

## Temporal and outlier sensitivity design

The underlying security sample is constrained to unique ticker×date valid USD log-return records, excludes SPY as response and requires both funding and market records on that day. Split each individual ticker sample chronologically at exactly floor(70% of available dates), never shuffled. Require ≥600 matched calendar days, ≥400 original training days, ≥150 untouched held-out days, ≥18 months, finite conditional funding-factor residual variance and independent source identities. An output row per ticker is a research unit; don't confuse repeated dates for 48 instruments with 48 independent market shocks.

Two **prespecified** fit variants, both scored against the same original held-out days and unchanged SPY-only benchmark:

1. `all_training_days`: all eligible training dates, retaining real funding shocks and adjusted-price exception flags.
2. `trimmed_training_stress_and_price`: excludes **only during fitting** funding-basis changes with absolute size ≥10bp or ticker dates flagged as ≥25% adjusted-price log-return jumps. These training exclusions assess source/corporate-action and tail-state sensitivity; they are not an authorized price repair or a second opportunity to select a favorable fitted result. All held-out dates, including stress and flagged-price days, remain in both tests.

No lookahead controls are trained on test data; all means, market regressions, funding slopes, and intercepts are training-estimated. Compute *incremental held-out explanatory skill*: `1 − mean[(heldout_y − market+funding_fit)^2] / mean[(heldout_y − market_only_fit)^2]`. It can be negative and the model cannot be called a predictive trading strategy: `SPY` and `basis_change_bps` are observed **same-day in hindsight**. The benchmark itself is retrospective.

## Governance and required follow-up

The builder fails closed on duplicate source keys, unexpected ticker count or currency, inadequate calendar dates, impossible market/funding variance, source SHA lineage, price-source rights/PIT/adjustment false approvals, inconsistent tail exclusions, and incorrect train/holdout boundaries. Versioned append-only `lab_security_funding_exposure_builds_v1` and `lab_security_funding_exposure_models_v1` preserve method state and original Git+Python SHA256; there is no unapproved API endpoint or beta release. No sign coefficient/p-value significance is invented.

Even if this pilot improves on SPY-only heldout squared error, institutional requirements remain: individually certified adjusted-close corporate actions, licensing of Yahoo/vendor pricing data for intended use, independently first-published-at rate values and time-zone market cutoffs, multiple factors with economic conditioning, tail and regimelike robustness, security universe as-of survivorship, actual portfolios, model-risk review and permissioned risk serving. Independent policy-surprise dates and event innovations are required before estimating an event→funding→asset transmission model. The previously blocked 24 automatic and four manual release gates stay blocked unless independently approved evidence changes.

## First executed MotherDuck evidence — October 25, 2026 UTC

MotherDuck Flight `eventrisk-lab-security-funding-market-adjusted-holdout`, UUID `5b2225d2-ae7b-4ecc-a05b-836171ffa6a4`, version 1 run 1 **SUCCEEDED** (exit 0), source commit `831d847b4d4cbab63fbcd072255dab8bea7168f6`, build `phase1-security-funding-basis-v1.0.0-20261025T062027957092Z`. Four GitHub workflows passed, including the expanded 266 Phase I Lab unit/contract tests (8 new adversarial cases). Fully materialized **96** fit rows for **48** non-SPY USD instruments, with **1,575 to 1,693** unique ticker/funding-matched calendar dates and minimum **473** untouched holdout dates. The security price history runs from 2020, which is longer than the 2024-start Treasury-rate research panel: there is no need to limit this security-specific overlap to ~695 days.

| Research specification | Models | Positive incremental holdout skill versus SPY-only | Mean incremental heldout skill | Best individual skill | Worst individual skill |
|---|---:|---:|---:|---:|---:|
| All original training dates | 48 | 6 | −0.012717 | +0.004668 | −0.101973 |
| Training excludes funding basis moves >=10bp and flagged adjusted-price returns | 48 | 24 | −0.004171 | +0.006978 | −0.066320 |

All **48** tail-adjusted fits excluded at least one training observation; across models, **153 total ticker-date training observations were excluded**. All held-out periods are unchanged and include any adverse returns or funding shocks. The full-sample market-only benchmark is the same within security for both variants. The max +0.6978% reduction in held-out squared error is small, *not independently identified*, and does not overcome negative average incremental heldout performance. The apparent improvement after tail-trimming is a **sensitivity diagnostic**, not selection or validation of a superior live model.

All upstream original issuer publication-time flags, Yahoo/vendor corporate action vintages, commercial rights and institutional security-beta release approvals remain FALSE. The original daily matched factor is a 2018–2026 **retrieved** NY Fed reference-rate series joined to 2020–2026 adjusted security returns by economic observation date. It is not verified that the reference rate was published before the matching security market close, and the same-day model cannot become a tradable prediction without both original publication times and a proper historical availability cutoff. Its event→factor causal transfer has not been estimated or approved.

