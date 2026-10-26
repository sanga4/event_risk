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
