# EventRisk Preview — independent engineering handoff

**Project:** EventRisk Engineering Preview (research-only), standalone subfolder \`preview/\` on GitHub feature branch \`feat/engineering-preview-isolated\` in \`sanga4/event_risk\`. This is a complete Git branch copy of the previous institutional repository base (main at \`2c7bc00bb71c6892d910459558679354b74015b2\`) rather than a second GitHub repository: **main and the old services have not been changed or redeployed**.

**Railway:** Separate private-project dashboard \`eventrisk-engineering-preview\` (project \`9e4ecad7-c78e-4427-923f-9f4ecca2cae9\`, service \`eventrisk-preview-web\` \`15f6674d-0ddd-4f1d-b156-a131b379beb6\`, environment \`ff3f3d7d-111d-4bb9-832d-c4baed77a101\`); git source \`sanga4/event_risk\`, branch \`feat/engineering-preview-isolated\`, root directory \`/preview\`. No database tokens or API credential variables are required or permitted for the demo app.

**Service URL:** https://eventrisk-preview-web-production.up.railway.app/ ; API https://eventrisk-preview-web-production.up.railway.app/api/v1/overview ; Excel taskpane https://eventrisk-preview-web-production.up.railway.app/excel/taskpane.html ; Excel sideload manifest https://eventrisk-preview-web-production.up.railway.app/excel/manifest.xml

## What is implemented

1. Standalone Python 3.12 standard-library HTTP server with static HTML/CSS/JS frontend, 5 selectable dashboard views, filterable institutional blocker ledger and descriptive research metric charts.
2. Bounded live **HTTP** JSON endpoints and Excel CSV export serving only versioned, audited **FROZEN aggregate metrics**. Not connected to MotherDuck at runtime. As-of 2026-10-26 03:30:30 UTC, with original source table/unit/limitations visible.
3. Five research-only views: system/release overview; illustrative event→economic→factor hypotheses; actual 96-fit/20,064-loss funding screen including zero valid Holm survivors; BEA/required-field evidence limitations; institutional continuation register.
4. Excel Office.js taskpane with sideloadable XML manifest and PNG icon, built to insert a research snapshot table into the active worksheet A1:F11 (or download the same Excel CSV). Excel insertion **requires actual user sideload and has NOT been tested inside an Office client**; source/static/manifest tests are in CI.
5. Offline Python HTTP/security/snapshot tests and Node JavaScript syntax checks in dedicated \`.github/workflows/verify-engineering-preview.yml\`; local run instructions in \`README.md\`.
6. Optional **SELECT-only** warehouse reconciliation script at \`scripts/reconcile_snapshot.py\`; requires user's separate, scoped MotherDuck read-only token outside code/deployment. The public service intentionally has no such token.

## Current engineering acceptance boundaries

- "Live API" means a real running HTTP application backed by a **frozen, auditable data snapshot**. Do NOT claim continuous warehouse ingestion, current vendor quote prices, freely redistributable market data or "live beta" until separately approved and implemented.
- Current source figures: 49,666 venue capture records across 12 runs / four capture dates, 893,988 event-factor co-observation rows (only two prospective factor source dates), panel v2 233,442, v4 466,884, 20,064 paired daily losses, 96 funding model fits, zero Holm-surviving beta coefficients, 135 missing mandatory fields / 255 uncertified, 10 original BEA reported values.
- Institutional release gate snapshot \`phase1-gates-v2.4.0-20261026T021002390238Z\` was 25 PASS/29 BLOCK of 54, plus four manual. Its 02:10 UTC computation **predated** the original BEA source ingestion at 03:23 UTC. Institutional release remains FALSE.
- The frozen numbers were compared using read-only live MotherDuck aggregate SQL on October 26 and reconciled; a later data change does not automatically revise the site.
- No trading, forecasting, externally licensed raw events/prices, privileged portfolio positions, original publication PIT, or causally identified economic shocks are served.

## Deployment verification checklist / acceptance

- [x] Isolated new Railway project, not old Factor Lab/MVP service.
- [x] Scoped new branch and \`/preview\` root, no source/main destructive changes.
- [x] Server process executed in Railway and \`/health/live\` returned HTTP 200 according to deploy logs on first successful release.
- [x] Dedicated preview GitHub Actions offline server, routing, manifest/security and JS syntax tests passed on first deployed commit.
- [ ] Match the **latest** Git branch SHA against the latest successful Railway deployment SHA and confirm HTML/API/Excel asset routes from the final release (do not infer from a prior successful deploy).
- [ ] Verify public HTTPS browser interaction and responsive site in an actual browser; Railway health 200 alone does not prove page UX.
- [ ] Verify Excel sideload and table insertion in an actual Office client. A valid manifest/test does not by itself prove deployment on each Excel platform.
- [ ] Verify access/rights scope if shifting beyond benign research aggregates to real vendor data.
- [ ] If authorized, set up bounded/manual refresh of reviewed aggregate snapshot with immutable source manifests and independent QA; do not silently add live MotherDuck credentials to public demo.

## User-facing sample outputs

- Homepage / overview with actual stored market, factor and release-gate counts.
- Event×factor transmission concept explorer labeled **illustrative**.
- Funded/Treasury beta validation view preserving negative results.
- Evidence/data-quality view preserving 135 gaps and unverified first-publication clocks.
- Searchable P0/P1 blocker tracker from the institutional continuation plan.
- JSON API for programmatic clients plus CSV export, XML Office manifest and functional taskpane code.

## Exact handoff for remaining institutional development

Refer to \`lab/PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md\`, \`lab/PHASE1_PRODUCTION_UNBLOCK_PLAN.md\`, \`lab/INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md\` and proposed \`lab/engineering_preview/INSTITUTIONAL_CONTINUATION_LEDGER.md\` in PR #73. Nothing in this preview resolves original venue price timestamps, BEA first-print/consensus histories, corporate actions, required vendor rights, 60 independent prospective capture days, 30 factor dates, effective event shocks, independent regression and covariance model-risk review, or human/legal authorization.

## Next continuation engineering work

1. Verify latest deployment SHA / public route smoke; fix any evidenced frontend/Office embedding issues.
2. Complete actual Excel Office sideload and worksheet insertion test when Excel client access is available.
3. Improve sample dashboards and optionally add an authorized, access-controlled incremental aggregation refresh; maintain snapshot provenance and no-distribution guarantees.
4. Freeze v1 tag/preview acceptance and document any genuine untested pieces rather than pretending those steps passed.

**Do not merge the feature branch into institutional main merely to deploy the separate Railway service.**
