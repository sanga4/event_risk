# Phase I event surprise research estimands — chronology, units and identification

**Status:** source-controlled methodology gates only. No genuine first-release observations, verified pre-event consensus vintages, legally approved exchange quote times, or institutional risk betas have been produced by this change.

## Why two distinct estimands are mandatory

A forecast-market probability revision is **not** a macroeconomic release surprise. The historically available quote and the original terms of the event contract may themselves be hindsight-biased, and a change in belief after an announcement can be endogenous to prices and news.

The new pure-source implementation is in lab/phase1_event_surprise_temporal_methodology.py with offline adversarial tests:

**Market belief revision candidate:** 100 × (post-event quote probability − pre-event quote probability), in **probability points**. It requires independently recorded pre- and post-event contract SHA256s that match exactly, a declared contract-version identity, two original provider quote publication timestamps, corresponding collector receipt times known within the declared decision as-of time, immutable original source record hashes and a pre-registered pre/post window (default 60 and 30 minutes). An original pre-quote must have been received before the event; a post-quote cannot count until actually received. Missing original quote clocks or out-of-order timestamps block estimation. This measures a descriptive change in belief; event_surprise_probability_points is intentionally NULL.

**Macro first-print surprise candidate:** officially first-published actual source-native value − independently timestamped and locally received **pre-release** consensus. Optional standardization must divide by a strictly positive dispersion fixed before the scheduled release, not by statistics fitted using the realized surprise. The source-native units must be declared **separately** for the original actual and the frozen consensus, and must match the prespecified output unit exactly; no implicit scaling or unit conversion is permitted. Original first-print publication and collector receipt times must follow the scheduled announcement and precede the declared decision as-of. Preserve the source's numerical unit, the original revision identifier and exact source digests. A macro raw deviation is not automatically a causal or investable price shock; market_probability_belief_revision_pp remains NULL.

The code accepts only narrow explicit source fields and rejects caller-supplied approval/certification assertions. Every passing candidate has all original-source authenticity, independent first-publication/PIT, license, causal identification and institutional beta approval flags FALSE.

## Statistical and economic methodology

To progress beyond descriptive estimation, a prespecified independent analyst must document what actual information changed, the source's *historically original first release*, the timestamped pre-event forecast ensemble, precise unit/sign conventions, contract version and event outcome definition, and the feasible asset-market reaction window. Source clocks must be authenticated separately from an HTTP receipt and original bytes must pass the separate source-packet SHA256 integrity validator.

Independent causal event→economic-channel→market-factor inference requires identification beyond simply comparing two contemporaneous observations. Check scheduled-vs-unscheduled news, simultaneity, pre-trends, correlated releases, news bundles, revisions, liquidity, funding conditions, and common market shocks. Prefer a prespecified event-study / high-frequency identified innovation with sensitivity windows, falsification tests, placebo dates, calendar-cluster uncertainty and chronological holdouts. Retain no-trading/no-PIT release until these tests, data rights, and human validation pass.

Never call a same-day factor change a direct beta without independent event identification. A large base dataset or 96 fitted security regressions cannot substitute for genuine issuer, factor release-vintage, and corporate-action source records.

## Use and boundaries

The two pure functions can be tested offline without licenses or network:
- belief_revision(record, pre_window_minutes=60, post_window_minutes=30)
- macro_release_surprise(record)

They return bounded descriptive research candidate dictionaries or raise MethodologyRejected on missing/chronologically impossible source inputs. They do not query or alter MotherDuck, trigger Flights, backfill event_innovations_v1, enable a GitHub workflow, call any provider API, or assert independently authenticated dates. Synthetic unit-test examples are **not actual source evidence**.

**Next ingestion gate:** obtain real signed/archived source payloads and original publisher clocks, independently timestamped pre-release consensus and documented source-entitlements. Only then populate an auditable research event-innovation candidate table, preserving true missing values instead of manufacturing historical shocks.
