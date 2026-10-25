# Phase I — Multiple testing and robust funding beta cross-variant evidence

The latest merged joint risk-factor research model fitted exactly **96** contemporaneous security funding sensitivities across **48** USD research instruments, with market SPY control and 2Y/10Y Treasury yield-shock controls. Its previous exploratory screen used 70/30 chronological return holdout, five-lag Newey–West/HAC funding-slope uncertainty and a first/second training-half sign agreement requirement, yielding **6/96** *exploratory* screen passes. No security coefficient was independently original-source certified, licensed or institutionally approved.

## Pre-registered independent diagnostic

`lab/phase1_joint_funding_familywise_audit.py` reads the original source-pinned versioned parent model build without modifying or refitting it. From the reported funding coefficient and original five-lag HAC standard error it calculates a **two-sided normal-approximation** p-value, `erfc(abs(beta / HAC_se)/sqrt(2))`. Every one of the **96** original cells, including those with negative holdout skill or unstable training signs, belongs to the **same multiplicity family**. The conservative step-down Holm familywise adjusted p-value is `max_{j<=i}((m-j+1) × p_(j))` capped at 1. Because Holm's dependence robustness applies only when constituent p-values are valid, the original HAC small-sample and historically unverified source inputs still prevent an institutional statistical-certification claim. Choosing one fitting variant after looking at its heldout skill would be invalid; therefore the whole 96-cell prespecified family is retained.

Separate **source robustness checks** pair each security's `full_training` and `training_tail_exclusion` fits while requiring **identical original training and held-out date windows**. A sign reversal is `beta_full × beta_trim < 0`; a large relative shift is `abs(beta_full−beta_trim) / max(abs(beta_full),1e−6) > 0.25`. For near-zero baseline betas the relative magnitude should be treated carefully and signed level shifts should also be inspected. All original training-only price exception flags and unusually large funding changes remain retained in the parent model's audit record; the new diagnostic never repairs prices.

At 2026-10-25 18:18 UTC, a *read-only independent check of the existing warehouse coefficients* yielded:

| Diagnostic | Result |
|---|---:|
| Previously reported exploratory original screens | **6 / 96** |
| Unadjusted two-sided HAC p-values under 0.05 | **22 / 96** |
| Holm-adjusted p-values under 0.05 | **0 / 96** |
| Minimum unadjusted p-value (normal approximation) | **~0.001410** |
| Minimum 96-family Holm-adjusted p-value | **~0.135386** |
| Security funding coefficient sign reversals between the two fits | **10 / 48** |
| Security coefficient shifts greater than 25% | **30 / 48** |
| Positive incremental heldout skill in both variants | **12 / 48** |

These values were computed in a read-only session from the latest source model build. They are not yet a new MotherDuck producer attestation: the organization had exhausted its 30 included Flight compute minutes for October 25, 2026, and the controlled producer needs to execute before its append-only tables can be described as materialized. CI unit-contract success alone is not proof of a MotherDuck Flight run.

## Persistent output and fail-closed status

When an authorized Flight can execute, it will create `lab_joint_funding_familywise_builds_v1` (source and code SHA, parent build identity, original rows hash and exact descriptive research metrics) and `lab_joint_funding_familywise_models_v1` (all 96 original coefficients with nominal and Holm p-values, signed variant changes, training-only exclusion counts and explicit reject statuses).

The new screening states are `REJECT_EXISTING_HOLDOUT_OR_STABILITY_SCREEN`, `REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING` and `RESEARCH_MULTIPLICITY_SCREEN_PASS_NOT_INSTITUTIONAL`. **No label ever authorizes trading or beta release.** Historic first-published timestamps, issuer adjustment vintages, legal rights, investable as-known universe, macro surprises and economically identified event→factor→asset causality are still missing. Multiple security observations share market and Treasury/funding dates, so 96 rows are not 96 independent shocks.

Methodological next step is an original-price and original-funding-source corporate-action/vintage evidence challenge and an independent block-bootstrap evaluation with a separate prospective holdout. Merely reducing the p-value threshold or fitting more regressions cannot cure those deficiencies.

## One-dispatch execution without MotherDuck Flight compute minutes

Use the manual source-controlled [Joint Funding Familywise Audit](../.github/workflows/phase1_joint_funding_familywise.yml) workflow. It runs its adversarial fixture tests and then appends the 96-row warehouse audit using a **privately configured, appropriately scoped GitHub Actions `MOTHERDUCK_TOKEN` secret**, with the exact checkout `github.sha` pinned to `LAB_PIPELINE_COMMIT`. The job fails without a configured secret and never suppresses independent source SQL or validation errors. The workflow is not scheduled; no recurring warehouse compute charges or unauthorized source credentials are assumed. In the absence of a verified completed action run, the numbers above remain independently queried descriptive previews **not a materialized familywise audit**.
