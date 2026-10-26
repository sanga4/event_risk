# Preview MVP — independent Analyst Beta v1

**Identity:** EventRisk `Preview MVP` — *not* institutional Phase I.

This application lives under `preview_mvp/` on the isolated `feat/preview-mvp-analyst-v1` branch of `sanga4/event_risk`. Its own Railway project is `eventrisk-preview-mvp`, project ID `c45ea63e-d1fb-456e-bf60-6713aaf6a741`. The institutional Phase I main branch, original factor-lab API and prior engineering preview Railway service are unaffected.

## Goal

Build an analyst-usable, research-only **direct server-to-MotherDuck** web API with paginated discovery of the actual graph, the full public catalog of 543 security references and 108 qualitative factor definitions, available source-observed economic time series, diagnostic regressions, and data lineage. Preserve the original compact Marco Hui Event Risk Graph design while adding on-click factor and model analysis.

## Warehouse reality independently verified 2026-10-26

- `graph_nodes` has **41,058 rows**; unique named types include **4,907 question**, **11,096 proposition**, **11,128 market**, **1,478 entity**, **543 security**, and **34 factor** node IDs. Counts are different semantic grains and should NOT be called distinct events.
- `graph_edges` contains **169,996 records** with temporal graph validity/versioning.
- `lab_factor_catalog` has only **22** warehouse rows while Git `seeds/factors.json` lists **108** factor definitions. Catalog definition != observed factor time series.
- `lab_joint_security_funding_models_v1` has **192 model rows** across 48 unique tickers and versions; earlier accepted research consists of a **96-model 48×2 specific build**. Never conflate the 192 all-build rows with 192 unique approved fits.
- `lab_live_market_latest_v1` has **4,889** latest captured market records; the collector covers a configured *sample*, not all worldwide prediction-market contracts.
- Prospective captures, release and factor data have known original-provider first-publication, rights and point-in-time gaps. Present *research*, not validated causal impacts.

## Architecture and rights boundary

- The **browser never talks directly to MotherDuck** or receives its bearer token.
- Public endpoints offer *only repo-published metadata* and the frozen source-audited demonstration graph. The backend can serve live queries from **`eventrisk_factor_lab`**, but only when an owner sets a **scoped READ-ONLY `MOTHERDUCK_TOKEN`** privately in this independent Railway service. We do NOT copy any Phase I credential.
- Dynamic database endpoints additionally require a secret **`PREVIEW_MVP_ANALYST_KEY`** server-side and a `X-Analyst-Key` header; frontend login input is not a substitute for an institution's SSO. Use narrow production permissions and replace single key with per-analyst SSO before broad rollout.
- Exact provider quote and question content, or derived restricted datasets, remain locked behind `PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED=true` and `PREVIEW_MVP_DERIVED_RESEARCH_APPROVED=true` respectively. These are **owner contractual entitlement assertions**, not institutional beta approval flags. These must remain disabled absent verified permitted use. Do not set them just to make demo graphs seem populated.
- Strict SQL table/name/parameter allowlists. No user-defined arbitrary SQL, database writes, raw bytes/packet blobs, bulk export or credentials. Cursor-based pagination limits responses, timeouts, snapshots, caching and API budget controls should be hardened before open public deployment.
- A successful HTTP deploy alone is **NOT** proof of a production MotherDuck connection. Verify `/api/v1/runtime` under auth after adding a real scoped credential and exercise the source queries. Do not claim 'fully connected' when `db_connected=false`.

## Milestone roadmap

1. **Isolation and original-style front end:** independent Railway project, separate feature branch and `preview_mvp` application; preserve Phase I and earlier preview. Ship a complete 543-security/108-factor public reference catalog and clear source-labeled initial event graph.
2. **Read-only, authenticated warehouse adapter:** factor observations, current graph paginated node/edge search, allowed model regressions and coverage counts; fail closed if token, authorization or source rights are missing.
3. **Analyst model desk:** choose a ticker and factor, render original regressions/coefficient/HAC/CI/holdout with model/version provenance, sign-stability warnings and source caveats. Never invent event beta estimates.
4. **Economic transmission coverage:** version 15–25 canonical channels and maintain mapping review status, original sources, valid times and human override. Normalize duplicated propositions to question-level event families.
5. **Excel and case-study reporting:** side-panel one-click fact/evidence export of entitled data, formal dated report templates for funding stress, trade restrictions and inflation; SSO and source-approved distribution boundaries.
6. **Operations:** approval process for market redisplay, least-privileged service identity, per-user auth, request limits, caching, monitoring, error budget, regression QA, and independent external browser + Excel acceptance.

**Launch criterion:** connected scoped MotherDuck token, actual authenticated API tests, compliant permitted dataset classes, usability QA, and permission-controlled access. If unmet, remain *deployed preview / database connection pending*, not analyst-ready production.

## Separate Phase I

