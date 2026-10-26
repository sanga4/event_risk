# EventRisk Factor — Phase I Engineering Preview (four-prompt execution contract)

**Purpose:** A small, parallel engineering-only workstream to provide an honest, usable visual inspection of the existing Phase I research system. It does NOT finish institutional production validation, claim event-impact forecasting, or alter the legacy MVP. The project does not earn approval merely by being technically demonstrable.

**Baseline verified:** 2026-10-26 UTC. Canonical repo `sanga4/event_risk`, starting at merged PR #72 SHA `2c7bc00bb71c6892d910459558679354b74015b2`. Lab source `md:eventrisk_factor_lab`. Separate canonical institutional and institutional_staging databases remain untouched. Existing Railway `eventrisk-factor-lab/factor-lab-api` is online on an earlier PR #44 deployment. The `huimarco/event_risk` legacy Railway service is NOT the target.

## Two definitions of done

1. **Engineering PREVIEW complete** (this bounded mini-project): a visible, clearly labeled, researched-data-limited web experience showing real current/pinned aggregate progress, event-factor methodology, source lineage and release blockers; repeatable fixtures and build; passing offline and integration checks; its own safe deployment or local run; handoff document. This is the target for a ~4 substantial-turn effort (including the present scope/handoff turn); a fifth turn may be needed for credentials or deployment issues.
2. **Full institutional Phase I complete:** historical first-publication and revision evidence, actual pre-event expectation vintages, licensed market data, verified corporate actions and security masters, prospective sample depth, time-valid event effects and independent review; operational approvals and legal signoffs. NOT in the four-turn mini-project. Previously assessed as at least ~9–17 additional substantive engineering iterations plus unbounded external dependencies. Do not label the mini-project 'institutionally complete'.

## Current numerical research snapshot (not claims of approval)

- 49,666 received venue market records; 12 runs, only four independent UTC capture dates as last verified.
- 893,988 event-factor warehouse co-observation rows; two distinct prospective factor source dates, insufficient for event-risk inference.
- 233,442 rows in panel v2; 466,884 rows in source-native v4. Both historical/observational research objects.
- 48 securities, two prespecified funding-model variants, 96 fits, 20,064 paired heldout losses; zero global Holm-surviving robust beta candidates.
- 16 institutional contracts with 274 field rules (255 mandatory, 135 mandatory fields missing, 255 mandatory fields uncertified).
- Last executed institutional release gate snapshot: 25/54 automatic passing, 29 blocked, plus four independent manual approval gates; production=FALSE. Source BEA receipt arrived *after* gate snapshot; do not imply newer BEA evidence was reviewed by those gates.
- BEA official publisher pages: two genuine receipt-time BLOB packets, ten published monthly PCE/personal-income/trade values, independently rehashed and re-parsed. These are NOT as-first-known release vintages or actual-minus-consensus innovations.
- GitHub CI: PR #72 five checks green, merged. A one-shot read-only MotherDuck acceptance Flight `bfcb3b2d-a687-4486-bdc2-9dbeede44e20`, version 2 run #2 succeeded. No mutation or automatically refreshed release-gate score.

Every metric rendered in the preview must show an `as_of` timestamp, dataset grain, a source table/report and either a pinned snapshot ID or explicit 'live internally recomputed' label. This baseline is illustrative until the display data contract is regenerated.

## Architecture boundaries

**Safest fast route:** separate web frontend under `lab/engineering_preview/`, using an allowlisted non-sensitive aggregate status snapshot with code/source provenance; never ship original venue quote rows, issuer-adjusted prices, archival HTML payloads, third-party licensed source files, security IDs/portfolio holdings, credentials, or raw restricted API responses. The aggregate preview should have an explicit internal-only use/legal review warning until distribution rights are established. Prefer an authenticated PRIVATE deployment even for status aggregates. When the credentialed backend is unavailable, use clearly labeled time-stamped synthetic fixtures for UX tests or a previously reviewed restricted aggregate snapshot, never invented live metrics.

**Optional future live mode:** authenticated, read-only API that follows the existing `lab/api.py` fail-closed protections (`X-API-Key`, scoped `MOTHERDUCK_TOKEN`, `LAB_DB`, `LAB_DATA_RIGHTS_ACK`). It may reuse existing research endpoints behind these controls, without circumventing missing vendor permission. No reconfiguring `LAB_DATA_RIGHTS_ACK` unless real documented data rights exist. All new public routes must return no restricted provider content without actual explicit authorization.

**No impact:** no destructive migrations, backdated event or release timestamps, change of independent approval flags, removal of gate controls, retroactive write into production event domain, replacement of legacy MVP, or automatic deployment of `main` simply because CI passes.

## Preview views (explicitly not approved trading products)

