# Phase I: independent acceptance after daily-loss materialization

## Executed and independently accepted research milestone — October 26, 2026 UTC

**VERIFIED ACTUAL WAREHOUSE APPEND AND INDEPENDENT READ-ONLY ACCEPTANCE, NOT A PROPOSAL.** The latest accepted retrospective joint-funding daily-loss build is `phase1-joint-daily-loss-v1.1.0-20261026T013322327429Z` from immutable Git source `8f0acd10648a9eecdfa213691ba4fafc46e31b1e`, original parent `phase1-joint-security-funding-v1.0.0-20261025T171802478028Z`, producer SHA256 `ca8fe072833427e6cdf0b8a7d6029f8e6f2573f863b03222204032fdd25cc01b`, parent estimator SHA256 `280ee147fe6d70b4b7a57cb04c6a5cb94f4ea848a8d9146adef9761a653bc83e`, parent source rows SHA256 `2b6373f916cb4221b7a704c5d73cf79aa976b812b9b02ff386baa184fc3cd060`.

- Original method source-locked read-only replay: on-demand MotherDuck Flight `25e4a973-69ad-4796-81ac-ecd2843c4f5e`, v1 run #1 **SUCCEEDED**.
- One-shot, manual-acknowledged internal research append: on-demand MotherDuck Flight `999d3436-42bf-42d0-86a5-055817aa248b`, v1 run #1 **SUCCEEDED**. Its write-ack has since been **disabled** in v2; do not repeat merely to get more rows.
- **20,064 real persisted heldout daily pairs** in `lab_joint_funding_daily_paired_losses_v1`, one versioned `lab_joint_funding_daily_loss_builds_v1` manifest, and two rows in `lab_joint_funding_shared_date_builds_v1`. Exactly **48 source securities × 2 predeclared training variants × 209 shared chronological holdout dates**, 2025-12-15 through 2026-10-15. Zero true original issuer-as-known, provider first-publication, licensed risk use or institutional beta flags.
- Independent source-stored acceptance: SELECT-only on-demand Flight `aed5f5ba-574b-4257-96dc-c15db0cb5453` v1 run #1 **SUCCEEDED** with `SOURCE_LOCKED_20064_DAILY_PAIRED_LOSS_RESEARCH_QA=PASS`. Checks source-locked estimator SHA, all 96 parent coefficients/MSE, loss arithmetic and uniqueness, source/holdout chronology, 48×2×209 rectangular completeness, independently reproduced shared-date bootstrap metrics, and all negative institutional release flags. This is an **internal retrospective calculation-integrity acceptance only**.
- Prespecified 209-date circular block bootstrap: block length 10 dates, 500 replicates, seed 20261025, 48-asset simultaneous 95% max-|t| familywise interval. Full training: **1/48 security passes exploratory familywise lower >0** (`SBUX`, mean daily bp² loss improvement +58.02778, simultaneous lower bound +1.0983 bp²), aggregate loss-improvement interval **[−333.13,+270.59] bp²** and aggregate mean **−29.46 bp²**. Training-tail exclusion: **0/48** pass, aggregate interval **[−563.39,+173.56] bp²** and mean **−167.67 bp²**. **No ticker passes under both prespecified variants**. Both aggregate intervals span zero; the economic signal is not robustly positive.
- Read-only source-pinned sensitivity Flight `2df41782-9fe5-4c73-8da1-87d3b38e8d4f` v1 run #1 **SUCCEEDED**, confirming both bootstrap variant computations and empty cross-variant familywise survivor intersection. **25 full-training and 14 trimmed variant fits** have positive raw heldout loss improvements (39/96); only **12/48 assets** have positive means in both variants. Cross-security same-date rows are NOT independent economic shocks.
- This materialization **does not** imply a verified Treasury/SOFR/EFFR original publication time, original issuer split/dividend adjustment vintage, contractual security price rights, identified causal event sensitivity, acceptable factor betas, cross-asset stress VaR or institutional beta approval. Previous executed 51 release gates: 23 PASS / 28 BLOCK, four external manual; not refreshed by this research append.

**Execution rule:** Treat the current table build and original parent as immutable. Conduct further date-regime sensitivity and original issuer/provider-vintage reviews without editing source history or enabling risk approval flags.

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

Original parent source model had 48 securities × two variants, each with 209 heldout dates, implying 20,064 records for a successful unchanged parent replay. That statement described the October 25 pre-execution snapshot; the October 26 build above now actually contains 20,064 verified daily-loss rows and both bootstrap summaries. It remains retrospective calculation-integrity research.

The producer's original parent estimator source SHA256 had been independently verified to match its stored original build digest. PR #55 tightened replay of all 27 parent-model source fields and PR #56 adds *post-persistence* verification so both halves of a research run can fail closed. The initial materialization has now completed using the manually acknowledged, Git-pinned on-demand MotherDuck Flight detailed above. Future writes still require separate authorization and an original-source audit.

A successful accepted retrospective bootstrap may only reject unreliable fits, never certify historical original-data PIT, event surprise causality, credit/funding source rights or institutional betas.