Do not modify original `main`, `eventrisk-factor-lab`, canonical panel builds, source producer Flights, governance gate fields, or merge Preview MVP into them. Institutional original provider PIT and source licensing approval remain separate milestones.

## Live preview and implementation status (2026-10-26)

**New Preview MVP site:** https://preview-mvp-analyst-production.up.railway.app/

**Separate GitHub review track:** https://github.com/sanga4/event_risk/pull/75 (DRAFT, base is `feat/engineering-preview-isolated`; never merge into Phase I `main`). GitHub creation of a completely separate repository is not exposed by the installed GitHub connector, so isolation is via a dedicated feature branch, source root, CI workflow and entirely separate Railway project. If repository-level independence is required, create a new GitHub repo and move `preview_mvp/` there as a standalone root.

### What an analyst can use now

- Browse the **543-security** and **108-qualitative-factor** public repository references and **22** explicit economic-mechanism hypothesis categories, and inspect the original-source qualitative seed exposures in the central graph.
- Explore graph node connections, searchable company/factor catalog and source notes in the original light-mode three-pane layout. Canvas rendering caps dense neighborhoods to keep it responsive; search is over the whole catalog, not just rendered nodes.
- Inspect `GET /api/v1/runtime`, `GET /api/v1/catalog` and `GET /api/v1/graph` without source credentials. They are **public reference data**, NOT active MotherDuck queries.
- The server implements parameterized, read-only `/api/v1/research/coverage`, `/events`, `/graph-nodes`, `/graph-neighbors`, `/factor-catalog`, `/models?ticker=...` and `/factor-series?factor_id=...`, but **live data is NOT connected by default**. The site will show a setup-required state until newly scoped credentials are provided and tested.

### Exact secure connection setup

In **only** the new Railway project `eventrisk-preview-mvp` → service `preview-mvp-analyst` → Variables, configure:

1. `MOTHERDUCK_TOKEN` — a **new, dedicated, least-privileged SELECT-only** MotherDuck credential restricted to entitled tables/columns or separately reviewed research-safe views. Do **not** reuse Phase I's production/ingestion writer credential.
2. `PREVIEW_MVP_ANALYST_KEY` — a new secret, random 32+ byte analyst research key, not committed to Git and not published to the homepage. This temporary shared-key scheme is for controlled beta testing only; add real per-analyst SSO before external analyst access.
3. Keep `PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED` **unset/false** until the provider's market/question redistribution terms and your users' research rights are independently confirmed. Real warehouse event/question search and source graph neighbors fail HTTP 403 meanwhile.
4. Keep `PREVIEW_MVP_DERIVED_RESEARCH_APPROVED` **unset/false** until derived security regression/factor-observation data publication is licensed and reviewed. Regression/factor-series routes fail HTTP 403 meanwhile.
5. Deploy, visit `/api/v1/runtime` and confirm `direct_database_queries_enabled:true`, then use the analyst key in the website's left panel and check **actual successful live COUNT query** through `/api/v1/research/coverage`. Successful configuration alone is not proof of a connected query. Any schema mismatches should fail closed and be remediated against the independently read-only warehouse catalog.
6. For public access to individual source market questions and derived research, use separate entitled datasets, real analyst accounts, rate limits, audit logs, usage policy and model disclaimers. Merely flipping a flag is not a rights review.

### Separate acceptances

Source-controlled GitHub Actions: `.github/workflows/verify-preview-mvp.yml` executes source-catalog parity, 543/108 definitions, exact example Taiwan→TSM 0.9 prior, node/edge referential integrity, denied unconfigured DB queries and denied source/derived routes; checks Python and JavaScript syntax.

Runtime deploy success and `/health/live` are **not** equivalent to a live database acceptance test or a fully licensed beta launch. Keep separate release-status labels for `DEPLOYED_PUBLIC_CATALOG`, `LIVE_DB_CONNECTED`, `ENTITLED_ANALYST_DATA`, and `INSTITUTIONAL_APPROVED`.


## Analyst Beta v1 next workbench milestone — October 26 2026

**Graph:** https://preview-mvp-analyst-production.up.railway.app/

**Analyst use-case desk:** https://preview-mvp-analyst-production.up.railway.app/lab

**Dated verified coverage:** https://preview-mvp-analyst-production.up.railway.app/api/v1/inventory

**Excel add-in manifest:** https://preview-mvp-analyst-production.up.railway.app/excel/manifest.xml

The separately deployed research desk offers eight clearly hypothetical economic
event scenarios. Each displays an illustrative economic-transmission chain, related
factor definitions and published seed entity/security relationships. The public
case-study dashboard never fabricates event effects, probabilities, regression
coefficients, significance or fitted performance.

Rights-gated research desk functions load the original SPY/2Y/10Y/funding
security-model variants, Newey-West HAC standard errors, confidence intervals,
heldout metrics and global Holm familywise audit for any fitted ticker.
Source-observed Treasury factor time-series charts are also rights-gated.
Analysts can print the workbench or export ONLY truly retrieved entitled results
to CSV. Empty or unentitled sources appear as unavailable, not synthetic data.

