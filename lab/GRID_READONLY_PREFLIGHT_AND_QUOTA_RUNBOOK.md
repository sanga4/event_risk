# Phase I grid preflight and Flight runtime quota boundary

**Scope:** Research-only. This operational check neither attests original provider quote/publication times nor approves licensing, causal links, model betas or institutional release.

## State observed October 25, 2026

The warehouse-as-of Flight was upgraded to version 2, pinned to commit 840255f716e98a901cc84da7cd8d6ad08d59ee57 with LAB_GRID_FULL_REPLAY=false and LAB_RESEARCH_SCOPE=internal-only. The last successful Flight, run #8, used version 1. The first v2 execution request was **rejected before execution** because this organization had exhausted its included 30 minutes of daily Flight runtime. Version 2 has NOT yet been remotely executed or benchmarked.

At this handoff, the research database held 806,004 event-factor grid rows representing 44,778 capture-market records over 11 runs; a separate read-only check found zero unrepresented capture identities, duplicate factor keys, future warehouse timestamps and unsupported approval flags. The data are still NOT genuine provider as-known PIT data.

## Read-only operational preflight

Use a scoped **read-only** token permitting SELECTs on eventrisk_factor_lab:

    python lab/phase1_grid_preflight.py

The script executes only SELECTs. It emits machine-readable JSON and returns exit code 0 for a structurally valid research grid, or 2 when missing data or integrity violations block processing. It does not use Flight runtime, but database query/compute charges may still apply.

Results are one of:

- INCREMENTAL_CAPTURE_SCOPE_NONEMPTY: new source identities (run_id, venue, market_id) need processing.
- INCREMENTAL_CAPTURE_SCOPE_EMPTY: all stored capture identities are already represented by at least one factor grid record.
- BLOCKED_GRID_INTEGRITY: future factor timestamps, duplicate keys, false warehouse validity or unsupported release flags.
- BLOCKED_MISSING_RESEARCH_DATA: capture source or target grid is empty.

**Important:** Having one factor observation for a capture does not guarantee all newly eligible factors have been considered. An upstream factor-catalog, source-time, rights-eligibility or approved-methodology revision requires deliberate explicit historical replay (LAB_GRID_FULL_REPLAY=true) after review; the default incremental run will skip already represented capture identities. The preflight does not itself decide whether full replay is required.

## Remote Flight v2 acceptance checklist, after daily quota permits

1. Re-check the Flight's active current version (2), pin, scope, no full replay, and absence of overlapping runs.
2. Record the preflight JSON, current capture identities, and persisted grid rows.
3. Trigger exactly one remote run of the pinned version and inspect its terminal status and logs, especially CAPTURE_GRID_REFRESH_MODE, STAGED_CAPTURE_MARKETS, NEW_GRID_ROWS, and WAREHOUSE_FUTURE_FACTOR_LEAKAGE.
4. Independently recheck source-to-grid identity coverage, duplicate keys, warehouse future data, immutable row counts, and the append-only producer build manifest. A 0-new-row run is expected only when no eligible new captures or source vintages arrived.
5. Compare runtime only to a genuinely comparable workload. A zero-candidate incremental run is not a valid speed benchmark against a historical full-replay run.
6. Refresh the formal release gates and blocker register after a verified success. Their independent PIT, evidence, rights, access, and model-risk blockers remain binding.

No cron, legal signoff, data rights acknowledgment or release approval is implicitly enabled by this preflight. The legacy MVP is a separate deployment and should not be treated as the research system.
