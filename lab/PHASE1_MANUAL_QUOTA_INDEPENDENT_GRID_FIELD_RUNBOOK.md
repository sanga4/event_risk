# Phase I manual grid and field audit: quota-independent operations

## Context and strict boundary

On October 25, MotherDuck refused to dispatch Flight v2 because the daily included Flight runtime allowance was exhausted. This new **manually dispatched GitHub Actions workflow** runs audited source-controlled research scripts on a GitHub runner with a least-privilege MotherDuck token. It does not run either MotherDuck Flight version 2, does not evade MotherDuck warehouse query/compute charges, and does not authorize vendor data usage or institutional beta release. Missing/invalid tokens cause an explicit error.

Workflow: .github/workflows/phase1_manual_grid_field_acceptance.yml

## Operator instructions

1. In GitHub repository Settings -> Secrets and variables -> Actions, configure repository secret MOTHERDUCK_TOKEN using a scoped, properly authorized research warehouse token. Do not paste secret values into chat, issues, commits, artifacts or logs.
2. Select GitHub Actions -> Phase I research grid and institutional field audit (manual) -> Run workflow, targeting a reviewed main commit.
3. The **default preflight_only** operation only runs existing offline tests, SELECT-only grid and field-ledger preflights, and bounded read-only summaries. No warehouse data are appended in this mode.
4. To perform explicit restricted research metadata/data writes, select incremental_grid_only, field_contracts_only, or incremental_grid_and_field_contracts and opt into confirm_research_writes. The workflow fails if a mutating mode lacks explicit confirmation.
5. Inspect the **terminal** success/failure and the final producer manifest validation. A dispatched workflow, passing liveness check or completed script subprocess alone is not proof of persisted data or of institutional acceptance.

## Engineering safeguards

- Pinned immutable SHA from the GitHub runner, internal-only research scope and LAB_GRID_FULL_REPLAY=false.
- Shares the prospective-capture GitHub Actions concurrency group to minimize race conditions. Independently started MotherDuck Flights are not locked by GitHub concurrency and must be checked before starting a manual run.
- Repository-offline regression suite must succeed before any remote database access or writes.
- Read-only baseline tests independently check duplicate capture-factor identity, factor availability not later than collector receipt, research approval flags and field ledger provenance. Baseline JSON is retained in runner-local temporary storage instead of exposing full domain data in logs.
- Explicit research execution appends records only via existing source-controlled grid and field-audit producers.
- Read-only post-run handoff checks the **latest** producer append-only manifest, exact Git commit, local producer SHA256 digest, positive/zero counts and immutable research-only statuses; it fails on unsupported release flags.
- Final preflights require persisted rows to be nondecreasing, no new future factor availability or duplicate keys, no unrepresented capture-identity growth during the workflow and no false independent field certification.
- Does not run collectors, alter API permissions, change Railway variables or enable scheduled market source collection.
- Does **not** establish authentic original provider publication/quote timestamps, legally approved redistribution or independent statistical model validation. No risk model or historical PIT backtest is released.

## Prior evidence, not freshly executed claims

The previous database research snapshot had 44,778 market-capture identity rows across 11 capture runs and 806,004 warehouse-as-of event-factor co-observations. Existing structural checks found zero unmatched capture identities, duplicate event-factor keys or source factors available after event receipt. The last October 24 institutional source-field audit had 16 datasets, 274 field rules, 135 missing mandatory, one completely unpopulated mandatory quote publication-time field and 255 independently uncertified mandatory fields. The new workflow must actually execute to update any research database record.

## Next substantive source and methodology dependencies

Original publisher quote/publication clocks with immutable exact payload bytes; independently evidenced first-release/revisions; authorized permanent security master and corporate actions; pre-event market expectations and consensus; license-scoped credit, tradable FX, commodities and volatility; independent reviewer attribution; valid chronological heldout beta/covariance model-risk review. The new original-source integrity intake verifier checks bytes and clock consistency but cannot confer authenticity, PIT certification or rights on its own.