- **Overview & freshness:** immutable latest audit IDs, capture-run/capture-day counts, panel composition and grain, missing data families, warning if a source or gate snapshot is stale, API code vs deployed version.
- **Event/factor research:** limited or synthetic-only example event/proposition and factor taxonomy cards, clean explanation of event -> economic mechanism -> market factor, source time limitations. No apparent 'causal risk beta' for a proposed link.
- **Beta/risk laboratory:** distributions of retrospective beta/heldout diagnostics and stability failures; prominently zero surviving funding candidates and no favorable-selection reclassification.
- **Data quality/evidence:** mandatory-field coverage, BEA official actual-source packets, missing original first-known and consensus, adjustment/revision and reviewer approval blockers.
- **Remaining work:** grouped backlog from `PHASE1_PRODUCTION_UNBLOCK_PLAN.md` and recent gate + institutional contract audits. Provide status, evidence to unblock, owner type and an institutional-vs-preview boundary.

## Four substantial continuation prompts

**Prompt 1 — Scope/contract (this turn).**
- Inspect `main`, Railway deployed SHA/health, MotherDuck audited source status; preserve verified vs assumed claims.
- Check in this plan and the separate unfinished-work ledger on a feature/docs branch.
- Pass when scope, data boundaries, acceptance conditions and target prompt budget are reviewable in GitHub. This does not itself implement the preview.

**Prompt 2 — Read-only snapshot & service contract.**
- Implement deterministic, allowlisted aggregate/metadata extraction: source counts, time span, gate build, missing-field snapshot, source QA and risk screens, code vs deployed SHA.
- Enforce fail-closed no source payloads/tokens, defensible timestamp handling, no false point-in-time or approval flags, small JSON schema with version and warnings.
- Add fixture mode, negative tests, CI and pinned data generation path. Pass when deterministic local/offline contract tests pass and a real, explicitly authorized aggregate snapshot can be compared with MotherDuck SELECT-only metrics.

**Prompt 3 — Usable engineering dashboard.**
- Implement the five compact views with clear methodology badges/warnings and date-stamped source metadata. Distinguish loaded records from independent samples, and research calculations from institutionally approved models.
- Add chart/table drilldowns only to permitted aggregate research metrics; fixtures must be labeled. Test responsive UI and failure/stale states. No unsupported public data delivery.
- Pass when a local self-contained build runs from a clean checkout with reproducible fixture data and usable navigation.

**Prompt 4 — Integration, QA, showcase and handoff.**
- Run offline/integration and security tests, reconciliation against real authorized aggregate observations, verify monitoring/restart and negative auth checks.
- If safe, authorized and credential-ready, provision a SEPARATE restricted preview deployment; otherwise deliver precise local run instructions and identify deployment as blocked (do not fake an accessible link). Do not modify existing source API or legacy MVP.
- Write `ENGINEERING_PREVIEW_HANDOFF.md` with URL (only if verified live), last SHA, expected screens, tested flows, actual CI/run IDs, known failures, environment variable names (never values), data freshness/rebuild instructions, exact next tasks and deferred institutional backlog. Explicitly distinguish engineering preview complete from institutional production blocked.

**Overflow Prompt 5 (only if necessary):** fix genuine CI, runtime or rollout failures, verify deployed SHA and final smoke checks. A fifth prompt is not permission to waive failed criteria.

These are substantial batches of tool work, not automatic asynchronous execution. The prompt count assumes the connected GitHub/Railway/MotherDuck tools remain available and does not include elapsed prospective calendar history, human legal/model review, or paid source acquisition.

## Acceptance checklist — ALL required to call the preview engineering-complete

- [ ] Buildable locally from a clean repository state; reproducible tests pass.
- [ ] Five views work; field labels, units, immutable source version, vintage, research status, and risk caveats are visible.
- [ ] Counts are reconciled to ONE explicit MotherDuck research snapshot or clearly labeled synthetic fixtures, not mixed incompatible builds.
- [ ] Freshness and missing-source/data-rights/approval statuses fail closed.
- [ ] Read-only backend/source contract; no unrestricted sensitive market data and no secret leakage.
- [ ] Security negative-path tests pass; no unapproved access to research rows.
- [ ] Preview deployment is verified reachable with valid access controls (or is explicitly marked not deployed and cannot be called a live preview).
- [ ] Does not change institutional releases, gate score, legacy MVP, or original research history.
- [ ] Complete reproducibility + handoff and deferred institutional blocker ledger, linked to authoritative source work.

## Simple progress semantics

Maintain *two separate status lines*: (1) engineering preview deliverables completed X/Y, with verified CI/run evidence, and (2) original institutional source/release gates (currently 25/54 automatic passed, 4 manual blockers, and production=FALSE). The first may reach 100% without changing the second. Do not reuse 70% or 40% judgmental estimates as an objective measure.

## Links

- Canonical: https://github.com/sanga4/event_risk
- Latest accepted original BEA source and gateway safety: https://github.com/sanga4/event_risk/pull/72
- Status: ../PHASE1_CURRENT_VERIFIED_STATUS_2026_10_26.md
- Institutional blocker playbook: ../PHASE1_PRODUCTION_UNBLOCK_PLAN.md
- Full source contracts: ../INSTITUTIONAL_DATA_DICTIONARY_AND_BACKFILL.md
- Deferred-work ledger: INSTITUTIONAL_CONTINUATION_LEDGER.md
