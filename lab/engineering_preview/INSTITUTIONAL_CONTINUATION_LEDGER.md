# Institutional Phase I continuation ledger — outside the engineering preview

**Status date:** October 26, 2026 UTC. **Decision:** Finish a restricted, research-only engineering preview without mutating or claiming completion of institutional risk modeling. This is an intentionally unfinished-work backlog, not a release approval.

Authoritative historical release snapshot: MotherDuck `eventrisk_factor_lab.main.lab_release_gate_summary_v1`, build `phase1-gates-v2.4.0-20261026T021002390238Z` as of 02:10:05 UTC. **25 automatic PASS / 29 BLOCK, 4 independent manual blockers, production FALSE**. Source BEA original actuals ingested later at 03:23:53 UTC. Existing 54-gate manifest predates that source ingest; rerun review/approval is a separate prospective gate action.

## Remains NOT finished (must not be silently marked complete)

| Area | Known current evidence | Remaining proof / build work | Responsible function | Acceptance checkpoint |
| --- | --- | --- | --- | --- |
| Independent source availability / historical PIT | Historical rate/event/issuer data are predominantly retrospectively retrieved; received-at is preserved | Original publisher/venue first-known clock, source revision history and snapshot version; no retroactive inferences | Data engineering + original vendors | Independent side-by-side first-available source replay with archived hashes, release clock and revision IDs |
| Venue quote chronology | 49,666 receipts across 12 capture runs but only 4 distinct capture UTC days; original quote creation unknown | Approved scheduled capture with real keys, freshness monitors; 60+ independent capture days and multiple genuine quote innovations | Ingestion/DevOps + venue-rights owner | Freshness and quote-publication proof; independently recomputed capture-day and run counts |
| Prospective factor depth | Grid has 893,988 co-observation *rows* but just 2 observed source factor dates; 18 factor labels do not multiply samples | 30+ distinct factor-source dates with actual value variation; >60 capture days, valid as-of joins | Data engineering + econometrics | Recompute distinct independent event/factor dates and effective sample sizes; holdout eligibility |
| Economic first-print surprises | BEA 2 original packets, 10 published native-unit values accepted; 13 future schedule items; original first-release calendar still not complete | Original as-published release-time snapshots, pre-release survey consensus versions, native-unit actual-minus-consensus algorithm; no backdating | Macro data + data governance | First-known before/after timing, consensus known-before-event, independent reparser and real event novelty verification |
| Data inventory | 16 dataset contracts, 274 fields, 255 required, 135 missing and 255 uncertified (2026-10-26 audit) | Prioritized genuine original data backfill, exact type audits, approval evidence. Do not fill gaps with fabricated NULL-as-known data | Data eng + source provider | New actual field audit run with decreasing verified omissions and independent certification |
| Institutional named datasets absent from contract snapshot | `lab_multifactor_security_betas_v1`, `lab_portfolio_positions_v1`, `lab_event_innovations_v1`, `lab_factor_scenarios_v1`, `lab_source_release_vintages_v1` are absent in this audit (some other exploratory tables exist) | Approved typed source contracts and actual primary evidence before materializing risk/positions/event-impact products | Quant engineering + positions owner | Independently reviewed lineage, permissible data and source-vintage replay for each required contract |
| Security master / corporate actions | 48 research securities and price/adjustment audit, but original total-return and delisted security histories not verified | Permanent issuer IDs, delisting universe, splits/dividend announcement versions, audited adjusted returns and redistribution rights | Security data vendor + quant QA | No unresolved price exception or survivor/adjustment vintage faults |
| Multivariate beta robustness | 96 SPY/Treasury/SOFR-EFFR model fits, 20,064 daily paired losses; **zero Holm-supported funding candidates**; regime/covariance instability observed | Better predeclared shocks, source validity, robust covariance and regimes; true economic-event identification; holdout after approval | Quant methodology + independent model validation | Independent checks of reference data, assumptions, multiplicity, effective dates, tail controls and outcomes |
| Event-economy-factor mapping | Proposed relationships and evidence/review queues; no independent approved event response matrix | Original citations, timestamped mechanism evidence, reviewed/rejected alternatives and dual signoff | Economics reviewer(s) | Dated approved mappings on genuinely available source evidence |
| Legal and licensing | Raw research sources recorded, but no commercial usage/redissemination entitlement assumed | Source-specific vendor contracts, permitted reuse scope, legal attestation and access segregation | Data licensing/legal owner | Written rights evidence, no unapproved third-party API data distribution |
| Production auth and operations | Railway factor-lab API runs older PR #44; its service variable-name inventory did NOT show `LAB_API_KEYS` and `MOTHERDUCK_TOKEN` in the prior check, `/health/live` was online | Confirm scoped secrets in Railway privately, rights policy, auth tests, alerting, tracing, restoration/rollback, safe deployed SHA | DevOps/security and project owner | Auth success/fail negative tests and audited readiness; do not bypass `LAB_DATA_RIGHTS_ACK` |
| Independent governance | Four external/manual release blockers remain, no signed model/data-rights approval | Research, access controls, licensed data and model-risk signoffs | Independent reviewers + committee | Explicit human-signed acceptance manifest and release committee decision |

