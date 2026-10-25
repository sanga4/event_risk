# Phase I — official NY Fed funding basis and Treasury-factor holdout (research only)

## Source-level economic definitions

* **SOFR**: a secured overnight funding-rate annualized level in *percent*, published by the New York Fed.
* **EFFR**: the effective federal funds rate, an unsecured overnight annualized level in *percent*.
* **Funding basis**: `100 × (SOFR_percent − EFFR_percent)` in *basis points*. This is a *funding-market dislocation proxy*, **not** the Federal Reserve's policy-surprise instrument, a priced security factor, or a causal geopolitical event effect.
* **Changes**: `funding_basis_bps[t] − funding_basis_bps[t−1]` in basis points; `100 × (SOFR_percent[t] − SOFR_percent[t−1])` in bps. Previous date must be within 7 calendar days, so there is no arbitrary long holiday carry.
* **Treasury response**: `100 × (Treasury_rate_percent[t] − Treasury_rate_percent[t−1])` in bps, using the **18** currently active permitted factor IDs and same within-7-calendar-days guard. The two nominal-minus-real yield proxies are not official traded breakeven inflation prices.

Official NY Fed source full-history via source-controlled `lab_nyfed_rate_levels_latest_retro_v1` is already populated for 2018–2026 with **4,288 distinct effective-date/series observations**; original raw history includes 500 duplicate dates across two separate request payload archives which must not inflate independent observation count. A source quality audit confirms **zero overlapping level revisions** and detects 20 significant ≥50 bps funding-rate changes, including the 2019 SOFR dislocation.

## Identification and validation

The new independently source-controlled `lab/phase1_funding_basis_treasury_holdout.py` rebuilds the 2,138-date funding basis, identifies exactly matched same-effective-calendar-date funding and Treasury yield observations and computes two descriptive univariate feature associations for each Treasury factor: (1) funding-basis daily change, and (2) SOFR rate-level daily change. All are **contemporaneous**, fitted only on first 70% of chronologically sorted eligible pairs; the final 30% is left untouched until validation. One fit per factor × feature = **36 prespecified research tests**. There is no right to interpret these coefficients as tradable, as a counterfactual event effect, security betas, structural Treasury yield forecasts, macro surprise response or institutional portfolio risk estimate.

A **deliberately impossible next-effective-day rate change** provides one aligned unavailable-future-feature placebo per model, fitted on the identical training rows and evaluated against the identical held-out response dates. A placebo with comparable or better skill signals potential time confounding or spurious contemporaneous structure; it must never enter a live feature feed. Test skill is `1 − mean_test[(y − fitted)^2] / mean_test[(y − train_mean)^2]`, allowed negative, and all heldout predictions use coefficients/mean fitted from training **only**. The source gate requires ≥1,500 distinct NY Fed matched effective days, 18 valid factor families, at least 450 independent paired model dates, 18 months, 300 train/120 heldout dates, zero duplicated factor/feature/date keys, finite variances, and full linked NY Fed source-vintage checks. No optimization on the heldout data, no p-value/FDR claims from 36 correlated outcomes, and no approval based on a favorable placebo comparison.

The 2018–2023 funding history extends beyond the current Treasury factor panel and is kept for future empirical coverage and issuer-level funding-risk research; it cannot create nonexistent historic Treasury observations. The overlapping Treasury panel currently covers 2024–2026; a previous read-only audit found 701 joined dates with 12,600 fully paired factor/day source changes, before the additional next-date placebo filter.

## Persisted research artifacts

The source-only `lab_funding_basis_levels_retro_v1` is an **append-only** per-build table with actual SOFR and EFFR percentages, basis in bps, previous rate day, observed rate-level change and the two official source JSON hashes, plus first-seen warehouse retrieval timestamps. Latest-build-only `lab_funding_basis_levels_retro_latest` view prevents counting reruns as independent rate observations. `lab_funding_treasury_holdout_builds_v1` is a pinned-SHA, script-hash, method/coverage acceptance manifest. `lab_funding_treasury_holdout_models_v1` records 36 per-factor-feature train/test windows and purely exploratory same-day and future-feature placebo test skill.

All independent `first_published_at`, licensed external redistributability, policy-surprise identification, *security* beta release and institutional use flags remain **FALSE**. These technical research rows must not be joined to historical event information as if past market participants knew the values before the issuer's first public publication. A Treasury factor change is a market outcome, not an equity asset return, and a SOFR basis response is not a security beta.

Outstanding gates include original issuer publication timestamps and revision vintages, FRED macro API credentials and calendar surprises, commercially licensed credit/FX/volatility, cross-asset adjusted price/portfolio data, independent event surprise definition, temporal research power and model-risk approvals. The formal 47-gate institutional release score does not advance from a statistical pilot alone.

## First executed and independently queried warehouse build — October 25, 2026 UTC

MotherDuck Flight `eventrisk-lab-funding-basis-treasury-holdout` UUID `6ffcf071-d059-4f30-b321-cb1eaabd30eb`, version 2 run 2 SUCCEEDED (exit 0). Its source SHA was `2c62b08b0650847decd7b91f74429686da3013d1`, build `phase1-funding-basis-treasury-retro-v1.0.0-20261025T055624943162Z`. The initial prototype failed a DuckDB reserved SQL alias (`months`) and a float-floor test boundary, both corrected before any source dataset was written. Full GitHub CI passed **258** Phase I Lab tests and the three other workflows.

The append-only source-native funding panel has **2,138 distinct SOFR–EFFR rate-effective dates** (2018-04-02 to 2026-10-22), **2,137 valid consecutive source-day changes**, and no independently approved publication/rights flags. Observed source spread range is **−15 to +295 bps**. The research fit has 18 factors × 2 prespecified features = **36** models, each on **699** distinct aligned dates, **489** train and **210** heldout. Outcomes are Treasury nominal/real/proxy changes in bps, not security excess returns.

| Contemporaneous research feature | Test sets with positive heldout skill | Future-feature placebo with positive heldout skill | Mean heldout skill | Mean placebo skill | Best heldout skill | Best placebo |
|---|---:|---:|---:|---:|---:|---:|
| Daily SOFR−EFFR basis change (bps) | 5 / 18 | 13 / 18 | −0.00139 | +0.00057 | +0.03832 | +0.00642 |
| Daily SOFR annual-rate level change (bps) | 11 / 18 | 9 / 18 | +0.00194 | −0.00066 | +0.02421 | +0.00892 |
| **Total** | **16 / 36** | **22 / 36** | — | — | — | — |

The highest single same-day test improvement is about 3.83% relative squared-error improvement versus the fixed training-mean yield shock; this is **one nonselected research diagnostic among correlated factors**, not an event or asset beta. The impossible future-date funding placebo is positive in **22/36**, including 13 of 18 basis-change models. Even a high score cannot make unavailable future values tradable, prove monetary policy identification, or override original publisher first-published-at, source rights or institutional approvals. No formal institutional release gate was automatically altered by this experiment.

