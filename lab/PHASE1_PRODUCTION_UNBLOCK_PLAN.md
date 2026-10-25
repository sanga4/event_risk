# EventRisk Factor Lab — Institutional production unblock playbook

As of October 24, 2026. Scope: sanga4/event_risk and eventrisk_factor_lab only. The separate huimarco/event_risk legacy MVP is not a deployment target.

The source-controlled register phase1_release_unblock_register.py maps the latest release gates into measurable acceptance evidence, accountable roles and workstream gate-passing percentages. An operational green status is not independent research or data-rights approval. The latest database tables of record are lab_release_gate_history_v1, lab_release_gate_summary_v1, lab_release_unblock_register_v1, and lab_release_workstream_metrics_v1.

## Precisely what must be unblocked

| Priority | Blocker | What it means | Evidence that clears it |
|---|---|---|---|
| P0 | Scheduled current-data collection | The collectors run when triggered; that does not protect the feed from becoming stale. The old realtime market_snapshots ingest and the newer prospective capture are separate sources. | Scoped GitHub Actions secret, enabled tested scheduler, recurring fresh successful Kalshi and Polymarket runs, verified alerts, and restored or retired legacy ingest via approved migration |
| P0 | Rights and backend credentials | Railway can serve HTTP 200 on /health/live while private research endpoints remain deliberately closed. Provider permissions and scoped DB/API credentials must be separately confirmed. | Rights approval for each venue/vendor and historical source; stored MotherDuck token, API key, confirmed LAB_DB, configured LAB_DATA_RIGHTS_ACK, negative unauthenticated tests and successful authorized read |
| P0 | Market quote first-available timing | The API response receipt does not prove a price was just published by the exchange; historic backfills cannot be retrospectively called first-known. | Independently documented source quote timestamps, stored original payload bytes/hashes and as-of replay proving eligible historical first-availability |
| P0 | Factor/macro release vintages | Treasury rate observation date and today's stored value do not prove what a trader knew at an event cutoff. Daily ALFRED vintages do not certify intraday release times. | Provider-attested original economic publication and revision history, release calendars and as-of reconciliation, plus valid model shock units |
| P0 | Security and total-return source proof | 2026 backfilled adjusted Yahoo close history may incorporate later dividends/splits and universe survivor bias. Twelve large-return flags require independent review. | Permanent security IDs, ticker validity, original corporate actions, source rights, audited adjustments and reconciled exception cases |
| P0 | Economic evidence / reviewer approval | The proposed paths and 97 review cards were generated, not independently accepted as causal relationships. | Real citations, licensed evidence and publication timestamps, human reviewer + peer review, signed decisions and explicit rejected alternatives |
| P1 | Cross-asset risk factor universe | Only 18 quantified rate/derived yield factor series exist; it is not a complete equity style, FX, commodity, vol, credit, inflation and liquidity model. | Versioned source-permissioned factor returns/shocks, asset master, unit/currency calendars, source time certification and complete data contracts |
| P1 | Beta and event impact validation | 864 SPY-controlled Treasury sensitivities are retrospective same-day associations, not event response betas or portfolio exposures; 18 yield factors are correlated. | As-known input history, validated event surprise/announcement clock, independently reviewed economics, prespecified horizon, key rates/PCA/regularization, temporal holdout, robust inference and model-risk signoff |
| P2 | Operations, access, independent approval | A deployed FastAPI process is not a reviewed institutional market model or licensed redistribution service. | Positive and negative auth tests, permission inventory, observability/SLOs, backup and rollback, source freeze, legal approval and model-risk committee release ID |

## Owner tasks that cannot be completed with scripts alone

1. In GitHub repository sanga4/event_risk: Settings > Secrets and variables > Actions > New repository secret > MOTHERDUCK_TOKEN. Use a least-privilege token for the research database. Do not paste the token into chat. The prospective_capture workflow is intentionally manual-only. Enable hourly cron only after licensing, alerting and successful credentialed manual execution are confirmed.
2. In Railway, project eventrisk-factor-lab, service factor-lab-api: confirm LAB_DB=eventrisk_factor_lab and provision MOTHERDUCK_TOKEN and LAB_API_KEYS as scoped secrets. LAB_DATA_RIGHTS_ACK may only be asserted following actual vendor legal approval. Keep licensed-credit and data distribution disabled until vendor rights are confirmed.
3. Assign independent economics reviewers to the evidence queue and an independent quantitative model-risk approver; their identities and signed decision records cannot be generated automatically.
4. Secure official source original release/revision vintages, corporate-action history and any necessary third-party market data license. Merely naming an API endpoint or filling a column from revised data cannot clear the source-provenance gate.

