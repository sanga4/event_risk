# Phase I prospective research grid — source-lineage and ten-day as-of acceptance

## Purpose

Phase I's 806,004 persisted prospective event-to-rate **research co-observations** must be reconciled to the stored capture receipts and exact versioned factor records. A row matching chronological warehouse timestamps is not enough if its source event payload changed, its factor vintage has been overwritten, or its source license class silently changed.

The read-only tool added in PR #49 checks exact persisted identities and source values:

    python lab/phase1_prospective_lineage_reconciliation.py

It independently joins every stored event-factor observation to:
- Source event identity run_id + venue + market_id, checking its source SHA256, proposition ID, probability and collector receipt-time equality.
- Factor warehouse vintage identity factor_id + observed date + digest + source ingested-at time, checking value, unit, availability, license class, provider and source run ID equality.
- Producer semantics: factor observed between 0 and 10 calendar days prior to the receipt date, ingested/available no later than capture, percent units for currently approved research rate factors, a strict three-class source license allowlist, finite and bounded numbers, lowercase SHA-256 integrity identifiers.
- Research-only approval flags, data-use class and unreviewed co-observation relation label.

It also detects duplicated source capture identities, duplicated factor source-version identities and join amplification, instead of accepting those duplicates as legitimate new independent observations. No external provider publication timestamp or independent data rights may be asserted by this script.

The tool emits PASS_RESEARCH_WAREHOUSE_LINEAGE_ONLY, BLOCKED_RESEARCH_SOURCE_LINEAGE or BLOCKED_NO_PERSISTED_GRID. A failed check exits code 2; no MotherDuck Flight is started and all SQL is SELECT-only. Even a passing result certifies only correspondence between *stored warehouse sources*, not whether source bytes truly came from an exchange/vendor or were historically known to market participants.

## Grounded baseline: October 25, 2026 read-only verification

- Stored grid: 806,004 rows across 11 prospective runs, 4,889 unique venue/market identities.
- Corresponding captured market input: 44,778 capture-market identities over 11 receipt runs.
- No missing source capture or factor-vintage link, no event timestamp/hash/probability drift and no versioned factor-value/unit/availability drift.
- No duplicate source identity rows, invalid SHA256 format or unsupported factor license class.
- Factor age at event receipt: minimum one, maximum three **calendar** days, within the strict 0–10-day research join horizon.
- Publisher quote/release clocks, commercial rights, independent causal economic mapping and institutional historical PIT release: **unverified or blocked**. Do not equate factor observed date with first-publication date.

These counts are a point-in-time read-only snapshot of existing warehouse data and need recomputation after new source capture or producer materialization. Source as-of-clock verification is strictly at *our warehouse* time, not independent historical source availability.

## Integration

The manually authorized GitHub Actions workflow from PR #48 now runs the expanded lineage check both before any opted-in append operation and afterward. Any parent source drift, false approval flag or new unsupported license class blocks the research acceptance job. It does not enable a cron schedule, call an external provider, request source rights or change Railway.

For future factor types whose unit is not percent, a versioned change to this research grid contract and its tests is mandatory: do not silently add unit types to preserve green checks. Similarly, eligibility changes for already represented captures require explicit reviewed full replay rather than the default incremental-only producer.

## External sources and methodology still outstanding

Independent original exchange quote time, original macro first-publication and revision-vintage records, signed commercial entitlement and security corporate actions remain the primary source dependencies. An economic event surprise also needs genuinely *pre-event* expectations, a timestamped realization, objective cutoffs and an independent analyst-approved channel mapping; this grid alone provides none of those. Security risk betas remain retrospective research statistics, not production estimates.
