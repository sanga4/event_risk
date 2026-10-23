# Phase I v2 diagnostics and institutional release gates — October 23, 2026

Authoritative source: sanga4/event_risk/main; **not** huimarco/event_risk/main.
The existing upstream MVP service is not modified.

## Jobs delivered

- lab/phase1_robust_regressions.py: MotherDuck Flight 77d9069a-e05f-4be1-9c51-599ae2d37ae6; 72 exploratory venue/factor regressions, 5-lag Newey-West standard errors, chronological 70/30 holdouts, Benjamini-Hochberg correction across all estimates.
- lab/phase1_release_gates.py: MotherDuck Flight e6053a40-6deb-48ed-9598-27abff027a7a; materializes lab_release_gate_history_v1 and lab_release_gate_summary_v1 with point-in-time, mapping, evidence, data freshness, and external data-rights gates.

Initial run: zero of 72 tested hypotheses passed 5% FDR; only 19 had positive holdout R-squared relative to the training-mean baseline. These are retrospective same-day or prior-venue-day statistical associations, NOT point-in-time regressions, causal event-factor betas, forecasts or trade signals.

Initial gate run: 2 out of 9 automated criteria pass, 7 block, and 4 manual criteria remain blocked. The released_to_institutional_production flag stays FALSE by construction. The two passing automated gates indicate successful materialization of historical and robust-regression research scripts, not research approval.

## Dedicated authenticated API endpoints

- GET /v1/research/v2/robust-regressions: research-only regression coefficients and out-of-sample metrics. Requires API key, an explicit retro-data switch and research_use=true.
- GET /v1/research/production-gates: last stored automatic and manual release gates. Requires API key and configured data rights.

The dedicated Railway factor-lab-api reads only eventrisk_factor_lab and deploys from sanga4/event_risk/main when merged. Its startup health does not authorize data access. Keep licensed credit feeds disabled until verified. Scope API credentials and database token in Railway; do not place secrets in source, Flight config, or chat.

## Unfinished launch dependencies

1. Restore authenticated and scheduled collection into a verified writable owned MotherDuck database, not a share. Add incremental quote and source revision capture; record actual retrieval and publication timestamps.
2. Build historical and forward-looking event features using only confirmed as-known quote records, with as-of ontology links; never relabel backfill or revised factor files as point-in-time.
3. Independently review event/channel/factor mappings, including evidence, reviewer signoff and validation as-of the original cutoff.
4. Fit event-level models with pre-specified horizons, training/testing chronology, factor release timing, controls, inference, multiplicity and holdout rules.
5. Independent data-rights, licensing and release committee approval. Configure Railway credentials and observability, backup and rollback.
6. Implement bounded incremental refreshes rather than rerunning the 11-million-row full-market reconstruction daily.

The structural database and analytical pipelines are deployed, but no investment-signal or research-product release is authorized by this status page.
