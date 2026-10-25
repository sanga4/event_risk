# Phase I — Shared-date, 48-security holdout uncertainty and familywise risk

## Objective and measured reason for this control

The previous joint funding beta model fits 48 USD research securities with the SAME market SPY, Treasury 2Y/10Y and SOFR-minus-EFFR macro shock dates. Each has a 70/30 train/holdout split, but 48 prices reacting to one funding announcement do not make 48 independent macroeconomic shocks. A marginal per-security Newey–West SE or p-value—even Holm-adjusted—cannot repair the common-time dependence without a robust repeated-date/cluster uncertainty diagnostic.

The new pure method is lab/phase1_shared_date_holdout_bootstrap.py. It requires EXACTLY 48 ordered unique non-SPY asset IDs, an identical chronologically ordered heldout date sequence of at least 150 observations, a predeclared training final day strictly before every holdout date, and paired nonnegative finite SQUARED forecast errors from the market+Treasury comparator and market+Treasury+funding joint model. It cannot reconstruct heldout *daily* forecasts from the existing stored per-security aggregate MSE fields. Actual model daily forecasts with immutable source lineage must first be persisted through a separately reviewed job; until then this method is **tested only on synthetic in-memory fixtures**.

## Prespecified simultaneous bootstrap method

Define per-security, per-date paired improvement d[t,i] = squared_loss_baseline[t,i] - squared_loss_joint[t,i] (positive is beneficial).

- Resample circular blocks of **10 consecutive observed dates**, not 10 individual asset rows. Each sampled date retains all 48 asset outcomes, preserving cross-sectional source-shock comovement. The 500 deterministic replicates use seed 20261025, and no holdout-driven choice of block length, seed, horizon or subset is allowed.
- Estimate each security's mean improvement and corresponding across-block bootstrap SE. Construct centered t deviations for each bootstrap replicate and take max ABSOLUTE t across the full 48-asset prespecified family. The 95th percentile is the simultaneous 48-security critical threshold. A research security's 95%-simultaneous lower mean-improvement bound can exceed zero only if its observed incremental forecast value survives the common-date, full-family uncertainty screen.
- Separately report the cross-security mean improvement and its 2.5/97.5-percentile circular-date-block interval; interpret this as descriptive group improvement, **not as 48 independent beta discoveries**.
- Reject degenerate baseline MSE, zero temporal variability, missing or duplicate/nonordered dates, unequal losses, nonfinite data, changed asset universes and training cutoff overlap.
- All automated output labels are RESEARCH_ONLY; no individual model or market surprise receives institutional release even if all 48 simultaneous lower bounds are positive.

The method assumes sample-date block resampling is an adequate approximation under serial dependence and a sufficiently stable source regime. With strong structural breaks, sparse events, heavy tails, unknown original source vintages, or price anomalies, even a favorable block interval is insufficient. Sensitivity and rolling later regime holdouts, issuer adjustment chronology, time-cluster placebo procedures and independent source rights reviews remain required.

## Current project state and next external execution acceptance

The most recent authenticated (but retrospective and first-publication uncertified) parent warehouse research build had 96 joint security fits, 39 positive incremental heldout variants, 6 original research screen passes, 10/48 funding-beta sign-flip securities, 30/48 coefficient shifts >25%, and 12/48 securities positive in both variants. Global 96-cell Holm read-only preview showed no adjusted p under .05. PR #52 made asset-level sign, relative shift and both-variant holdout nonpositivity binding reject gates, without rematerializing v1.1. These values do not imply shared-date bootstrap results: no daily per-model paired loss history has been ingested or independently certified yet.

For actual acceptance: produce identical-day out-of-sample predictions for ALL 48 assets and both original predeclared variants, keep original security prices/corporate-action versions and source announcements traceable, validate every prediction's training-source cutoff and publication clock, persist immutable paired daily loss records with source build identifiers, and only then pass the daily 48-column matrices into this bootstrap. Never fabricate losses from aggregate MSE numbers or use a future/holdout price to retune the model. Explicitly maintain no institutionally approved betas or portfolios until rights and independent model-risk signoff.

## Usage

    from phase1_shared_date_holdout_bootstrap import assess
    report = assess(sorted_security_ids, common_heldout_dates, train_last_day,
                    baseline_squared_error_matrix, joint_squared_error_matrix)

This function performs no I/O, writes no MotherDuck data, and cannot certify original source publication, legal rights or historical point-in-time backtesting. Synthetic unit tests demonstrate an artificial 48-asset common-date improvement and an equally artificial common-date null that must not gain 48x spurious effective-sample size.

## Release boundary

HAC(5), simultaneous bootstrap-t, chronological holdouts, FDR/Holm, shrinkage comparisons and robustness screens may only REJECT a weak research result. A green statistical gate does not establish issuer provider-clock correctness, event causal identification, trading VaR suitability, authorized portfolio positions or institutional readiness.
