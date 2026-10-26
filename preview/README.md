# EventRisk Engineering Preview — isolated demonstration

This folder is a **standalone research engineering preview**, not an institutional deployment. The GitHub branch contains a complete Git snapshot of the institutional repository but changes *only* preview-specific files. Railway must build from root directory \`/preview\` in a separate project. **Do not merge to main until intentionally reviewed**, change any data rights flag, or attach the existing production laboratory service.

## Run locally

\`\`\`sh
cd preview
python app.py
# Open http://localhost:8080/
# Open http://localhost:8080/api/v1/overview
# Download http://localhost:8080/api/v1/metrics.csv
python -m unittest discover -s tests -p 'test_*.py' -v
\`\`\`

No API key or MotherDuck token is used: these endpoints are restricted to a frozen, manually reviewed **aggregate-only** snapshot of previously verified research evidence. They are not the protected Factor Lab API. This prevents accidental release of raw venue quotes, security return inputs, proprietary source packets, restricted/uncertified betas or portfolio data. Do not add such data to snapshot.json.

### Routes

- \`/\` — 5-tab research/engineering dashboard: Overview, Event × factor, Beta laboratory, Data quality, Next steps.
- \`/api/v1/meta\` — snapshot version, as-of provenance and limitations.
- \`/api/v1/overview\` — audited counts and the last institutional release-gate snapshot.
- \`/api/v1/release-gates\`, \`/api/v1/factors\`, \`/api/v1/evidence\`, \`/api/v1/blockers\` — explicitly bounded descriptive summary endpoints.
- \`/api/v1/metrics.csv\` — Excel-compatible plain CSV of aggregates.
- \`/excel/taskpane.html\` — Office.js taskpane that writes aggregate research metrics to Excel (on Excel hosts) or provides CSV export.
- \`/health/live\` — process health, not warehouse or legal readiness.

### Excel add-in

After successful HTTPS deployment, edit \`excel/manifest.xml\` to the exact verified domain for TaskPane source. Sideload into Excel as a custom add-in. The taskpane displays current **frozen snapshot** metrics and uses \`Excel.run\` to insert a 6-column source-labeled table into the selected active worksheet. There are **no trading, pricing or custom-function forecasts**. In browsers the same taskpane explains how to sideload and allows CSV download.

### Source provenance and UX rules

Every figure in \`data/snapshot.json\` has an as-of UTC, source table and concrete unit. The source data itself changes only when explicitly reviewed and exported with appropriate access. Showing API responses at a live URL does **not** make data continuously updating. No provider first-publication / quote-creation clocks, full signed institutional model acceptance, causal innovations, licensing or active collection is implied by the snapshot.

Read \`HANDOFF.md\` for blockers, exact delivery status and next-phase dependencies.
