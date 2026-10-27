# EventRisk — October 27, 2026 handoff and implementation roadmap

## Product boundary
EventRisk's primary interfaces are the **versioned API and Microsoft Excel add-in**. The website is solely a raw, Marco-style graph viewer with a small access-aware Factor Research Lab. Do not convert it into a fintech dashboard. The canonical Marco original is `web/index.html` on `main`.

## Infrastructure to verify
- GitHub: `sanga4/event_risk`
- Product worktree: `product/eventrisk-research-v1`, legacy source directory `preview_mvp/`
- Production Railway project `eventrisk-research`, service `eventrisk-research-web`
- Product site: https://eventrisk-research-web-production.up.railway.app/
- MotherDuck database `eventrisk_factor_lab`, accessible from Railway; previous external HTTPS and Railway logs proved startup SELECT. The standard PAT can have write authority; API SQL is limited at the application layer. Never show/copy token values.
- Institutional Phase I: protected separate `main` and Railway `eventrisk-factor-lab`, must remain unchanged.
- Public repo catalog: 543 securities, 108 established factor definitions, 22 economic channels; original raw public graph maintained at `/api/v1/graph`.
- Research data restrictions: public catalog != actual Kalshi/Polymarket licensed redisplay. `EVENTRISK_SOURCE_REDISPLAY_APPROVED` and `EVENTRISK_DERIVED_RESEARCH_APPROVED` are independent gates; never flip without owner/legal verification.

## Work executed in this handoff turn
1. Created `preview_mvp/pathways.py` and `GET /api/v1/graph-paths` with an explicit **synthetic** five-stage path: demonstration contract → hypothetical data-center demand event → thematic infrastructure entity → existing security references → proposed factor definitions. The synthetic contract is **NOT** a real Kalshi/Polymarket listing, has **zero** real observed market price, and the factor links are **not** fitted beta estimates. Original `GET /api/v1/graph` contract remains stable.
2. Updated original Marco-style `viewer.html` and `viewer.js` to browse Contracts / Events / Entities / Securities / Factors / Questions, and display the small complete directional five-stage path without requiring enormous global graphs.
3. Repaired the page routing: `/lab` now serves the real research workbench in `preview_mvp/lab.html` rather than an API documentation placeholder. `/api` remains the plain API index. Fixed lab `sessionStorage` key persistence and show *connected but rights-gated* states explicitly. Real funding regressions and factor history are still restricted until approved.
4. Added `market_providers.py` with pagination and normalization of native contract identifiers from Kalshi cursor-based events and Polymarket Gamma offset-based events. This is a **bounded discovery/normalization library**, NOT a complete ingestion, not a licensed redisplay service, and not an archive.
5. Added `factor_universe.py`: broad cross-asset proposed factor taxonomy alongside the canonical 108; all proposals have **no validated observed history**. Public `GET /api/v1/factor-proposals` exposes clear review flags.
6. Updated Excel taskpane with an opt-in import of proposed factor definitions and demo five-stage graph sheets, preserving original factor catalog and graph-prior sheets.
7. Added Python unit, source contract, HTTP and Chromium browser acceptance checks in the product branch; verify CI status on latest commit before release.

## Architecture plan (proceed without needless confirmation)
### Phase A: graph and contract identity
- Data model: provider `(kalshi|polymarket)`, immutable provider contract ID, provider event ID, source titles/outcomes, settlement criteria, lifecycle, captured_at, source first-published-if-verified, separately reviewed canonical event ID, entity mappings, security references, economic transmission channels, proposed vs observed factors, review status and source rights.
- Visually represent contract → event → entities → securities → factors, optionally displaying transmission channels between entities/factors without implying causality.
- For real listings, never infer a canonical real-world event solely from a string match; review high-confidence mapping and preserve ambiguous/unmatched pools.

### Phase B: full Kalshi + Polymarket discovery
- Kalshi event cursor pagination, nested markets, all lifecycle states and separate multivariate/historical endpoints when allowed. Polymarket Gamma event/market offset pagination, tags, closed markets and appropriate historical data sources. Use official APIs; respect rate limits, provider terms, quotas and historical cutoffs.
- Checkpoint every cursor/offset and venue series, dedupe stable native IDs, retain source changes as versioned snapshots, monitor invalid pagination/rate throttles.
- Stage standardized raw records in a separately entitled data store, then maintain normalized views in MotherDuck. A complete snapshot means only *all accessible pages within a declared scope/time*, not “all markets ever.”
- Require provider data rights and redistribution review BEFORE publishing licensed contract text or prices to Excel/public website. Do not use MotherDuck `query_rw` without explicit confirmation.

### Phase C: comprehensive factors and economics
- Cover electricity, AI/data-center infrastructure, energy, semiconductors, utility capex, real estate, industrial metals, carbon/water, FX, rates, credit, equity/style, funding, inflation, labor, housing, trade, geopolitics.
- Add factor series via documented provenance, units, point-in-time/revision methodology, license, date coverage, sample counts, and quality gates. Catalog definitions != data coverage.
- Regression coefficients are noncausal until event design, independently timed surprises, multiple comparison correction, out-of-sample validation and institutional review pass.

### Phase D: research lab, API, Excel
- Source-aware `/lab` displays working hypothesis routes publicly. Historical regression/factor controls call the same authenticated API as Excel, and show 401/403 and rights blockers precisely, not fabricated values.
- API endpoints for contract discovery, canonical events, mappings, factor taxonomy, factor history, model/Holm diagnostics and coverage/correctness audit.
- Excel add-in imports the same data contracts as API; test Excel sideload and formulas manually. Do not call Excel client acceptance complete until tested.

### Phase E: institutional release
- Auditable captures, deterministic backfill, failed-source retries and report exact per-provider number of source pages/records/canonical mappings. Separate Phase I source rights, vendor rate limits, sample independence, research regression governance and SSO.

## Next actions
1. Inspect latest CI statuses and Railway deployment pin. Do not deploy failed browser/test commits.
2. Test `/api/v1/graph-paths`, `/api/v1/factor-proposals`, `/lab`, and Excel taskpane HTTP with real browser and remote HTTPS.
3. Implement a bounded **provider snapshot coverage audit** without assuming capture rights; then seek rights-approved storage and historical backfill.
4. Extend mapping confidence/review and connect genuine entitled provider IDs to canonical events.
5. Validate the real Excel-client installation and underlying source rights independently.

The key principle is to state concrete progress without claiming provider-wide ingestion, tested original PIT, inferred betas or published licensed data.
