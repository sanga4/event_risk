# EventRisk Phase I — Current-month official Treasury source receipts

**Status:** source-controlled code + synthetic tests; no authenticated production execution, new MotherDuck rate row or rights approval claimed.

**Method:** `lab/phase1_treasury_current_xml_refresh.py`

**Manual operator workflow:** `.github/workflows/phase1_treasury_current_xml_refresh.yml`

## Evidence and motivation

The existing internal event/interest-rate co-observation grid contains 806,004 research rows sourced from 11 venue capture runs across only three calendar days (October 23–25, 2026). Every one of its 18 factor series uses the same October 22 observed daily rate level. The independent historical factor archive already contains 12,656 factor observations across 702 dates, but it currently ends on **October 22**. The archive's older rate history cannot substitute for venue quotes genuinely captured on those older dates. This is a hard statistical identifiability and data chronology failure, documented by PR #57 and four release-gate checks added in PR #58.

The official U.S. Treasury documentation describes the **Treasury Daily Interest Rate XML Feed**, with monthly query parameters `data=daily_treasury_yield_curve` and `data=daily_treasury_real_yield_curve` and `field_tdr_date_value_month=YYYYMM`:
https://home.treasury.gov/treasury-daily-interest-rate-xml-feed

### Specific narrow source coverage

- Daily nominal par yield curve: `DGS1MO`, `DGS3MO`, `DGS6MO`, `DGS1`, `DGS2`, `DGS3`, `DGS5`, `DGS7`, `DGS10`, `DGS20`, `DGS30` (11).
- Daily real par yield curve: `DGS5R`, `DGS7R`, `DGS10R`, `DGS20R`, `DGS30R` (five). **These use source XML properties `TC_5YEAR`, `TC_7YEAR`, `TC_10YEAR`, `TC_20YEAR`, and `TC_30YEAR`, NOT nominal yield properties `BC_*`.** This field distinction was verified against Treasury-sourced public series and externally documented Treasury XML examples in PR #61; source-controlled tests now fail closed on a wrong BC-tag real feed.
- Two **derived rate gaps**, not tradeable breakeven proxies: `PAR_NOMINAL_REAL_GAP_5Y`, `PAR_NOMINAL_REAL_GAP_10Y`. These are source-native percent yield level differences, NOT identified market inflation shocks.
- Explicitly EXCLUDED: FRED `T10YIE` and `NFCI` (different source/rights), Kalshi/Polymarket quote times, licensed credit spreads, futures, option vol and portfolio positions.

## Core original-source and chronological guarantees

- Calls official `home.treasury.gov` monthly nominal and real XML feeds using fixed URLs (never a caller-supplied arbitrary endpoint). HTTPS request maximum 30 seconds, no redirects, bounded XML body (2MB each), limited 35 daily entries.
- XML parsing requires the Treasury Atom/OData envelope, valid NEW_DATE, finite source par rate tenor values and exact same-day nominal/real calendars; missing tenors are **not forward-filled**, replaced by zero or hidden under a research "complete" label. Invalid or future dates and malformed responses cause fail-closed behavior.
- For *new* source coverage, consider only factor observed dates within the last ten calendar days of **actual receipt**, and skip source records whose latest stored warehouse value for that factor/date is unchanged. This prevents replaying the 702 archived earlier dates as fake newly available historical first prints. A genuinely revised recent rate value remains a separately versioned original-source research record. The current provider fetch is never backdated to the observation date.
- Raw official nominal/real XML **original bytes** are archived with their SHA256, original feed URL, the actual response-received UTC time and research-only flags. The candidate per-factor record hash includes the exact payload SHA256, native percent rate value, source day, factor identity and source URL. Derived gap hashes include BOTH nominal and real original source packet hashes.
- Each appended `lab_factor_observations` row has **`ingested_at=availability_at=actual_http_response_received_at`**. The `availability_basis` expressly states `official_xml_http_receipt_not_original_publication`. Original first-published date/time, Treasury revision-vintage PIT, source reuse/redistribution and all beta releases remain **FALSE/UNVERIFIED**. Warehouse-as-known is strictly not Treasury first-known.
- Successful opt-in writes append records transactionally alongside original binary packets and a source-Git-pinned manifest. A no-op feed can have an audit manifest with zero new values, but may not fabricate 18 fresh rate realizations when source values have not changed.

## Independent persisted-receipt acceptance (PR #60)

The manual source-refresh workflow now runs **a separate SELECT-only acceptance script after any opted-in research append**:

    python lab/phase1_treasury_receipt_acceptance.py --source-commit <reviewed 40-char commit>

It examines the latest source run manifest, archives both exact Treasury nominal and real XML byte packets, recomputes each source payload SHA256, authenticates the immutable producer source-file hash against the Git SHA of this execution, and checks that the source URL, UTC received-at clock and stored digest have not drifted. It reparses the original archived XML, recalculates the approved research 11 nominal + five real + two derived rates, and independently reconciles every newly persisted factor source value, original SHA link, source URL, percent unit, `ingested_at` and `availability_at` against the original HTTP receipt evidence. Duplicate source identities, missing rows, changed source payloads, forged publication or license approvals, or a mismatch to original source counts terminate acceptance. A documented zero-new-factor-value ingestion can legitimately pass with both original response packet hashes archived.

**Successful script execution does NOT create the right to distribute Treasury data, establish original first-publication, prove retrospective point-in-time market knowledge or license an institutional rate/beta product.** Failures are research-data consistency failures, not reasons to erase original packets or silently correct source history.

## Operation and requirements

1. Set a valid least-privilege GitHub Actions `MOTHERDUCK_TOKEN` with internal warehouse source archive write permission, respecting provider terms. Never paste the secret in chat or a commit.
2. Choose GitHub Actions → **Phase I Treasury nominal and real recent source XML (manual)**. Its **default** `append_research_records=false` only fetches official XML, checks the source-currentness/digests and reads existing warehouse values; it **does not persist** new source data.
3. If the original XML responses are well formed and the owner authorizes internal research appends, explicitly select `append_research_records=true`. The job then adds `LAB_SOURCE_REFRESH_WRITE_ACK=confirmed` and calls the producer with `--append-research`. It shares the existing `factor-lab-prospective-capture` GitHub concurrency lock and has no cron.
4. Inspect the completed job logs and new MotherDuck run manifest, source byte hash, candidate dates, actual new row counts and all FALSE PIT/rights flags. **Never infer success from a dispatched job alone.**
5. A subsequent **separately authorized real venue capture** through the existing `phase1_prospective_capture.yml` is needed to add future market receipt observations that could *legitimately* match a now-available newer Treasury vintage. Do not recompute old event captures with new source information, reassign their `known_at` or turn the factor-observed date into an exchange quote timestamp.

## Why this is not yet institutional readiness

Refreshing daily published rates will help remove the single-vintage stagnation once real future venue capture runs join to the genuinely received new vintages. It will not magically create 60 distinct venue capture calendar days or 30 factor observation dates, independently certified original Treasury first-published timestamps, true event surprises, causal financial factor responses, corporate-action adjusted security PIT, permitted exchange data redistribution, or approved betas.

Do not automate hourly trading data collection, spend Flight minutes, or publish source data externally without an operator's explicit permissions and review of ongoing costs and vendor policies. The research response is already non-causal; it cannot be used to trade as though original first-published times were confirmed.

## Audit follow-up

Run existing read-only `phase1_prospective_lineage_reconciliation.py`, `phase1_prospective_effective_information.py` and release-gate version 2.3 only after real source and venue capture updates. A blocked estimability screen is expected until enough genuinely separated date observations accumulate.
