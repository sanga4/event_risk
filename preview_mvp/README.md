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
