# Phase I — Effective-information gate for prospective event-factor research

**Read-only audit timestamp:** 2026-10-25 (warehouse capture period ending 17:54 UTC).

**Key conclusion:** The prospective event-factor grid is a valid internal collection and source-lineage dataset, but is **not yet a statistically estimable event-to-factor response panel**. Repeated capture-market rows and repeated factor data do not create independent events, independent factor innovations or usable historical point-in-time observations.

## Grounded evidence from existing warehouse

| Statistic | Verified |
| --- | ---: |
| Stored prospective event-factor rows | 806,004 |
| Distinct captured market/run identities | 44,778 |
| Unique venue-market contracts and proposition IDs | 4,889 each |
| Captures / separate collector run IDs | 11 |
| Calendar dates containing those captures | 3 (October 23–25) |
| Factor IDs in prospective grid | 18 |
| DISTINCT factor observed dates inside the prospective grid | **1 (2026-10-22)** |
| Original stored factor vintages used inside the prospective grid | **18 (one per factor)** |
| Unique observed factor levels **per factor** | **1** |
| Factor rows in the broader archival warehouse | 12,656 |
| Factor archive observed dates | 702 (2024-01-02 to 2026-10-22) |
| Market capture identities with earlier observations | 39,889 |
| Market capture identities with nonzero recorded probability revisions | 3,436 |
| Independently certified source publication/quote clocks or approved event-factor mappings | **0** |

One stored rate quote source vintage was paired with every one of the 44,778 market-capture identities. It was replicated into 18 factor columns, yielding 806,004 rows. Those are **not independent factor realizations**. A regression estimating the relation between each event probability revision and a contemporaneous rate-factor innovation has no independent variation in its factor response. Training an event-to-financial-factor beta from this grid would be unidentified or statistically meaningless.

The broader archived warehouse contains 702 factor observation dates, but cannot be replayed backward as if original prospectively captured event quotes, pre-event expectations, and independently verified first-published factor values had existed at those times. This is the key distinction between available retrospective reference history and an as-received event-factor training sample.

## New audit gate

Run:

    python lab/phase1_prospective_effective_information.py

It uses SELECT-only SQL over the current grid and original factor archive and prints complete source counters and per-factor source-data maturity. A nonzero exit code 2 means **BLOCKED_PROSPECTIVE_FACTOR_STATISTICAL_ESTIMATION**, not a warehouse-integrity failure or a reason to stop lawful collector ingestion. Its checks include:

- Every captured market identity must form a complete currently defined factor rectangle; no duplicate or missing event-factor rows may inflate the apparent denominator.
- Aggregate capture days, run IDs, original quote revision/paired-capture identities, factor source day counts, distinct observed values, archived vintage counts, and actual research source approval flags must be internally consistent.
- Each prospective factor must have at least **30 independently observed factor dates and two distinct values**, in a minimum prospective capture window of **60 calendar days across 60 capture runs** to pass a *research sample-variation screen*. These are intentionally conservative predeclared minimum-screen heuristics, **not** proof of sample adequacy, statistical identification, independent original quote clocks or licensed production readiness. Higher sample and regime requirements will be evaluated separately.
- The script always declares original-source first-publication clock, independent event innovations, causal factor betas and institutional risk-model approvals **FALSE**, even when its minimum data-variation screen passes.
- The independent tests construct a large synthetic event-market cross-section paired with constant factor vintages, proving it blocks apparent massive row counts without actual factor time variation. A separate synthetic 65-day, 65-run sample may pass research *variation* only, never source/PIT/causal/institutional acceptance.

**Operational note:** Do not add this gate as a hard prerequisite to the Phase I incremental collector or warehouse grid ingestion job. That would make acquiring the required new observations impossible. Treat this as the gate for training, evaluating or publishing prospective event-factor beta/impact models. Ingestion is allowed to append authentic source observations while this research estimability gate remains blocked.

## What genuine source backfill and continued collection require

1. Continue authorized collector captures over a long real trading/calendar horizon, retaining original venue quote/contract published times **separately** from our HTTP capture receipt times, immutable source payloads and revision identities.
2. Refresh the actual factor warehouse with original Treasury/FRED publication and revision vintages **when available**, with verified as-known ingestion timestamps. The current archive ends at 2026-10-22; never substitute historical observation DATE for original first-published timestamp.
3. Independently identify truly pre-event source consensus and a first-published event realization for each macroeconomic innovation, recording native-unit and contract-version evidence. A changing price is not by itself an exogenous surprise.
4. Join only source vintages whose warehouse receipt and independently verified historical availability precede the relevant event capture decision time. Do not invent October 23–25 factor innovations from the older October 22 factor level.
5. After sufficient varied as-known factor/event days, run independent pretrend, calendar-bundle, staggered publication, dependence-blocked/familywise uncertainty and true forward holdout model validations. Maintain all vendor rights, corporate action and independent economics/model review signoffs.

## Relation to the 48-security funding beta research

The existing 96 joint security funding models are a **separate, retrospective** security return/rate/basis association exercise. Its 702-day-type historical rate and security coverage does not solve the prospective 3-day market-event/impact identification problem. Neither the 48-security beta sample nor the 806,004-row co-observation grid supports a causal, production or historical PIT trading-risk claim without genuine original-source vintages and independent validation.