## Engineering and measurement terminology

- Software runtime: unit tests, deployment and process liveness. Already implemented; research serving credentials are separate.
- Descriptive research: loaded historical and on-demand current data, labeled as non-PIT and not approved.
- PIT research: independent source-first-available times for market, macro, corporate actions and event graph, with model-ready as-of joins. Not yet certified.
- Institutional factor beta: actual returns versus independently defined and licensed shock/return factors, multivariate covariance, identity/units, cross-asset coverage, valid holdouts and independent model validation. Not yet approved.
- Portfolio impact: requires authorized holdings, currency, scenario source, model approval, stress and covariance. Not yet deployed.

An automatic-gate pass percentage is exactly passing automatic gates divided by total automatic gates in the latest gate build. Workstream percentages are the exact subset of those gates plus separate manual blockers, not a weighted business-progress forecast. Field structural coverage is populated-required-fields divided by required-field-rules and is not independent data certification. The prior 95% infrastructure estimate and 50% institutional-readiness estimate are informal implementation opinions; do NOT interpret them as odds of a product being approved.

The present automatic release gate definitions do not cover every eventual style, FX, commodity, credit, vol, holdings and scenario readiness control. A future green score would still require explicit product-scope review. A go-live date cannot be responsibly estimated until external owner actions and genuine time-valid evidence are in place.

## Safe work that can continue now

Run on-demand prospective capture, forward feature views, warehouse-as-of grid, review triage, and release checks. Maintain rigorous source-only append and P0 issue logs. These actions improve current research history, NOT original publication/vintage certification, independent legal rights, causal identification or model release.


## New official FX/funding cross-asset blockers (2026-10-24)

- **FX source (loaded)**: 39,088 historical ECB EUR-base reference observations, 7 pairs, sourced by actual SDMX URL/CSV content hash. These are explicitly information-only and NOT guaranteed exchangeable prices; independent historical publication and rights evidence must be collected.
- **Funding/inflation/macro feed (not loaded)**: FRED historical source endpoint timed out from MotherDuck twice. Require an accessible authorized source transport (scoped official API key/connection if appropriate), original ALFRED provider revision-history and formal native daily/weekly/monthly units before claim of ingestion. Do not assume any DFF/SOFR/NFCI/CPI/UNRATE/WALCL observation exists from this new importer.
- **Cross-asset covariance (research loaded)**: 7x7 unit-standardized rate/FX/style factor matrix and train-only shrinkage pipeline exists. **69.94% train-to-holdout relative covariance discrepancy** calls for regime-change/robustness investigations. No production portfolio risk model or VaR approval.
- **Measured release gates**: **14 of 29 automatic pass**, 15 block and four owner/manual controls remain open. Successfully materializing new research families is progress, but true time-vintage and vendor-permission gates remain blocked. Full details: [Cross-Asset Research Methodology](CROSS_ASSET_FX_MACRO_RISK_METHOD.md).


## New documented blockers and actual evidence (2026-10-24)

- **Instability from real rolling risk checks:** 17 252/63-day seven-factor covariance windows were computed on 655 strict rate/FX/style common observation dates, every window exceeding prespecified covariance-drift or heldout variance-ratio screening thresholds. *Unblock:* predeclare and validate regime-adaptive covariance/stress choices, document test windows and evaluate independent PIT/rights; independent model-risk signoff is still required.
- **Official New York Fed short history (loaded):** 250 source-effective-date SOFR + 250 EFFR observations, 498 changes; second run inserted zero duplicate source rows. *Unblock:* verifiable source as-published historical snapshots, original published-at and revisions, NY Fed data-use rights and actual announcement shock measurement. **Do not confuse first repo fetch with first official availability.**
- **Source-family gaps (measured):** 7/16 source families have data; nine named domains remain unavailable including corporate actions, executable FX, credit, commodities, volatility, portfolio, macro-surprise consensus, original evidence archive and the FRED multi-frequency feed. Every source original PIT/right approval remains FALSE. *Unblock:* actual vendor/publisher originals, authorization, versioning and second reviewer; no synthetic publication dates.
- **Required data-source operations:** renewed manual public collector brought prospective receipts to **20,334** and restored venue capture within the freshness threshold at audit time, but this does not prove scheduled collection or independent exchange quote freshness.
- **Formal acceptance:** new release-gate v1.9 has **17/35 automatic passes, 18 failures**, 4 independent manual controls open, zero production approvals. All 39 tracked automatic+manual requirements have an evidence-defined remedy. Details: [Phase I closeout request estimate](PHASE1_CLOSEOUT_ROADMAP.md).


