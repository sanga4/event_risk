# Phase I — Event-to-Financial-Factor Laboratory

## Purpose and authoritative boundaries

Phase I links event/proposition observations to versioned economic transmissions, traceable factor series, and an independently auditable historical research panel. This is **not** an estimated factor-beta engine and should not be promoted to trading-signal or client risk outputs without the point-in-time and data-license gates.

- **Institutional source:** `md:event_risk_institutional`, with separate `md:event_risk_institutional_staging`; the former hosts canonical events, sources and lineage. Do not write back from the public API.
- **Research laboratory:** `md:eventrisk_factor_lab`; includes `lab_event_factor_panel_v2`, factor observations and catalogs, candidate paths, archive hashes, ingestion runs and dataset builds. Treat it as an independently governed research domain.
- **Qualitative factor taxonomy:** the existing `factors.py` / `seeds/factors.json` 108-factor repository catalog is a logical relevance layer. Do not equate it with the laboratory's 22-series factor-observation catalog, and do not convert accepted logical links into return forecasts or betas.
- **Existing MVP Railway service:** upstream `huimarco/event_risk`, not this fork. Do not replace or repoint it as a side effect of laboratory work.
- **Dedicated Railway laboratory service:** `eventrisk-factor-lab/factor-lab-api`. It has no deployment/source and no public domain as of the 2026-10-23 audit; it is **not** live.

## Snapshot: verified on 2026-10-23

The lab database had 233,442 panel-v2 rows, 2,283 distinct propositions, 18 distinct observed factors and event dates 2026-10-17 through 2026-10-22. Factor histories date back to January 2024, but the joined event-factor panel covers only six event calendar dates. All panel rows were `mode=retrospective`, and all were marked `data_lookahead_warning=true`. As of the audit, **zero panel rows qualified as point-in-time eligible by their factor availability timestamps**.

The latest registered build was `lab-phase1-v0.6.0` at 2026-10-23 14:46:53 UTC, labeled `verified_retrospective_panel_v2_weekend_alignment`. That status is a **producer's record**, not independent release certification. The lab's `lab_dataset_builds.source_commit` includes friendly labels, not always immutable 40-character Git SHAs; resolve reproducibility before institutional release.

The query in [`phase1_v2_validation.sql`](phase1_v2_validation.sql) was verified against the database on 2026-10-23. It returned zero duplicate composite keys, zero invalid probabilities, zero date/carry/hash/bps inconsistencies and zero **unflagged** factor look-ahead rows. The `factor_daily_change` convention is **basis points**, so the factor-level percentage-point difference is multiplied by 100. A zero count of recorded `lab_quality_issues` is **not** evidence of independent accuracy or data-rights approval.

### Mapping governance checkpoint

As of the same read-only audit, the lab had **48,711 candidate event-factor paths**, all `review_status=proposed` and `historical_mapping_lookahead=true`; **50 proposed ontology relations** with no linked `evidence_id`; **40 pending reviewer cases** (none decided); and **zero records in `lab_evidence`**. Two restricted ICE/BofA credit entries remain inactive. Three of four build records use source labels instead of immutable 40-character Git SHAs.

The separate read-only [`phase1_mapping_readiness.sql`](phase1_mapping_readiness.sql) returned `BLOCKED_UNREVIEWED_MAPPING`. **Proposed candidate paths must not be represented as analyst-approved economic relationships** merely because they are materialized in MotherDuck.

## Release gates (all mandatory)

1. **Source control and reproducibility.** Check in and review the panel builder and factor ingestors; pin exact full Git SHA, runtime/package versions, extraction snapshot SHA and the SQL model version to each build. The observed `lab-phase1-v0.6.0` label alone is insufficient.
2. **Bitemporal event+factor availability.** Build and independently validate a strict point-in-time join: `event_observed_at` and `event_known_at` must be honored, factor release/ingestion availability must precede the evaluation cutoff, and there must be no retroactive use of revised values. Hold all retrospective-only rows out of backtest-safe outputs.
3. **Provenance, calendar and licensed series.** Validate official release timezones, holiday/weekend carry-forward, revisions, missing dates, source-row checksums, provider terms, and distribution rights. The inactive `restricted_ice_bofa` credit entries must remain blocked without a license.
4. **Independent QA.** Attach a reproducible acceptance suite to CI, including negative-control event/factor pairs, event source-to-contract trace, no look-ahead assertions, idempotent rebuilds, duplicate/revision handling, and held-out evaluation. Escalate issues rather than merely keeping the quality-issue table empty.
5. **API and deployment segregation.** Add a separate **read-only** laboratory API with authentication, pagination, bounded queries, transparent `mode`/`data_lookahead_warning` response fields, health/readiness checks, request limits, audit logs and freshness metadata. Do not reuse the upstream production deployment or expose token-bearing variables in responses/logs.
6. **Operational acceptance.** Staging-only rollout, live smoke tests and validation against a pinned database snapshot before serving any public research data. Keep Factor Lab offline until a source, scoped MotherDuck credential, explicit data rights policy and deployment checks are in place.

