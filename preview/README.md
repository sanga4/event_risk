# EventRisk — knowledge graph preview

**Site:** https://eventrisk-preview-web-production.up.railway.app/

**Capability comparison report:** https://eventrisk-preview-web-production.up.railway.app/report

This separate engineering preview **reuses the original `web/index.html` stylesheet as the visual base** (light palette, original Event Risk Graph header, tab/split-pane/legend patterns) and reproduces the original EventRisk project's **three-panel knowledge graph interaction** while expanding its conceptual path from *events → involved reference entities → securities* to *economic transmission channels → financial risk factors*. The original repository \`main\`, the \`eventrisk-factor-lab\` production API and \`event-risk-mvp\` are not modified. Preview source is on \`feat/engineering-preview-isolated\`, built from \`/preview\` and deployed to a **different Railway project**.

## What is on the website

- **Left sidebar** lists and searches event scenarios, securities, entities, qualitative factor definitions and economic channels. Search is global when non-empty. Selecting any node changes focus.
- **Center** is a fully interactive force-assisted canvas network. Click nodes to explore; drag nodes, drag the whitespace to pan, use scroll to zoom, **Fit view**, neighborhood hops **1/2/3**, **All nodes**, hide prior-exposure edges or show their names. Node shapes and colors distinguish semantic types.
- **Right detail panel** shows selected node type, company ticker/sector/country where available, reported economic actuals only for authentic official source receipts, important independent evidence limitations, full relationship list including original qualitative analyst-prior *weight*, source paths and publisher/Wikidata links. Clicking a relationship navigates to that neighbor.
- **Methodology** page explains what is observed, what is illustrative and why the model cannot be treated as institutionally accepted.
- **Capability report** at `/report` is computed per HTTP request from the admitted, dated public graph and aggregate research snapshots. It contrasts the earlier explorer with newly available economic-channel paths, public-seed verification and original BEA evidence. It is NOT a realtime venue-data report.
- **API and Excel** remain accessible. The Office taskpane now has an **Import graph + formulas** action, which builds dedicated `ER_Nodes`, `ER_Edges`, `ER_Metrics`, and `ER_Explorer` sheets. It does not overwrite the original research workbook sheets; the Office client sideload itself still requires user verification. The downloadable `.xlsx` workbook created for this project contains 84 nodes, 102 edges, dashboard calculations, a 7-formula research path explorer, a new-versus-earlier capability comparison and source-maturity caveats.

## Graph sources (critical distinction)

\`data/graph.json\` contains **84 source-linked research graph nodes and 102 edges** in its initial frozen preview (9 event/release, 8 entity, 52 security, 5 transmission-channel and 10 factor definition nodes). Four semantic edge families:

| Relation | Evidence | Approval |
| --- | --- | --- |
| \`entity → security\` | The **real original** public \`seeds/exposures.csv\` analyst-prior seed plus ticker descriptions from \`securities.csv\`. The displayed weight is taken from the published seed, **not** a verified beta or security return sensitivity. | UNREVIEWED ANALYST PRIOR |
| \`event scenario → entity\` | Explicitly constructed **illustrative** involvement. Scenario nodes are not claims of current events or market-implied event probabilities. | HYPOTHETICAL |
| \`event/release → economic channel\` | Illustrative economic mechanism. Two BEA nodes quote genuinely reported August 2026 values stored in MotherDuck from official publisher pages *as retrieved October 26* (core PCE +0.2% m/m and positive August trade deficit magnitude $105.6bn), not original issuer first-publication timestamps. | UNREVIEWED MECHANISM |
| \`channel → factor\` | Factor names and descriptions from the public \`seeds/factors.json\` qualitative factor catalog. Link is an illustrative possible transmission, not approved factor-impact regression. | HYPOTHETICAL |

All graph edges carry \`review_status=RESEARCH_ONLY_NOT_APPROVED\`. Graph JSON is checked against a versioned allowlist, validated node IDs and qualitative release statuses; malformed or falsely elevated approval fails HTTP 503. No venue quotes, proprietary corporate-action adjustments, positions, licensed credit data, bookmaker market prices, full MotherDuck warehouse tables or credentials are exposed through this graph.

**Important:** There is no independent evidence to support live, historically point-in-time-correct event→security or event→factor impact estimates. Original Phase I release remains FALSE with last 54-gate historical audit 25 PASS / 29 BLOCK + four manual. The BEA receipts are later than the audit.

## Running and testing

\`\`\`sh
cd preview
python app.py
# http://127.0.0.1:8080/             graph website
# http://127.0.0.1:8080/api/v1/graph  graph research sample JSON
# http://127.0.0.1:8080/api/v1/overview verified aggregate status
# http://127.0.0.1:8080/excel/taskpane.html
python -m unittest discover -s tests -p 'test_*.py' -v
node --check assets/app.js
node --check excel/taskpane.js
\`\`\`

The app has **no direct MotherDuck connectivity and no vendor credential**. Its site and API run live as HTTP services, while *the graph and numbers are dated, frozen, reviewable research snapshots*. To update the visible graph, perform a reviewed source-controlled seed/graph build and independent acceptance. Do not give the public preview a MotherDuck token or simply disable the original \`LAB_DATA_RIGHTS_ACK\` control.

### JSON endpoints

- \`GET /\`: three-pane graph website.
- \`GET /api/v1/graph\`: frozen source-derived nodes, typed relations, documentation and explicit non-approval flags.
- \`GET /api/v1/overview\`: previously accepted 2026-10-26 research counts and 25/54 gate snapshot.
- \`GET /api/v1/factors\`, \`GET /api/v1/blockers\`, \`GET /api/v1/evidence\`, \`GET /api/v1/release-gates\`: structured *aggregate-only* status from the older preview.
- \`GET /api/v1/metrics.csv\`: Excel-compatible aggregate rows.
- \`GET /excel/manifest.xml\` and \`GET /excel/taskpane.html\`: Office add-in scaffold; live Excel host install/write **not** independently verified.
- \`GET /health/live\`: process liveness, NOT source freshness, rights or institutional model readiness.

## Next steps to institutional authenticity

This prototype is intentionally much more visual than the earlier metric-card preview. Future tasks must be carefully separated: (1) publish only rights-authorized versioned event/entity/security graph subsets; (2) preserve exact original event market/contract and issuer-clock lineage; (3) obtain legal and independent validation of directed exposure and factor mappings; (4) accumulate more prospective economic source dates; (5) reject unreviewed causal/event beta claims. See \`lab/PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md\` and proposed \`lab/engineering_preview/INSTITUTIONAL_CONTINUATION_LEDGER.md\` in PR #73.

## Deployment

Railway project \`eventrisk-engineering-preview\` (ID \`9e4ecad7-c78e-4427-923f-9f4ecca2cae9\`) deploys service \`eventrisk-preview-web\` (ID \`15f6674d-0ddd-4f1d-b156-a131b379beb6\`) from the isolated feature branch with root \`/preview\`. When changing code, deliberately update the **pinned service commit** and verify the resulting deployment SHA, CI, \`GET /api/v1/graph\`, website and source-safety checks. Do not change or merge the original \`main\` branch just to deploy this standalone preview.