## Rolling factor beta and original source evidence requirements — 2026-10-25

**Executed new rolling model:** 958 FF5/Mom six-factor security windows (378 train/63 held out, 63-step), 5,748 HAC5 coefficient diagnostics; 59 relative coefficient drifts, 36 poor relative heldout comparisons and 65 flagged price outlier-exposed windows. All inputs are retrospective, original corporate-action/revision history is unverified. Independent model risk must sign off on stability/regime and security selection. A user prompt cannot approve risk betas or infer causal event impacts.

**Original evidence: 448 formal requests:** 12 adjusted-price anomaly cases (48 requirements), 4 original FX quote conflicts (12), and 97 proposed event-channel review cases (388). Each requires source URI/archived content SHA, as-of published time, compatible rights, analyst rationale and second-review signoff. 0 verified and approved. Missing evidence is now queryable, not solved.

**Current release evaluation:** gate v2.0 **19/39 automatic passed**, 20 blocked, four independent/manual controls outstanding. Owner roles and required proof retained in 43-case, nine-workstream `lab_release_unblock_register_v1`. Do not change approval flags without real first-published sources, signed owner evidence and source rights.


## October 25 — issuer action provenance and covariance acceptance gap

The new vendor-adjustment source audit processed **107,149 distinct close/adjusted-close price records**, found 369 candidate source adjustment-ratio changes (51 >=200 bp) and linked all 12 flagged large-return observations without original exchange/company corporate-action verification. No major same-day adjustment-step among the 12 means it is **not justified to automatically mark those days as stock splits/dividends or erroneous**. *P0 unblock:* first-known security master/issuer ID, official split/dividend notification and amendment histories, original exchange close, vendor original adjustment revisions, independent source and reuse rights.

The new 7-factor covariance stress sweep tested six predeclared training diagonal shrinkage values: none meets a 50% holdout covariance drift criterion. Condition improves with stronger shrinkage but unseen covariance fit does not. *P0 unblock:* independently specified regime-aware covariance and tail test evaluated on untouched PIT validation, true exposure/positions and signed model-risk review.

New source & model acceptance gates are deliberately split into **two research PASS and two production BLOCK**. Gate v2.1: **21/43 PASS, 22 BLOCKED**, four manual. Unblock owner register v1.6: **47 requirements**, nine workstreams.


## Walk-forward risk and training-price uncertainty (2026-10-25 UTC)

**Executed separate models:** 656 genuinely chronological one-day seven-factor covariance score evaluations (4 fixed methods × 164 dates, strictly preceding 252-date training each); no EWMA/extra shrinkage method outperformed baseline mean loss. 500 deterministic ten-date block-bootstrap resamples remain exploratory. **P0 source/method review:** as-published factor/FX source vintages, legal source access, outlier-aware tail factor returns, regime/volatility validation on genuinely untapped known-at data, approved portfolio exposure/position source and signed model risk. Do not select model from the same heldout test.

**Security beta price-quality sensitivity:** 48 US six-factor model comparisons using identical original chronological holdout, removing historically flagged >25% adjusted price daily returns from TRAIN only for counterfactual. 8 exposed training ticker samples, **2** beta changes ≥10%, and 6 models with better same holdout fit; **zero price corrections**, issuer split/dividend as-published proof or rights approvals. P0 price-owner QA needs independently sourced permanent security identifiers, original exchange price, and first-known corporate-action adjustment versions. This analysis does NOT establish price errors or justify removing flagged days for production.

**Measured release gate v2.2:** 23/47 auto PASS, 24 BLOCKED; 4 manual controls. 51 independently accountable evidence requirements across 9 workstreams. Corporate-action source evidence and source rights remain blocking.
