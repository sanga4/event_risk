# Phase I — Event-to-factor temporal and unit-semantics acceptance firewall

**Scope:** internal research only. Executable producer: `lab/phase1_event_panel_semantics_audit.py`. This is an independent read-only source reconciliation followed by append-only audit manifests and per-factor evidence in MotherDuck `eventrisk_factor_lab`; no original event/factor rows are edited.

## Three fundamentally different provenance standards

- **Historical v2:** daily retrospective event/probability observations against revised Treasury factor values. `factor_available_at` is **after** `event_cutoff_at` in all 233,442 rows, and `data_lookahead_warning` is true for all. Native factor level inputs are percent; *factor daily changes* are `bps`. This is NOT original-provider published-at as-of data.
- **Historical v3:** contains 233,442 event-factor rows, identical event/probability/level values keyed to v2, but factor availability is after `event_known_at` for every row. `factor_unit='percent'` correctly denotes the native factor level; `factor_change_bps` correctly denotes changes, so do not falsely declare a unit error. All rows are explicitly retrospective, unreviewed and `internal_research_only`.
- **Prospective warehouse-as-of:** 630,018 event/factor co-observations in the last verified snapshot, with 0 future factor availability relative to HTTP receipt time and 0 independently certified quote-publication dates. This only demonstrates **warehouse receipt availability**, not first-publication time, source redistribution approval, causal attribution, or a safe historical trading backtest.

## V2→V3 semantic mismatch requiring independent investigation

Matched 233,442 exact factor/event/date keys and values/probabilities/deltas across v2 and v3; however **76,662** v2 rows have `factor_carried_forward=TRUE` while their v3 counterparts have `factor_carried_forward=FALSE` and `factor_observed_date` advanced by **1–2 calendar days**. Do **not** silently harmonize observation dates or treat v3 as better PIT data just because the carry flag disappeared. The audit retains both discrepancy counts and the intersection; no factor value was changed and the economic validity of carry-date semantics is unapproved. Investigate the originating transform and preserve accurate factor observation dates before any event-study use.

A later known-at event cutoff occurring after the last venue quote is not itself a clock error: quoting and aggregation cutoffs have different meanings. The unacceptable historical-as-known claim is the **factor source becoming available after the event cutoff**.

## Safety and acceptance contracts

Every run enforces 18 expected factor IDs per dataset; complete cross-version joins; identical event/factor levels and probability deltas; no duplicate factor/event keys; no unflagged retrospective factor lookahead; no prospective warehouse future-factor rows; fixed research-only status; expected **native factor level units = percent** and retrospective **factor change units = bps**; valid probabilities and 64-character checksums. On any failure it raises before writing new audit evidence.

Materializes `lab_event_panel_semantic_audit_builds_v1` (1 row per execution) and `lab_event_panel_semantic_audit_factors_v1` (18 per panel, 54 subjects per build), with source Git SHA and script SHA256. Historical PIT certifications, approved causal relations, licensing permissions and institutional model release are never set. These counts come from a sequence of warehouse queries and do not guarantee a physically immutable read snapshot of concurrently ingested sources.

**No retrospective observational correlation can certify event-caused Treasury rate repricing.** The next modeling research requires original provider publication clocks, matched pre-event controls, revised-vintage recovery, confounder tests, calendar/exchange conventions, independent economic-channel mappings and approved data rights.
