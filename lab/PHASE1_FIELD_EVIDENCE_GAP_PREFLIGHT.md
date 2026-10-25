# Phase I field-evidence gap preflight and contract type safeguards

**Source ledger timestamp:** 2026-10-24 23:06 UTC. Read independently on October 25, 2026. This is an existing audit snapshot, not a fresh scan or a production certification.

## Evidence summary

The MotherDuck lab data dictionary specifies 16 institutional datasets and 274 field rules, of which 255 are mandatory. The last successfully written audit has **135 missing mandatory fields**, **1 present but entirely unpopulated mandatory venue quote-time field**, and **119 present/populated yet institutionally uncertified mandatory fields**. All 255 required rules remain institutionally uncertified. The preceding snapshot reported 146 missing fields, so structural missing-field counts decreased by 11 but source/PIT/legal approval did not change.

Use a scoped read-only MotherDuck token and execute:

    python lab/phase1_source_field_gap_preflight.py

This script selects one latest immutable build manifest and the corresponding exact field and domain rows, reconciles the manifest counters, checks for mixed builds, duplicated fields, conflicting source counts, invalid field-status rules and unsupported source approval flags, and emits all mandatory missing/empty source fields as machine-readable JSON. **It does not rescan raw source tables** and it cannot replace a new, versioned institutional-field-audit run. Its SQL is SELECT-only and does not spend Flight runtime; ordinary database query compute may still apply.

## Updated schema checks

The field-audit producer now requires BOOLEAN type for rights/approval fields ending with _approved and for licensed_redistribution. It requires NUMERIC for n_effective and calendar_cluster_robust_se, and STRING for source SHA256/digest and permanent security identifier evidence. Adversarial CI tests demonstrate these incorrect types are rejected.

A type-valid TRUE flag is not a license agreement, independent provider timestamp, source-payload proof or model approval. Strings holding arbitrary data are not verified hashes merely because their types match; hashes require independent byte-for-byte lineage QA.

## Top original-source gaps (last audit)

| Source domain | Source rows at audit | Required fields missing | Unblocked by |
| --- | ---: | ---: | --- |
| Source release calendar | 0 | 12 | Original provider publication/revision records, source bytes and rights |
| Event innovation | 0 | 13 | Announcement time, independent pre-event expectations and reviewer evidence |
| Security prices | 107,157 | 12 | Original issuer IDs, corporate-action vintages, return adjustments and rights |
| Factor observation | 12,656 | 6 | Original Treasury/FRED source release/revision time and archived bytes |
| Historical market quote | 11,101,967 | 4 | Exchange-native quote/publication history and immutable payload records |
| Event to economic factor mapping | 8,216 | 9 | Evidence signatures, first-available clocks and attributed peer review |
| Prospective quote receipt | 15,445 | 0 missing, 1 empty | Native provider quote time, not substituted with HTTP receipt |
| Asset factor model | 0 | 19 | Independently validated, as-known and rights-approved security factor model |
| Position exposure | 0 | 14 | Permitted holdings, original security identifiers and FX |
| Factor scenario | 0 | 13 | Reviewed scenario factors, shocks and uncertainty |

The remaining six contracted domains also have gaps. All 16 are included in the new read-only output.

## Acceptance order

1. Obtain original exchange/provider source versions and legal entitlements; preserve immutable source hashes, original publication/version clocks and observed capture clocks separately.
2. Load primary security masters and corporate actions with as-known symbol histories; reconcile existing adjusted-price exceptions before approving any beta.
3. Load real provider release calendars and pre-event consensus data. Do not generate fake event surprises from daily historical hindsight joins.
4. Rebuild the versioned field audit only after genuine source ingestion, verify stricter data types and reconcile all 16 source contracts against the producer manifest.
5. Obtain actual external analyst, rights and model-risk review. The automated field ledger must not issue approvals.

**Institutional status:** the latest recorded formal gates remain 22/47 passing, 25 blocked plus four manual approval requirements. This change does not authorize institutional trading, data redistribution, risk models or production access.