**Automatic release gates are not the same as completed engineering tasks**; percentages of automatic passes should never be called objective percentage completion. The existing passed gate count is a historical snapshot, not a new audit after the BEA receipts.

## What preview completion IS allowed to claim

- Research infrastructure, event/factor panel and retrospective model diagnostic sources exist and are queryable with correct access.
- Source and review flags are faithfully displayed, including failures.
- A restricted preview allows browsing approved aggregate status, risk diagnostics and precisely identified unfinished work.
- UI, reproducible snapshot extraction, unit/security tests and a safe standalone preview deployment/local experience have actually passed.

## What preview completion MUST NOT claim

- Institutional event impact beta, causal event surprises, predictive alpha, tradable risk signals, point-in-time-valid investment backtests or portfolio stress output.
- Approved source publication timing, venue quote exchange creation timestamps, historical issuer action vintages or vendor redistribution rights.
- A new institutional release-gate score without running its actual pinned producer, gate acceptance and governance.
- Scheduled ingestion or a live dynamic research frontend when only a static fixture build was shown.

## Continuation order when preview is ready

1. Rerun current read-only field/gate inventories and reconcile original source state vs the dated manifests, without altering historical approval records.
2. Source/rights work: legally approved timestamped venue originals, BEA release/consensus first prints, Treasury/NYFed revisions, security master/corporate actions.
3. Genuine prospective observations accumulate over calendar time; collect independent days/runs/levels, not inflated same-day cross-products.
4. Independent reviewer-signed event-to-economic mechanisms; causal shock design, deconfounding and negative controls.
5. New models and asset beta calibration on version-true, permissioned sources, predeclared holds; multiasset covariance and sensitivity reviews; show failing models.
6. Security/operations: private authenticated access, scoped tokens, observability and role review; independent model-risk/legal release gate signoff.
7. ONLY if all operational, model and third-party rights gates close, consider a separately reviewed institutional release.

## Handoff protocol for future work

At the end of each continuation batch, record in `ENGINEERING_PREVIEW_HANDOFF.md` (preview) or the Phase I status document (institutional):
- exact Git main SHA and branch / PR merge ID;
- actual MotherDuck database, table/build identifier, source-retrieval and ingestion timestamp, distinct economic sample/date counts and provenance SHA;
- executed test commands, CI and Flight run IDs + terminal status;
- Railway project/service deployed SHA, public/private routes tested, authorization check status;
- changes performed, changes only planned, *what remains blocked*, next P0 tasks, dependencies owned by user/vendor;
- release gate count **only if newly executed and independently accepted**.
Never infer a sandbox link or a deployment URL without current verification.

**Canonical sources:** `../PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md`, `../PHASE1_PRODUCTION_UNBLOCK_PLAN.md`, `../INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md`, `../PHASE1_BEA_ECONOMIC_GATE_FRESHNESS_PREFLIGHT.md`.
