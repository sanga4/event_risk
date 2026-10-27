> **Verified connection update (2026-10-26/27):** EventRisk Research Railway successfully executed a MotherDuck startup SELECT using its privately configured token. This verifies network/database connectivity, **not** database-level read-only privileges. The API uses one-statement SELECT parsing, fixed SQL templates, parameterized filters and separate source/derived redisplay gates. Regression and factor-history queries were independently checked against live warehouse tables. The API and Excel are the product; the Marco-style website is only a reference graph viewer.

# EventRisk Research — Product Release & MotherDuck Integration

**Product identity:** EventRisk Research (not an MVP or Preview-branded customer product).

**Production infrastructure (separate from Phase I):**
- Railway project: `eventrisk-research`, ID `a450ceba-b3f2-47f2-907f-ff77ca36c91b`
- Railway service: `eventrisk-research-web`, ID `1a0dbbf9-5c17-439a-b943-f0da9b62813a`
- Production domain: https://eventrisk-research-web-production.up.railway.app/
- Repository: `sanga4/event_risk`, standalone root `/preview_mvp` (historical internal directory name; not product branding).
- Source branch for full product: `product/eventrisk-research-v1` (feature branch, NOT the institutional `main`).

## Features
1. Original Marco light/dark knowledge graph with focused event → entity / economic channel → financial factor / securities relationships, searchable across all published reference companies and factor definitions. All source hypothesis edges are research-only.
2. Browser-local portfolio event relevance and optional manually supplied what-if return scenarios. No holdings uploads or event-return beta fabrication.
3. Factor Research Lab with historical observed Treasury series, actual 48-security funding regression diagnostics, independent Holm familywise evidence, original source-date warnings and separate modeled-status flags.
4. **Full schema Database Explorer** at `/data`: catalog sourced directly from MotherDuck `information_schema`. Verified warehouse contains **148 research tables and 2,239 columns** on Oct 26, 2026. A separately entitled admin can browse those available datasets using maximum 50-row, parameterized, per-table reads, schema metadata and CSV of only retrieved rows. The browser does not accept arbitrary SQL.
5. Standalone Excel Office.js manifest/taskpane, workbook catalog, data priors and basic lookup formulas. Source model and factor observations require independent permissions; actual Excel-host sideload acceptance is still needed.

## Credentials — owner action required

Use a dedicated MotherDuck identity and approved research database share. A Read Scaling Token is preferable when the subscription supports it; a standard token can connect on Lite but retains database write authority, so only use it for controlled internal research with tightly scoped application queries. Read scaling prevents writes but **does not grant table-level confidentiality automatically**. Limit the shared database/rights at the MotherDuck service-account level. MotherDuck docs: https://motherduck.com/docs/key-tasks/authenticating-and-connecting-to-motherduck/read-scaling/ and https://motherduck.com/docs/key-tasks/ai-and-motherduck/securing-read-only-access/.

In Railway project `eventrisk-research` → service `eventrisk-research-web` → Variables, set these server-only, strong secrets privately:
- `MOTHERDUCK_TOKEN` — a securely stored MotherDuck token; standard Lite PATs can write at the database level even though EventRisk API paths use fixed parsed SELECTs.
- `EVENTRISK_ANALYST_KEY` — separate closed-research identity verification key; replace with per-user SSO for a wider commercial multi-analyst release.
- `EVENTRISK_DATA_ADMIN_KEY` — distinct, high-entropy internal read-only admin key. **Never** give it to ordinary public-site visitors.

Optional governance flags (must **not** be enabled without documented data-use approvals):
- `EVENTRISK_SOURCE_REDISPLAY_APPROVED=true` authorizes display of provider-origin graph/question/market records.
- `EVENTRISK_DERIVED_RESEARCH_APPROVED=true` authorizes corresponding derived model/factor/research table read permissions.

The previous `PREVIEW_MVP_ANALYST_KEY` and `PREVIEW_MVP_*_APPROVED` aliases remain understood strictly to permit rolling migrations; use canonical `EVENTRISK_*` variables for new production.

**Never paste issued tokens into chat or the public website.** The browser prompts only for the analyst access key, and /data additionally requires its separate administrator key.

