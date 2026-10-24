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

## Prospective timestamped market capture — 2026-10-23

**New source-controlled producer**: `lab/phase1_live_capture.py` (MotherDuck Flight
`eventrisk-factor-lab-prospective-public-market-capture`,
`6a13c2c9-8d1e-480e-bd74-7b50e890a246`). It fetches bounded public
Kalshi / Polymarket current-market API pages and writes only into new,
versioned internal-research tables. A successful HTTP response receipt time is
logged as `capture_received_at`, distinct from the unknown original venue
quote time. SHA256 hashes preserve the source response, record and contract
content (this is provenance, not the raw original API payload).
`provider_quote_freshness_verified = FALSE` and
`historical_point_in_time_released = FALSE` on every collected record.

- `lab_live_market_captures_v1`: capture/venue/market observations with
  receipt timestamp, contract lineage, reported bid/ask and research-only
  release labels.
- `lab_live_market_contract_versions_v1`: new contract content hashes with
  first observed capture time; existing versions remain intact.
- `lab_live_capture_runs_v1`: per-venue success/error metadata, counts,
  immutable script/source hash, and partial-run state.
- `lab/phase1_prospective_features.py` produces **views**
  `lab_live_event_features_v1`, `lab_live_market_latest_v1`, and
  `lab_capture_feed_freshness_v1`. A second capture creates
  consecutive market probability deltas, using receipt order. These
  are **not true exchange-quote age or historical backtest releases**.

The first two flights successfully captured 1,889 Kalshi market records per
run. The corrected Gamma numeric tag filtering subsequently captured 3,000
Polymarket and 1,889 Kalshi observations in one run. The public collector is
**bounded**: at most 3 pages per request/search and 3,000 quotes per venue,
so the result is neither the venue's full market population nor a
fully audited category taxonomy. Market quote fields come from public venue
metadata and may not represent executable or fresh order book prices.

The dedicated laboratory API exposes `/v1/research/live/overview`
for authenticated receipt/health status, and
`/v1/research/live/changes` only with the separate explicit
`LAB_ENABLE_PROSPECTIVE_READ=true` and `research_use=true` gates.
Rights acknowledgement and API key plus database token still apply.
Do not enable these settings for public users without verifying market
redistribution permissions and scopes.

**Scheduling**: the current MotherDuck plan rejected an hourly scheduled
Flight. The checked-in GitHub Actions
`.github/workflows/phase1_prospective_capture.yml` is *manually runnable*
but intentionally has no active schedule. Configure a least-privilege
GitHub Actions `MOTHERDUCK_TOKEN` secret, confirm the data-use permission
and a successful authenticated manual run, then enable its hourly cron.
Until then, on-demand Flights do not constitute continuous ingestion.

**Current blocker**: the Factor Lab's dated retrospective 2024–2026 factor
observations cannot be promoted into historical point-in-time data.
Current-capture market timestamps, human-approved event–factor mappings
and genuine source-available factor vintages must all accumulate and pass
independent review before statistical model release.

## Prospective factor vintages and warehouse-as-of co-observation grid — 2026-10-23

Builder: `lab/phase1_warehouse_asof_grid.py`. MotherDuck Flight
`eventrisk-factor-lab-warehouse-asof-prospective-grid` has UUID
`4b2c0eb4-06ec-42a0-9c7c-bad9b80d0e5d`.

The source-controlled program materializes three new tables in
`eventrisk_factor_lab` without changing the existing v2/v3
retrospective historical panels:

- `lab_factor_warehouse_vintages_v1`: one immutable factor ingested
  version from the existing factor observations, with the ORIGINAL source
  ingestion and availability timestamps, provider, numeric value, license
  class and SHA256; records when this particular ledger independently
  reconciled it. It DOES NOT retroactively claim that published values were
  accessible before their source warehouse ingest time.
- `lab_prospective_event_factor_grid_v1`: candidate venue market response
  receipt joined to the newest source factor observed version that the
  warehouse had **ingested and marked available before** that receipt.
  Limited to data observed within the prior ten days, permitted source
  license classes, valid hashes and real timestamp eligibility.
  This is a co-observation grid of candidate factors, not a signed semantic
  edge, causal link, market risk beta, tradable signal or performance record.
- `lab_prospective_grid_runs_v1`: exact source commit, source script
  checksum, as-of leakage diagnostics and build counts.

The first successful build materialized **12,656 factor vintage records**
and **190,008 event-factor grid rows** across 4 capture runs, 4,889 distinct
markets and 18 nominal/real Treasury series. Independent database checks
found zero future factor-ingest/availability timestamps, zero licensed-series
violations, zero duplicate market/run/factor keys, and zero approved/released
rows. The associated Flight returned `SUCCEEDED`.

**Two essential timeline caveats**:

1. **Warehouse-as-of is not independent publication-time PIT.** The
   `availability_at` and `ingested_at` values were recorded by our
   legacy factor ingestor in October 2026. We have not yet independently
   validated provider release and revision timestamps.
2. **Public market API response receipt is not venue quote time.** Our
   collector knows when it received the response, not when the exchange
   first quoted each value. For these reasons, both independent source
   timing flags, all review flags and backtesting release flags are FALSE.

The materializer is append/idempotent: input factor vintage hashes and
event-run/venue/market/factor keys are checked before insertion; later
ingestion of revised economic data cannot overwrite the past as-of version
of an earlier event capture. The guarded (manual, currently not scheduled)
GitHub workflow runs capture > research feature views > as-of builder.

