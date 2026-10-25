# Source-reconciled event–factor v3.1 (forward-only, research-only)

Executable `lab/phase1_v31_factor_source_repair.py` creates a new separately versioned dataset `eventrisk_factor_lab.main.lab_event_factor_panel_v3_1`, never overwrites legacy v2, legacy v3 or any raw factor observation.

## Root-cause and source truth

Legacy `lab/phase1_build_v3.py` constructs a temporary curve with `SELECT d.observed_date, d.cutoff_at, f.*`, where `f.*` itself also includes `observed_date`. The later unqualified `c.observed_date` refers to the **event date**, not the factor source observation date, causing a false non-carried label for 76,662 rows and re-dating their historical factor observation by 1–2 days. This is not a provider-time-first-known-at claim; it is an internal join-column namespace defect.

The corrected v3.1 materialization uses a **three-way exact join** of historic v3 + v2 (event proposition, factor, event observation date) and `lab_factor_observations` by the factor's source identity (`factor_id`, `record_sha256`, and `run_id`). Replaces `factor_observed_date` with the source row's actual observation day and recomputes `factor_carried_forward` by comparing factor source day with event observation day. It also uses the preexisting validated v2 `previous_aligned_factor_value` and `factor_daily_change` for aligned factor changes in bps, preserving the factor's native level unit of percent. It retains all original v3 fields, plus original build/run IDs and immutable source-row reconciliation markers.

Audited original sample: 233,442 rows, 18 factors, original-source verified date changes **76,662**, carry flags changed **76,662**, significant aligned-change differences / previous missing versus valued **2,806**. Remainder of exact float inequality was sub-microbps floating arithmetic noise; the correction uses v2 values rather than forcing exact floating equality across independently computed formulas.

The preflight refuses source joins that introduce duplicates/missing rows, any original-source hash/unit/value/availability mismatch, any discrepancy in source-side v2 original observation dates or carry flags, any missing source family or false publication/licensing/release claims. It checks the v3.1 staged output before committing. Two new tables are append-only, one corrected versioned panel and one manifest `lab_event_factor_v31_repairs_v1`. **Always filter on the latest manifest build ID**: do not pool multiple builds as independent observations.

**No independent historical PIT certification:** the source price/value file was ingested later; source observation day is not original public release time. V3.1 is a more internally consistent **retrospective** factor alignment only. Underlying event quote prices, factor values, issuer corporate actions and provider original publication clocks remain unapproved. The builder does not compute a causal event effect or grant licensed institutional reuse.

The only required run variables are LAB_RESEARCH_SCOPE=internal-only and LAB_PIPELINE_COMMIT pinned to the versioned source Git SHA. There is no cron, protected API export or distribution license authorization.

Use the read-only `lab_event_factor_panel_v3_1_latest` view to select a single current build safely. The append-only history table intentionally contains multiple builds after reruns and must never be analyzed without an explicit build filter. The latest view is an **internal research convenience only**, not an approved signal feed.
