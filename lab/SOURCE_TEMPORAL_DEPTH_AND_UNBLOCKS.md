# Phase I — Institutional source-family temporal adequacy audit

## Purpose

The existing source-family ledger contains 16 required macro, credit, market, FX, event, security and portfolio families. Row counts alone cannot establish research fitness or an institutionally acceptable as-of sample. An 11.1-million-row historical market snapshot may lack **both original quote publication provenance and recorded first/last observation-date metadata**; a 718,020-row prospective event/factor grid may contain only three independent capture days. The original official SOFR/EFFR subset contains only 250 effective dates per series, even though the full historical importer is now merged.

The independent research-only producer `lab/phase1_source_temporal_depth_audit.py` cross-checks the latest 16-domain inventory against **native venue captures**, **SOFR and EFFR records**, **prospective warehouse-as-of grid**, and **source-native retrospective v4 panel**. It fails if independent counts diverge, a false original publisher-time/rights approval appears in underlying rate/venue/grid/model inputs, rate families disappear, or an impossible temporal count appears. Each source-family retains its exact original evidence requirement.

The audit makes the following **descriptive research screens**, without presenting them as universal statistical requirements or institutional approval:

- At least 1,500 distinct original NY Fed reference **effective dates** for *each* SOFR and EFFR (first observation date no later than December 2018); additional source revision history and source rights remain independently necessary.
- At least 60 independent warehouse receipt **calendar dates**; on-demand repeated same-day captures add venue row volume but not independent day coverage.
- At least 60 dates with paired factor and event changes for *exploratory* event-to-factor inference. This does **not** imply that 60 iid observations suffice for causal effects; shared factor returns, event clustering and serial dependence require further independent review.

The prior source ledger also has a real coverage metadata weakness: `historical_market_snapshots` is populated with ~11.1 million retrospective rows, but `first_observed_date` and `latest_observed_date` are both absent in the latest inventory. The new audit explicitly flags `POPULATED_BUT_FIRST_LAST_OBSERVATION_DATES_MISSING` rather than pretending the date span was reviewed or erroneously refusing to register the gap.

The audit creates append-only `lab_source_temporal_depth_audit_builds_v1` and 16 per-family `lab_source_temporal_depth_audit_domains_v1` audit rows, along with the pinned source Git commit and script SHA256. All independently approved original publication-clock, commercial reuse and institutional event/beta model flags remain FALSE. It is **not** a producer of macro surprises, vendor quotes, priced financial factor shocks, inferred issuer actions or licensed institutional betas.

### Next independent evidence steps

Load the official NY Fed history in an authorized MotherDuck Flight once the connected Flight code update can be executed (no historical source load should be claimed before that). Load authenticated FRED release vintages only with a privately provisioned authorized key. Secure licensed original credit, executable FX and volatility inputs, verified issuer actions, and economically identified event-to-factor mapping with a documented human reviewer. Collect genuinely new prospective calendar days with stable capture windows, verified exchange quote publication times and terms of use.

The audit is purposefully separate from the formal 47 automatic institutional release gates. Do not inflate the published 23/47 pass fraction merely because a better descriptive research register exists.

## Verified live execution — October 25, 2026 UTC

MotherDuck Flight `eventrisk-lab-institutional-source-temporal-adequacy`, ID `905c9c55-b9c0-450e-b136-6302f6e8e8bd`, version 1 run 1 SUCCEEDED (exit 0). Manifest `phase1-source-temporal-adequacy-v1.0.0-20261025T052949522220Z` pinned to source commit `e4939fd35dc2bdd9d24edefe3622335dde3f654c` and family inventory build `phase1-source-gap-matrix-v1.0.0-20261025T051639467055Z`. Successfully reconciled 39,890 market receipts across 3 independent capture dates, 500 official NY Fed effective-date observations (250 dates per rate), 718,020 prospective as-of coobservations across 3 capture dates and 233,442 retrospective v4 pairs with just 5 complete event calendar dates. Persisted **16** domain-level subject reviews and one immutable execution manifest; **7 populated families, 9 empty**.

Domain-level results: 9 `MISSING_SOURCE_OR_CREDENTIAL_OR_ORIGINAL_EVIDENCE`; 1 historical NY Fed truncation review; 1 missing historical market first/last observation date metadata; 1 prospective capture-date insufficiency; 4 populated source families requiring independent original PIT and rights. All original publication clocks, commercial rights, and institutional event-factor model approvals remained **FALSE**. GitHub CI passed **237 offline Lab tests** including nine new adversarial audit tests, plus three other workflow suites.

**Next fix:** In the existing historical-market source family producer, retrieve the native snapshot event-date range (not the warehouse fetch timestamp). Record the first/last dates with the build. No as-known historical source clock is inferred from these observation dates.
