# Source lineage hardening and unattended QA batch

As of October 24, 2026 (Los Angeles). Research use only.

## Reconciliation correction

Adjustment audit v1.1.0 calculates the previous observed source date before
excluding duplicate or invalid records. A valid observation immediately after
an excluded date cannot be silently paired with an older valid price. Actual
calendar gaps remain visible; this is not an exchange-calendar certification.

An exception reconciles only when its previous date, current and previous
adjusted prices, current raw close, vendor, currency, run ID, retrieval time and
reported return agree with the source pair. The log-return algebraic identity
alone cannot validate a stale or differently sourced exception. This does not
verify corporate actions, economic causes, historical publication or rights.

Read-only MotherDuck checks against the current source snapshot found:
- 0 intervals currently bridged across excluded source dates;
- 369 adjustment-ratio candidates remain under the stricter adjacency rule;
- all 12 current flagged cases match their recorded source prices, interval,
  vendor, currency, run and receipt time.

These results show no present count regression; adversarial tests demonstrate
that new duplicates, invalid records and stale provenance fail reconciliation.
No raw prices, reviews or approval flags were changed for this audit.

## Run outside a chat session

After this workflow is merged to the default branch, use GitHub Actions →
**Factor Lab source QA batch** → **Run workflow**, selecting the intended ref.
A scoped `MOTHERDUCK_TOKEN` repository Actions secret is required. Never paste
it in a conversation or commit it. The workflow does not create credentials.

The sequence is offline tests → price exception audit → strict adjustment
reconciliation → evidence requirements → release assessment → blocker register.
Each stage is a separate job. Successful stages remain complete when using
**Re-run failed jobs**; a rerun retains the original source commit. Every data
stage has a 45-minute bound. GitHub owns execution after dispatch, independent
of the chat connection. This is a finite QA batch, not an autonomous developer
or a promise to finish institutional approval.

Stage summaries retain emitted build IDs and source commit. Existing producers
append versioned build results transactionally; retrying a failed stage can
append another build if the prior commit succeeded before the process failed.
This is at-least-once execution, not exactly-once processing. Source tables are
not overwritten. A green job means successful execution, not all gates passed.

The batch concurrency group prevents overlapping copies of this workflow only.
Other Flights or ingestion jobs can still write to the warehouse. Existing
producers read latest upstream builds, so this is not an immutable database
snapshot or a fully isolated cross-job transaction. For a certified replay,
freeze a source snapshot and pin all upstream build IDs first. A partial rerun
with changed warehouse inputs must be interpreted as a new research assessment.

No schedule, automatic production promotion, approval bypass or automatic
infinite retry is enabled. Hardcoded source-universe checks in existing
producers deliberately stop if case counts change; investigate and version
those assumptions rather than bypassing them.

Remaining blockers: original evidence/rights, independent reviewers, source
vintages, covariance stability, and production access controls remain open.
