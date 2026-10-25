# Phase I — Source-locked daily paired loss reconstruction and shared-date bootstrap

**Producer:** lab/phase1_joint_daily_paired_loss_research.py

**Manual workflow:** .github/workflows/phase1_joint_daily_loss_replay.yml

**Scope:** Strictly retrospective internal research. This is not source PIT, commercial data rights, issuer corporate-action approval or institutional beta release.

## Why this is needed

The original 48-asset × 2-variant SPY + Treasury + funding regression parent stores per-model aggregate heldout MSE. The shared-date bootstrap from PR #53 requires the ACTUAL daily paired out-of-sample squared losses, never fabricated pseudo-observations from aggregate beta/MSE statistics. Current verified parent model records share a common original heldout period 2025-12-15 through 2026-10-15 (209 dates), but those source observations are retrospective and original publication time is not verified.

## Exact source/model replay

**Critical PR #55 hardening:** The first daily-loss producer implementation compared the funding beta, its HAC SE and aggregate forecasting skill, but did not compare every persisted SPY/Treasury slope, the original full-design condition number, both training-half beta diagnostics, the exact training-tail exclusion/heldout exception counts, and the original source estimator's byte digest. Those omissions were discovered during post-merge engineering review. The revised replay now matches **all 27 non-approval parent model fields per each of 96 cells**, plus the original estimator's SHA256 from its persisted source-build manifest. Any mismatch rejects the new paired loss build before writes. This is a tighter software/source lineage standard, **not** historical first-publication or corporate-action verification.


The script fetches the latest original parent model manifest, original source market/rate/funding rows, and all 96 original fitted model records using the inherited source-controlled SQL. It recomputes an exact SHA256 of the original source-row sequence and rejects if that is not identical to the SHA256 saved at the original parent build. Any updated issuer price, funding value, source vintage, date alignment or parent model should be independently rebuilt rather than silently accepted.

For all 48 × 2 predeclared security training variants it independently refits the original multi-factor model, validates every source identity, training fit count, holdout cutoff, funding slope, HAC standard error, benchmark MSE, joint MSE and incremental skill against the parent append-only output. For a fixed security and variant, the baseline controls SPY + Treasury 2Y + Treasury 10Y, while the joint variant adds the SOFR-minus-EFFR funding basis. Both predictors are fit only on the identical original permitted training dates; heldout actual returns are never included in training.

The producer next reconstructs true daily paired heldout return forecast errors in basis points squared, verifies same dates across all 48 securities, and applies the joint common-date bootstrap with a prespecified 10-observation block, 500 resamples, seed 20261025 and simultaneous 48-security max-|t| intervals. Neither variant is chosen post-hoc using holdout performance.

## Default mode — no source writes

After configuring a scoped read-only MotherDuck credential and an exact 40-character Git SHA, run the script with LAB_RESEARCH_SCOPE=internal-only and LAB_PIPELINE_COMMIT set. It produces only console research summary JSON (no market records) and performs source SELECTs plus temporary SQL transformations. The script does NOT append default research output, run a MotherDuck Flight, schedule ingestion or grant approvals.

## Explicit opt-in research append

For authorized appends, use GitHub Actions > Phase I source-locked joint funding daily holdout losses (manual), select append_research_records=true, and configure secret MOTHERDUCK_TOKEN. Default operation is read-only. Direct local execution requires --append-research **AND** LAB_RESEARCH_WRITE_ACK=confirmed.

After complete source replay validation, the script atomically appends:
- lab_joint_funding_daily_loss_builds_v1 — Git source, parent build, counts, source-PIT and legal/approval FALSE;
- lab_joint_funding_daily_paired_losses_v1 — immutable security/variant/date actual return, two forecasts, squared losses, four distinct false institutional source/release flags;
- lab_joint_funding_shared_date_builds_v1 — 48-family simultaneous research bootstrap summary for each of two predeclared variants.

A successful new build is still retrospective research only. Expected based on the old parent counts: 48 securities × 2 variants × 209 dates = 20,064 daily paired loss records. Verify actual completeness and final source counts after a real completed run rather than assuming these records already exist.

## Genuine institutional acceptance still requires

Authentic original issuer identifiers, split/dividend and adjusted-price as-known histories, original release timestamps and revisions for Treasury and NY Fed funding reference rates, source license/rights review, a true pre-event consensus and independently known actual first-print, and original venue quote time. These prerequisites cannot be substituted by mathematically correct retrospective model replay. The shared-date bootstrap is a research rejection screen; it cannot prove causal event-to-factor-to-asset exposure, institutional model approval or tradeable PIT investment history.

The source controls and tests are committed, but no live GitHub Actions run, warehouse append, MotherDuck Flight v2 success or statistical result on the real daily loss matrix is claimed until verified.