Read-only aggregate inventory shows 4,907 distinct graph question IDs, 169,996
versioned graph-edge records, 18 independently source-observed factor series,
12,764 factor observations on 703 observed dates, 48 funded-regression tickers,
96 original 48x2 family fits, and ZERO adjusted-Holm surviving funding candidates.
The inventory is dated as 2026-10-26: not a continuously live provider feed.

The distinct Office.js sideload add-in imports all 543 securities, 108 published
qualitative factor definitions, 22 hypothesis-only economic channels, graph
analyst-prior links, actual audited source inventory and formula-driven graph
connectivity worksheets. Source regressions and factor observations require
independently approved data-use permissions and actual live warehouse auth.
The Excel add-in has code/HTTP/syntax acceptance but must still be installed
in real Excel to verify the Office-host worksheet import end to end.

Source graph SEARCH and neighbor endpoints now enforce latest asserted-only
temporal record semantics and exclude the withdrawn 'retract' operations.
Original warehouse versions are never silently treated as simultaneous active links.

Not yet unlocked: new least-privilege server-only MOTHERDUCK_TOKEN, an analyst
access key, independent authorization for source market-question redisplay and
derived research coefficient/series distribution, actual successful dynamic
query acceptance from the Railway service, per-analyst SSO and operations hardening.
Do not copy the Phase I writer token, flip rights flags without permission, or
represent a successful static deployment as connected investment-data readiness.

Manual source QA: verify preview_mvp/tests/test_app.py and
preview_mvp/tests/http_smoke.py under the dedicated Preview MVP workflow;
add actual browser and Office client testing prior to a broader analyst release.

Both the institutional main branch and the older engineering-preview service
remain separate and unchanged by this Preview MVP feature branch.

## Marco-original homepage and manual Event Attribution (Oct 26)

The default `/` route now serves `preview_mvp/marco.html`, which reuses the **exact original Marco Hui CSS** from `web/index.html` and the same header, tabs, resizable 3-column panels, vis-network graph, shapes, type colors, labels and right-hand detail interaction. New feature-specific CSS is appended below the original unchanged stylesheet at `preview_mvp/assets/marco.css`. The previous prototype UI remains available at `/previous-explorer` for rollback comparison, but is no longer the homepage.

The website does **not** silently bring over old sample market odds from the legacy Graph MVP: Preview MVP shows the full public catalog of 543 company/security references, 108 factor definitions, 22 illustrative economic channels and eight research event scenarios from its own `/api/v1/catalog` and `/api/v1/graph`. Real provider questions remain rights-gated via `/api/v1/research/events`. The pinned original vis-network library (v9.1.9) loads from the same external unpkg.com library originally used by Marco's app, under a route-restricted CSP; standard desktop browsers need access to that library. All other application code is first-party.

### Manual portfolio Event Attribution

From the original-style header select **Event Attribution**, or use `/?view=attribution`; no upload is required. Users type up to 100 ticker holdings and signed USD position amounts (positive long, negative short). A demo portfolio is available through an **explicit** sample button, never auto-presented as the user's actual positions. The client joins the selected research scenario's entity associations to the original `seeds/exposures.csv` analyst-prior entity/security links. For each security with multiple matching entity links it takes the **highest** prior, not the sum, so interconnected hypotheses do not inflate exposure.

Formula: `qualitative_relevance_score = Σ_i (|position_i| / total_gross_position) × max_matching_seed_prior_i`. Source-prior mapping coverage = mapped gross positions / total gross. Any holding with no seed prior is labeled **not mapped** and not treated as an actual 0-beta security. Long and short positions both contribute to qualitative gross relevance without implying an event return sign. No probability, event coefficient, factor beta, realized historical P&L, or forecast is invented.

A **separate what-if P&L** is `Σ_i (signed_position_i × user_entered_assumed_return_i / 100)` and reports a partial-coverage label if any return is left blank. It is wholly user-entered scenario return assumptions, not EventRisk's own price-impact estimate. All holdings stay in tab-memory only, are never sent in API requests or query strings, and are exported as local CSV only when the user clicks Export. Input and calculation support unknown ticker/blank/shock range validation and nonzero signed positions; tests include long/short and no-P&L-unless-entered cases.

The feature is tested by `node preview_mvp/tests/attribution.test.js` (deterministic pure `preview_mvp/assets/attribution-core.js`) and the Preview MVP Python HTTP smoke. The separate institutional Phase I remains unaffected.

**Security status:** users can research public seed relevance without a database key; reading actual market question records and actual fitted funding models still requires newly scoped and permissioned server-side MotherDuck access. Event attribution must not be advertised as causal or risk-return-based until data-quality and model-validation milestones exist.
