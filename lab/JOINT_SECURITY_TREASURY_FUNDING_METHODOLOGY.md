# Joint security / Treasury / funding research model

**Status: Retrospective internal research only. Not a trading signal, production portfolio risk beta, identified policy surprise, independently as-published time series, or licensed data output.**

## Predeclared regressors and units

The joint OLS is a per-security response regression with an intercept and exactly four contemporaneous regressors: SPY adjusted-close USD log return (×10,000 to bps), US Treasury **DGS2** and **DGS10** *nominal yield changes* (each 100 × difference in percent-quoted yields, bps), and New York Fed **SOFR−EFFR funding-basis change** (100 × percent-rate spread change, then consecutive-day difference; bps). Estimated beta funding units are security return bps per one bps of spread *change*. The separate comparator is SPY + DGS2 + DGS10 without funding basis, on identically selected dates.

These variables are not independent macroeconomic policy innovations, ex-ante cash-flow shocks or risk-factor premiums. All reference-rate and Treasury series were backfilled; historically original-publication clocks and corporate-action adjustment vintages have not been independently verified.

## Identifiability and validation

The producer `lab/phase1_joint_security_funding_beta.py` uses NumPy OLS on training-standardized predictors with an intercept. It rejects singular or poorly conditioned fits (standardized design condition number >30), nonfinite inputs, duplicate asset dates, source-role mismatch and spurious rights/PIT approvals. Funding-slope uncertainty uses five-lag Bartlett/Newey–West HAC with an n/(n−5) adjustment; the descriptive unadjusted 95% interval does not correct multiple testing across securities.

Each of 48 non-SPY USD adjusted-price research securities uses a chronological **70% training, 30% unchanged holdout** partition, requiring at least 600 matched dates, 400 training dates and 150 heldout dates. The prescribed `full_training` and `training_tail_exclusion` variants differ **only in training rows**: the latter omits flagged security-price moves and funding-spread changes of at least 10bp absolute size. Its same-date holdout is never trimmed. Every variant fits the controls-only model on its own training sample and measures incremental heldout skill `1−MSE_joint/MSE_controls`.

Even for a numerically estimable model, `RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL` requires positive incremental holdout skill, concordant funding-slope signs on both independent chronological training halves, and a five-lag HAC funding 95% interval not spanning zero. Otherwise status explicitly rejects for negative heldout skill, unstable sign or interval crossing zero. These are **exploratory screening criteria**, not causal identification or institutional-model approvals. Severe rank failure aborts before source records are mutated.

The immutable source-data join and source-code SHA hashes are persisted with the build in versioned `lab_joint_security_funding_builds_v1` and per-asset variant `lab_joint_security_funding_models_v1`. Every provider publication-time, adjusted-price corporate-action, vendor commercial rights and institutional-beta-release flag remains FALSE.

**Next actual release unblocks:** verified source publication/revision clock and rights; audited equity corporate actions and live as-of investable universes; independent event innovation/surprise identification; portfolio and cross-asset factors; HAC model-risk challenge; and independent production operating-control signoff.