Authenticated research API routes:
`GET /v1/research/forward/asof-coverage` (summary) and
`GET /v1/research/forward/grid` (bounded, explicit prospective research
flag). No user gets access to this data without the scoped database token,
API key, confirmed data rights and explicit research opt-in.

The expanded release-gate Flight version 1.2 reported **6/14** automated
checks passing, **8/14** blocking, and **4** external/manual gates outstanding.
The new passes are engineering/data-lineage checks only. Independently
validated point-in-time history, legal rights, approved mappings, source
publication/quote-time evidence and validated causal models remain blockers.

## Institutional factor-return and beta methodology — 2026-10-24

The authoritative specification is
[`INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md`](INSTITUTIONAL_FACTOR_BETA_METHODOLOGY.md),
which separates (a) the 108-item qualitative catalog, (b) measured market
factors, (c) *security return beta* to those factors, and (d) identified
event-information shocks and **factor responses**. The old same-day
venue-level regression coefficient is neither a security beta nor an
event-to-factor causal impact.

The source-controlled materializer
[`phase1_methodology_coverage.py`](phase1_methodology_coverage.py) created
`lab_institutional_data_coverage_v1` (factor-by-factor and venue coverage)
and `lab_institutional_beta_readiness_v1` (build-wide scorecard).
First MotherDuck Flight `eventrisk-factor-lab-institutional-methodology-coverage`
succeeded on October 24, 2026. It measured 22 quantitative catalog series,
20 active, 18 with any historical observations, 0 with independently certified
source publication vintages, 11,101,967 older snapshots, 565,695 retrospective
market-day features, 10,556 newly captured quotes, 190,008 warehouse-as-of
co-observations, 0 evidenced approved economic mappings, 36 exploratory
OLS fits, 72 retrospective HAC/OOS fits, and **zero independently validated
security betas or event-factor response estimates**.

### Backfill boundaries

Historical market and factor backfill is already materialized for retrospective
research. The audit explicitly records missing factor families and identifies
where factor histories are absent. No non-existent equity, FX, commodity,
style portfolio or asset total-return data may be fabricated from the
qualitative factor labels. Sources must be individually licensed, unit-
standardized, timestamped, revision-versioned and release-reviewed before
they can be used to estimate security betas. Older event-market snapshots
cannot be reclassified as truly point-in-time merely because a 2026 warehouse
now contains them.

Institutional model release remains **BLOCKED** until actual investment
return-dependent variables, PIT source factor shocks, eligible event
innovations, approved economic transmission links, robust pre-registered
event-time regressions, governance review and API/data rights have been
independently validated.


## Security adjusted-price returns and Treasury rate-sensitivity backfill — October 24, 2026

The lab already contained 107,157 historical `security_prices` records across 63 symbols. The new source-controlled `phase1_security_rate_beta_backfill.py` created versioned `lab_security_returns_retro_v1`, `lab_rate_shocks_retro_v1`, `lab_security_rate_betas_retro_v1`, and `lab_security_beta_builds_retro_v1` by a successful MotherDuck Flight. Results: 83,427 USD asset adjusted-price log-return days (49 instruments including SPY), 12,618 Treasury/derived yield-change days (18 series), 864 SPY-controlled retrospective rate sensitivities across 48 securities and 18 factors; 130 BH FDR q<.05, 414 positive retrospective holdout R² against market-only, and 49 satisfying both. All **remain unapproved**, with 12 large adjusted-price moves flagged and unresolved. See [the exact quantitative regression and units methodology](SECURITY_RATE_BETA_RESEARCH_METHOD.md). Do not confuse this market-controlled rate sensitivity with a security's licensed risk-model beta or with a causal event-factor response.

## Institutional field and cross-asset factor methodology inventory (2026-10-24)

Authoritative new source-controlled artifacts:
- [Institutional Data Dictionary and Backfill Requirements](INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md): exact separate market quote/source release/security/corporate action/FX/style/factor/model/event/portfolio requirements, timing and data rights.
- `institutional_data_contracts.py`: executable **16-dataset / 274-field** contract (255 mandatory plus 19 optional).
- `phase1_field_coverage.py`: live source completeness inventory into `lab_institutional_field_contracts_v1`, `lab_institutional_field_audit_v1`, `lab_institutional_dataset_audit_v1`, and `lab_institutional_data_contract_builds_v1`. First Flight successful: 146 missing required fields (includes six not-yet-loaded target datasets), one existing but fully null original venue quote timestamp. A populated column is never automatically certified.
- `phase1_factor_risk_diagnostics.py`: source-controlled 22-factor transform and licensing inventory plus 153 pairwise correlations among 18 percent-quoted Treasury/derived rate shocks. First Flight successful: **nine** rate pairs with absolute correlation at least 0.95, and **33** pairs touching derived nominal-minus-real proxy series. Retrospective rates are **not** independently publication-vintage verified.
- New authenticated research read endpoints: `/v1/research/data-contracts/summary`, `/v1/research/data-contracts/fields`, `/v1/research/factors/collinearity`. These cannot authorize model release or substitute for source rights.

**Production direction:** capture verifiable original quote/release timestamps, security/corporate-action vintages and total returns; source licensed equity style, FX, commodity, credit, inflation and volatility factors; implement market/factor calendars; resolve highly correlated maturity and derived factors *before* training a multifactor covariance/beta engine; obtain evidence-based event economic mapping and external model-risk approvals. The 864 existing single-factor rate regressions remain retrospective, unapproved research results. This work only changes `sanga4/event_risk`.