## Live connection and application-layer SELECT acceptance
1. Set the three independent server-only secrets. Do not reuse Phase I's token.
2. Confirm `GET /api/v1/runtime` reports `database_credentials_present:true`, `analyst_key_configured:true`, `admin_key_configured:true`. Those flags indicate **configuration, not proof of a query**.
3. Enter the issued analyst access key under the Marco graph's `Research connection` disclosure. It calls `GET /api/v1/research/coverage` and should return `LIVE_DATABASE_COUNT_ONLY`, matching current MotherDuck counts. After a *successful* SELECT, `connection_tested:true` and the last-successful timestamp are reported.
4. Open `/data` with analyst and admin keys. The response should be `LIVE_MOTHERDUCK_CATALOG`, listing all authorized `main.lab_*` and graph datasets with typed source columns. A row read through `/api/v1/research/table?table=lab_factor_catalog&limit=25&offset=0` succeeds **only with independently approved derived-data authorization**.
5. Test positive/negative auth, no arbitrary SQL, query limits, restricted source-record denial, original-vintage cautions, timestamp provenance, and the UI in an actual browser. Keep operation logs free of credentials and sensitive query parameters.
6. Bring per-analyst SSO, permissions, account audit trails, distributed rate limits and economic model validation online before declaring an institutional/commercial public investment product.

## Explicit source limitations

A successful database connection with SELECT-restricted application queries does not make every observation a verified event nor validate the institutional factor model. Captured market/question node counts differ from unique independent economic events; the historical factor warehouse covers 18 source-observed series against 108 public definitions. Funding regressions remain **associational research** with zero global Holm-surviving candidates in the audited original 96-family. Provider-first-publication PIT, redistribution rights and event-specific causal effect validation remain separate release gates.

**Institutional Phase I** is preserved in its own `main` branch and Railway deployment. The former Preview MVP remains an independently pinned prior iteration; it is not renamed, replaced or merged into Phase I.

## Status semantics

- `DEPLOYED_SITE`: Railway domain and application process verified.
- `AUTHENTICATED_DB_SELECT`: a real server-side MotherDuck SQL SELECT succeeded from this product instance.
- `SOURCE_ENTITLED`: source contract/rights allow redistribution to this product's specific end users.
- `ANALYST_OPERATIONAL`: browser workflows, Excel client, authorization, monitoring and error handling accepted.
- `INSTITUTIONAL_MODEL_APPROVED`: separate methodology/validation/governance release, **not inferred** from any above.

Only mark a gate passed after it has actually been verified.

## Product vs. website: corrected scope (October 26)

**The EventRisk product is the API and Excel add-in.** The website is only a minimal, read-only knowledge graph visualization—based directly on the original `web/index.html` from Marco's graph viewer, reusing its first 9,626 bytes of CSS and original list/canvas/details split-pane layout. It is intentionally plain, not a financial dashboard, marketing landing page or separate analyst platform.

- Raw graph: `/`. Search repository entities (source-backed seed CSV), 543 security references and 108 factor definitions. The original fixed research links are displayed with their type and provenance. Questions tab loads actual versioned MotherDuck graph questions only when an authorized backend SELECT succeeds and source redisplay rights permit it.
- Plain API index: `/api`. The previous nonworking `/lab` UI is retired; `/lab` serves the same plain API/Excel documentation. No unavailable regression/model panel is presented as working. The underlying protected quantitative endpoints remain API-only and explicitly fail closed when source privileges are absent.
- Excel manifest: `/excel/manifest.xml`; workbook taskpane: `/excel/taskpane.html`. Actual Excel-client sideload acceptance remains outstanding.

The warehouse database and protected `/data` administrative explorer are **backend research infrastructure**, not the main website product or a license to display provider-controlled content publicly.

### What the owner must configure (privately)

In MotherDuck, **create an isolated research identity, using a Read Scaling Token if available or an internally controlled standard PAT on Lite**, granting it access only to the approved EventRisk research data/approved share. The connected MotherDuck research plugin can query the account but does not offer durable token creation. In Railway's **eventrisk-research → eventrisk-research-web → Variables**, set `MOTHERDUCK_TOKEN` (the database token, private), `EVENTRISK_ANALYST_KEY` (a new strong password for the closed API audience), and only if admin table inspection is needed `EVENTRISK_DATA_ADMIN_KEY` (different and restricted). Do not put MotherDuck tokens or admin keys into GitHub, browser scripts or this chat.

Data-owner approvals are **separate from database connectivity**. Enable `EVENTRISK_SOURCE_REDISPLAY_APPROVED` only after documenting legal rights to display source question names and records. Enable `EVENTRISK_DERIVED_RESEARCH_APPROVED` only after documenting rights to distribute derived financial model/factor records. Without these approvals, the website may show its public repo seed graph, but protected records stay unavailable.

Once Railway variables are set, perform a real authenticated `GET /api/v1/research/coverage` and verify `connection_tested:true` at `/api/v1/runtime`. No credentials are automatically generated or copied from institutional Phase I.
