# Historical market snapshot source-span contract

The institutional source evidence matrix previously recorded **11,101,967** historical venue market snapshots but left `first_observed_date` and `latest_observed_date` NULL. This was because the source specification for `market_snapshots` had an empty date column even though its native `ts` column is present.

The corrected `lab/phase1_source_family_evidence.py` records MIN(CAST(ts AS DATE)) and MAX(CAST(ts AS DATE)) in the next **append-only** source-family inventory build. The live read-only warehouse independently established **July 8, 2021 through October 22, 2026**, with **1,857 distinct observed calendar dates**, no NULL snapshot timestamp and no records timestamped more than five minutes in the future. Inclusive span length is **not** the same as the number of observed dates or independent economic outcomes. A fail-closed source contract rejects missing, reversed, future or implausibly old source observation days.

Crucial distinction: `market_snapshots.ts` is a retained **historical event-time observation field**, not an independently verified original publisher `published_at` nor a proof the warehouse or trader possessed the data on that day. The correction intentionally leaves `last_local_retrieved_at` NULL for this source because there is no verified receipt timestamp column. `research_semantics=RETROSPECTIVE_ONLY`, `provider_original_publication_verified=FALSE`, `commercial_reuse_approved=FALSE` and `institutional_factor_model_approved=FALSE` remain unchanged.

After the corrected inventory is run, the independent `lab/phase1_source_temporal_depth_audit.py` should no longer flag the missing date span; the family's disposition should become `POPULATED_BUT_ORIGINAL_PUBLICATION_PIT_AND_RIGHTS_UNVERIFIED`. No one should infer a source as-of backtest, economic event surprise, causal exposure or rights clearance from this metadata improvement.

This repair touches only the versioned institutional source-family inventory and its tests. No historical price rows, venue quotes, factor beta coefficients or existing gate approvals are overwritten.
