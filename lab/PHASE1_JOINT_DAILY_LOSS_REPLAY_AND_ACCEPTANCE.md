# Phase I — Source-locked daily paired loss reconstruction and shared-date bootstrap

**Producer:** lab/phase1_joint_daily_paired_loss_research.py

**Manual workflow:** .github/workflows/phase1_joint_daily_loss_replay.yml

**Scope:** Strictly retrospective internal research. This is not source PIT, commercial data rights, issuer corporate-action approval or institutional beta release.

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

## Why this is needed

The original 48-asset × 2-variant SPY + Treasury + funding regression parent stores per-model aggregate heldout MSE. The shared-date bootstrap from PR #53 requires the ACTUAL daily paired out-of-sample squared losses, never fabricated pseudo-observations from aggregate beta/MSE statistics. At initial design, the verified parent model records shared an original heldout period 2025-12-15 through 2026-10-15 (209 dates), but those source observations are retrospective and original publication time is not verified.

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

A successful new build is still retrospective research only. Expected based on the old parent counts: 48 securities × 2 variants × 209 dates = 20,064 daily paired loss records. Verified after actual execution on 2026-10-26 UTC: 20,064 rows exist and passed independent acceptance; see the executed milestone above.

## Genuine institutional acceptance still requires

Authentic original issuer identifiers, split/dividend and adjusted-price as-known histories, original release timestamps and revisions for Treasury and NY Fed funding reference rates, source license/rights review, a true pre-event consensus and independently known actual first-print, and original venue quote time. These prerequisites cannot be substituted by mathematically correct retrospective model replay. The shared-date bootstrap is a research rejection screen; it cannot prove causal event-to-factor-to-asset exposure, institutional model approval or tradeable PIT investment history.

Actual on-demand MotherDuck read-only replay, append, and independent acceptance are now verified above. The GitHub Actions workflow itself was not used for this load; no original issuer PIT or institutional approval is implied.
