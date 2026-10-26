# Phase I — Independently attest a Treasury current-month source-receipt build

**Auditor:** `lab/phase1_treasury_receipt_acceptance.py` — SELECT-only; all output is internal-research evidence.

**Producer:** `lab/phase1_treasury_current_xml_refresh.py` (PR #59).

## Actual remote execution note — October 26, 2026 UTC

The first fully authorized source append **did persist** 108 official Treasury XML-backed internal research factor records, spanning six observed factor days. The combined on-demand producer+auditor Flight exited nonzero because the Flight dependencies omitted `pytz` while DuckDB loaded timezone-aware SQL values. A separate subsequent read-only audit Flight with `pytz` also initially failed **before accessing any audit rows** because MotherDuck remote session timezone `Etc/Unknown` cannot be mapped to a `pytz` timezone. This is an auditor runtime configuration failure, **not evidence of source arithmetic validity or invalidity**. The new auditor now executes `SET TimeZone='UTC'` on its MotherDuck connection before calling SELECT/fetchall; the resulting timestamps remain original UTC instants. The source rows are NOT to be re-appended merely to get an auditor result. Run the corrected, read-only auditor against the original pinned writer build `phase1-treasury-current-xml-refresh-v1.3.0-20261026T011511640541Z`. Reconcile source packet hashes, 108 actual rows, old-retrospective exclusion and all false publication/right/approval flags. A passing audit is required to close this acceptance incident.

## Trust boundary

Treasury's recorded `NEW_DATE` is an observation-date label, **not** a separately verified first-publication timestamp. This audit verifies exact downloaded Treasury XML bytes, SHA256, source URL, actual HTTP receipt times, matching warehouse rate values, and the Git-pinned research build. It NEVER authenticates provider first-publication chronology, original historical vintages, licensed redistribution, an economic surprise, causal event-to-factor betas, or institutional risk model release.

The manually opted-in research append workflow now executes the independent auditor after completing the source fetch and warehouse write. A successful append process alone is not the acceptance criterion. A separate copy of the raw source is retained in the source packet table.

## Acceptance contract

- Source build manifest must match the **exact checked-out Git SHA** and the SHA256 of the producing Python script, with precisely two independent source packet categories: nominal and real.
- Both persisted raw XML payloads must re-hash exactly, come from the two fixed allowlisted official URLs, have timezone-aware receipt timestamps preceding the producer finish time, and have *FALSE* original-provider-publication and source-rights approvals.
- Independently reparse each packet and reconstruct all **11 nominal + five real + two labeled derived** par-rate values per complete observed date. Missing/duplicate tenors, malformed dates, unexpected XML families, packet tampering or original receipt clock drift fail closed.
- Reconstruct the **same prior XML-packet-backed warehouse source inventory** that would have existed at original fetch receipt. Legacy retrospective CSV values do not constitute previously downloaded original XML evidence, even if their yield levels match. Exclude the current run's factor rows; choose the latest earlier stored source record per factor/date. This supports valid *zero-new-row* no-op manifests while rejecting invented empty reports that conceal genuinely new or revised rates.
- Compare every new/revised factor record to its source date, per-factor content SHA, native percent unit, two-case provider classification, availability-basis marker and real recorded receipt timestamp. Require `warehouse.ingested_at == warehouse.availability_at == actual warehouse append time`, and reject any warehouse clock *before* the original HTTP receive time; no backward dating or fake source first-known assertions.
- Compare the manifest's accepted date count and newly inserted factor rows against independently recomputed deltas; detect duplicate records and unsupported institutional approval flags. Any failed acceptance exits nonzero.
- The research workflow is manually dispatched; preview is the default and writes nothing. Append mode requires an authorized scoped `MOTHERDUCK_TOKEN` secret and opt-in, and the post-write auditor MUST succeed to count a full research source acceptance.

## Manual run

From the repository's GitHub Actions panel, select **Phase I Treasury nominal and real recent source XML (manual)**. Its `append_research_records=false` preview is preferred first. After reviewing the source data and respecting source terms, an authorized operator may select `append_research_records=true` to append an actual receipt-time research build. The audit runs automatically on this path. An external independently scoped MotherDuck read-only token may run:

```bash
LAB_RESEARCH_SCOPE=internal-only python lab/phase1_treasury_receipt_acceptance.py --source-commit <exact producer Git SHA>
```

A successful audit establishes **internal lineage only**. It does not retroactively turn the already captured October 23–25 event-market receipts into independent historical factor source days. New real future venue receipts *after* the refreshed factor source become eligible for warehouse-as-of co-observation; separate independent first-publication source certification and contractual rights remain mandatory.

## Materialization evidence

At development handoff (October 25, 2026), PR #59 and this independent acceptance logic are engineering changes. No live Treasury source refresh or later venue capture has been verified, the old grid remains 806,004 research co-observation rows with one observed factor date, and formal institutional release remains blocked. A merged PR or green synthetic CI is **not** the same as running the GitHub Action or inserting historical source records.
