# Original source-clock acceptance audit — internal research only

Phase I source: lab/phase1_source_clock_gap_audit.py. The audit writes append-only evidence-gap snapshots to two new MotherDuck tables within eventrisk_factor_lab, without modifying market, factor, or security-price source records.

- lab_source_clock_gap_builds_v1: one reproducible run manifest with source Git commit and SHA-256, pinned source-family inventory build, 16-family coverage, HTTP venue-receipt integrity, historical vendor security-price integrity, prospective factor-grid temporal integrity and explicit false institutional approval.
- lab_source_clock_gap_subjects_v1: 20 audited subjects consisting of the 16 source families, Kalshi and Polymarket receipt sets, retrospective Yahoo-adjusted security prices, and warehouse-as-of factor coobservations. Each identifies original-source evidence still required.

The implementation deliberately distinguishes an upstream assertion of rights or a provider publication clock from an independent signed review. All independently_signed_clock and institutional_release_approved fields remain false. Venue capture_received_at is **not** a venue quote's original publication timestamp. Historical adjusted closes are **not** original as-published corporate-action vintages. A temporal-safe warehouse coobservation is **not** historical release-safe or an identified event-factor causal effect.

Failure conditions include missing venue coverage, invalid source hashes/probabilities, falsely approved venue source timestamps, malformed historical prices, missing/duplicated source-family inventory, any forward warehouse factor leakage and any falsely approved grid mapping or historical backtest row. Successful execution means only that these mechanical assertions passed. Source-family rows are from their last versioned inventory; other read aggregates may change during execution, so there is **no claim of a consistent immutable upstream snapshot**.

There is no scheduler, license toggle, API exposure, historical backtest release, credential creation or automatic regulatory approval. Any independent evidence must be separately sourced, attributed, timestamped, dual-reviewed, licensed and accepted through formal governance before changing institutional readiness flags.

## Verified first remote execution (October 25, 2026 UTC)

MotherDuck Flight: eventrisk-lab-institutional-source-clock-gap-audit, id b693ec0a-623f-4347-9eb6-829318da9bab, version 2, run 2, status SUCCEEDED, exit code 0. Flight requirements are pinned to duckdb==1.5.6 and pytz==2025.2 (the first attempt without pytz failed before materialization). The producer SHA for this execution is bfaee4b767b58d746b1a9125c2fc7330fc9846f5.

Build: phase1-source-clock-gap-v1.0.0-20261025T031956854427Z. It audited 16 institutional source families (7 populated, 9 missing), 30,112 event-market receipt records (zero provider quote timestamps), 107,157 vendor security prices, and 542,016 warehouse-asof event-factor observations. Invalid receipt/price records, forward warehouse-factor observations, false source approvals and independent original-clock signoffs were all zero. The new tables contain one immutable append-only audit build and 20 subject requirements; verified original publication/revision vintages and licensed institutional uses remain outstanding. Source-family counts are taken from the previously versioned source-family inventory, not a simultaneous source-provider snapshot.

Do not interpret the 0 errors result as original exchange quote freshness, original issuer action provenance, vendor redistribution rights, historical point-in-time validity or an independently approved investment risk model.
