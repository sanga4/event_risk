# EventRisk Graph Preview — Engineering Handoff

**Current user-facing preview:** https://eventrisk-preview-web-production.up.railway.app/

**Core decision:** The engineering preview has become a **knowledge-graph-first** experience modeled on the previous Marco Hui main EventRisk network. It is NOT the previous five-card dashboard as its homepage. It is an expanded event/entity/security/channel/factor explorer with left search/list, central zoomable/pannable network and right details/provenance panel. The JSON stats and Excel interfaces from preview v1 remain available separately.

## Isolation and architecture

- Canonical original repo \`sanga4/event_risk\` remains on main at \`2c7bc00bb71c6892d910459558679354b74015b2\` as of graph preview work; do not merge the preview draft PR #74 into original main simply to deploy.
- Separate work branch: \`feat/engineering-preview-isolated\`, containing original code plus independently deployable \`preview/\`.
- Separate Railway project \`eventrisk-engineering-preview\` ID \`9e4ecad7-c78e-4427-923f-9f4ecca2cae9\`; service \`eventrisk-preview-web\` ID \`15f6674d-0ddd-4f1d-b156-a131b379beb6\`; environment \`ff3f3d7d-111d-4bb9-832d-c4baed77a101\`; source branch above and root \`/preview\`; service uses a pin to an explicit exact commit SHA. This prevents unreviewed pushes and changes to the original institution-facing deployment.
- \`preview/app.py\` is a standard-library Python HTTP server, no vendor DB runtime access. \`preview/data/graph.json\` is a frozen sample from original public seed source files; \`preview/data/snapshot.json\` is prior accepted aggregate research metric evidence.
- GitHub PR #74 is a **draft** preserving review context, not a merge request to change original institutional production.

## Implemented graph (reviewed at snapshot level, not institutional model approval)

- 9 event/release nodes: seven explicitly hypothetical world/policy/supply scenarios and two actual numbers originally published by the official U.S. BEA, but pages were received October 26 **after** original release dates; publication-as-first-known unverified.
- 8 Wikidata reference entity nodes; 52 stock/ETF/FX security-reference nodes from original \`securities.csv\`; 5 constructed economic transmission hypothesis nodes; 10 original named qualitative factor definitions from \`seeds/factors.json\`.
- 102 edges: 60 original \`seeds/exposures.csv\` entity→security analyst-prior links with 0–1 relevance weights, 13 hypothetical event→entity associations, 14 illustrative event→economic-channel links and 15 illustrative channel→factor mappings. All edges \`RESEARCH_ONLY_NOT_APPROVED\`. **No empirical event beta, price forecast, probability, risk weight, validated security impact or causal mapping.**
- \`preview/scripts/verify_graph_source.py\` independently cross-checks each public analyst-prior edge weight and original rationale against actual source CSV and checks security metadata plus factor definitions. \`preview/app.py\` fail-closes any missing/malformed node ID, unsupported release status or falsely approved edge in \`GET /api/v1/graph\`.
- Original observed BEA values include core PCE +0.2% m/m and US trade deficit positive magnitude $105.6bn for August 2026. These are **actual reported values, not surprise estimates**, and pre-event expectations/provider vintages are not verified.

## Graph UX interactions

- Browse across five tabs, or search across **all** graph node types.
- Left list selection and canvas node click highlight active node; right panel provides provenance and followable relationships, ticker, sector, country, and analyst-prior seed weight/rationale.
- Graph focuses 1, 2 or 3 relationship hops; supports whole-graph mode, hide analyst-prior edges, show edge labels, drag nodes, pan blank area, scroll to zoom, Fit view, zoom +/- and previous-selection history.
- Responsive browser CSS with type-coded shapes and neutral caution; Methodology page and links to quantitative aggregate API and Office taskpane.
- **Privacy and exposure:** This is an intentionally public sample of published repository metadata and prior relationships; it neither queries nor exposes raw prediction venue quotes, portfolio holdings, restricted factor source records, credentials, or unpublished warehouse assets.

## API / Excel deliverables

- \`/\`: expanded graph interface.
- \`/api/v1/graph\`: documented graph node/edge provenance with frozen status.
- \`/api/v1/overview\`: verified prior aggregate data, including the original release gate snapshot 25 PASS / 29 BLOCK out of 54 automatic and four independent manual, institutional production FALSE.
- \`/api/v1/meta\`, \`/api/v1/factors\`, \`/api/v1/evidence\`, \`/api/v1/blockers\`, \`/api/v1/release-gates\`: bounded audit aggregate endpoints.
- \`/api/v1/metrics.csv\`: Excel-compatible export of audited aggregate stats.
- \`/excel/taskpane.html\` and \`/excel/manifest.xml\`: Excel add-in package with source labels and UTC as-of; **actual manual Excel client sideload/write remains unverified**.

## Verification method

1. \`python -m unittest discover -s preview/tests -p 'test_*.py' -v\` and \`python preview/scripts/verify_graph_source.py\` locally or GitHub \`verify-engineering-preview.yml\`; \`node --check\` graph and Office JS.
2. Check independent 84-node/102-edge source lineage, nonapproval statuses and exact prior CSV weights (not just schema shape).
3. Deploy to **existing separate preview service only**, pinned to a Git commit; verify Railway's actual successful deployed SHA matches the intended GitHub commit and remains distinct from the institutional service.
4. Independently GET over HTTPS: \`/\`, \`/assets/app.js\`, \`/assets/styles.css\`, \`/api/v1/graph\`, \`/api/v1/overview\`, \`/api/v1/meta\`, \`/excel/taskpane.html\`, \`/excel/manifest.xml\`, PNG asset and CSV, inspect semantics. A Railway healthcheck alone does not constitute a graph usability test.
5. Actual browser click/drag experience and Office sideload require a browser/Excel environment. Do not claim either was proven merely because HTTP succeeds. Include any visual/browser limitations at closeout.

## Institutionally unfinished (preserved separately)

- Source-as-first-published and version/revision clocks, venue quote historical PIT, independent event shock and original survey consensus, license/vendor redistribution terms.
- Original field contract audit had 16 contracts, 274 field rules, 255 required, 135 missing and 255 independently uncertified; no fake schema backfill.
- True prospective co-observation depth: 49,666 venue records across 4 capture days and 2 factor observation dates (893,988 join rows do NOT represent that many independent samples).
- Independently approved causal event→factor mapping, security master original adjusted-return provenance, durable modeling rights, 96-model Holm familywise funding screen with zero survivors, robust cross-asset covariance/regime, independent signoffs.
- The last 54-gate institutional snapshot predates BEA source receipt; Phase I release is **not approved**. Do not change any false governance approvals for this demo.

## Next side-project enhancements

- Once approved legally and technically, add a versioned **public/permissioned** subset of original canonical event-question relationships while preserving exactly dated first-known contract clocks; use a source access policy instead of exposing entire market capture logs.
- Add extra search/filter views for date, sector, region, causal channel and semantic edge; provenance links to original review items. Current graph scenarios must remain explicitly illustrative until original event evidence is independently obtained.
- Re-test any changes with offline source replay + HTTP smoke; complete actual Office Excel side-loading and worksheet write.
- Keep all future graph snapshots time-stamped and pinned to reviewed source commits. No live MotherDuck token in public preview service.

**Primary technical index:** \`preview/README.md\`. **Institutional continuation:** \`lab/PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md\` and \`lab/PHASE1_PRODUCTION_UNBLOCK_PLAN.md\`. PR #73 is a separate planning/continuation-ledger draft on another non-main branch.
