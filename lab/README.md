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
