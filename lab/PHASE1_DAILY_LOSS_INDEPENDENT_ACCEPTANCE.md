# Phase I: independent acceptance after daily-loss materialization

## Status and trust boundary

This validation is read-only, source-pinned and intentionally **non-institutional**. It checks stored retrospective daily predictions/losses and statistical summary arithmetic, NOT original issuer publication times, source redistribution rights, issuer adjusted-return vintages, economic identification or approved beta release.

**CLI (after an explicitly authorized producer append):**

    python lab/phase1_daily_loss_build_acceptance.py --source-commit <40-char reviewed git sha>

Requires a properly scoped MotherDuck read-only research token. The manual GitHub Actions joint daily loss workflow calls this *after* append only, making a final job success contingent on passing the independent check. It never starts a MotherDuck Flight, schedules source collection or writes a release approval.

## Independent evidence checks

- Latest original daily loss build manifest must identify the exact Git SHA, SHA256 of the checked-out daily-loss producer, original parent build ID, 48 source securities, two predeclared variants and at least 150 common heldout dates. All institutional source/legal/issuer/risk flags must remain FALSE.
- Parent build must contain original model-code/source-data SHA256 fingerprints and no release flags. The immutable original model manifest must contain exactly 96 ticker-variant models and no approved cells.
- Persisted daily loss table must contain exactly **48 × 2 × common heldout dates** records. Every ticker/variant/date identity must be unique and source-parent pinned, with no changed training cutoff or date beyond the original parent's heldout horizon.
- For every daily row independently recompute the source squared error from (actual return − stored baseline forecast)^2 and (actual return − stored joint forecast)^2. Reject altered forecasts or losses, negative/nonfinite results, source identity drift and TRUE source/PIT/release flags.
- Re-average all daily baseline and joint losses for each of the **96** security-model cells and compare to its previously persisted original parent heldout MSE. Reject different results or missing dates. All 48 assets must share the exact same date set for each training variant.
- Recreate the complete 48-column daily matrices and rerun the predeclared shared-date circular block bootstrap for BOTH variants, comparing each stored max-t critical value, 48-family pass count and cross-security aggregate CI with independently calculated results.
- Enforce the original SHA/statement and research-only status even if the numerical data appear favorable.

## Measured prerequisites and next steps

Original parent source model had 48 securities × two variants, each with 209 heldout dates, implying 20,064 records for a successful unchanged parent replay. The prior October 25 system audit showed no new daily-loss research table. Therefore this report must NOT say 20,064 records already exist or that the bootstrap produced empirical significance.

The producer's original parent estimator source SHA256 had been independently verified to match its stored original build digest. PR #55 tightened replay of all 27 parent-model source fields and PR #56 adds *post-persistence* verification so both halves of a research run can fail closed. Actual materialization still requires a scoped MotherDuck credential and an explicitly opted-in manual GitHub Actions run; compute/repository connection limitations remain external blockers.

A successful accepted retrospective bootstrap may only reject unreliable fits, never certify historical original-data PIT, event surprise causality, credit/funding source rights or institutional betas.
