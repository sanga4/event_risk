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