## Immediate CI repair

Four existing GitHub ingestion/pricing workflows previously installed unconstrained DuckDB 2.0.0 despite the repository pin `duckdb==1.5.6`. MotherDuck rejected this version; job logs also indicated the `MOTHERDUCK_TOKEN` Actions secret was unset. This branch switches workflows to `pip install -r requirements.txt` and adds an explicit credential gate. **Do not merge and assume collections are restored** until the repository secret is configured and a fresh manual workflow invocation demonstrates successful writes and source freshness. The collector's graph-building step must not continue after a failed snapshot step.

## v3 historical data & exploratory regressions (2026-10-23)

The definitive source is sanga4/event_risk. No changes are needed in the separate huimarco repository. The dedicated Railway project is eventrisk-factor-lab.

### Source-controlled executable scripts

- lab/phase1_build_v3.py: Flight eventrisk-factor-lab-phase1-v3-materializer, output lab_event_factor_panel_v3 (233,442 retrospective and 0 as-known rows), run manifests, input lineage and reviewer decision storage.
- lab/phase1_historical_regressions.py: Flight eventrisk-factor-lab-historical-research-regressions, output lab_market_daily_historical_v1 (565,695), lab_venue_daily_features_v1 (2,979), lab_exploratory_regressions_v1 (36 fits), and lab_history_build_runs_v1.

The historical source spans 2021-07-08 through 2026-10-22. Approximately 536,699 market-day rows originated from snapshots marked backfill. Their timestamp is an observation label, not independent proof of the information's historical availability. Output is point_in_time_verified=FALSE.

Exploratory models use contemporaneous daily venue-average absolute market probability moves (percentage points) against daily factor changes (basis points for percent-quoted yields or native units otherwise). At least 120 matched observations, 12 months and nonzero variance are required. The initial 36 regressions each cover 492–640 dates. R-squared lies between approximately 0.00000065 and 0.00752. These are weak research associations, not event-level impact coefficients, predictive signals, causal links, investment recommendations, or validated historical backtests.

### Isolated Railway read API

API runs in /lab using pinned dependencies. Health liveness does not authorize data serving. Read endpoints require the X-API-Key request header, LAB_API_KEYS, a scoped MOTHERDUCK_TOKEN, LAB_DB=eventrisk_factor_lab and explicitly confirmed LAB_DATA_RIGHTS_ACK=true. Historical/regression reads additionally require LAB_ENABLE_RETROSPECTIVE_READ=true and research_use=true. Keep LAB_ENABLE_LICENSED_CREDIT=false. Never publish secrets.

API routes include /v1/research/v3/builds, /v1/research/v3/summary, /v1/research/v3/panel, /v1/research/history/coverage, /v1/research/regressions, /v1/research/mappings/readiness. PIT release remains blocked.

### Remaining production release gates

1. Restore ingestion freshness and scheduled collection with narrowly scoped credentials; record actual known_at, ingested_at, availability_at and historical factor revision vintages.
2. Build substantially longer independently supported as-known event and factor histories. Retrospective backfills cannot be silently relabeled as PIT.
3. Review and evidence event-to-economic-channel-to-factor links; track reviewers, decisions, rationales and valid as-of periods.
4. Develop causal/forecast research with predeclared horizons, temporal holdouts, robustness to serial dependence, multiplicity control, coverage and missing-data policy, and true factor return benchmarks.
5. Configure the dedicated Railway secret(s), explicit data rights, API keys, access logging, uptime monitoring and rollback. Do not repoint the existing huimarco-based MVP.
6. Use an immutable source commit, script SHA and source versions on each build.
