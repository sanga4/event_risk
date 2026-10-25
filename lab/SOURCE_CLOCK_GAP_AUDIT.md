# Original source-clock acceptance audit — internal research only

Phase I source: lab/phase1_source_clock_gap_audit.py. The audit writes append-only evidence-gap snapshots to two new MotherDuck tables within eventrisk_factor_lab, without modifying market, factor, or security-price source records.

- lab_source_clock_gap_builds_v1: one reproducible run manifest with source Git commit and SHA-256, pinned source-family inventory build, 16-family coverage, HTTP venue-receipt integrity, historical vendor security-price integrity, prospective factor-grid temporal integrity and explicit false institutional approval.
- lab_source_clock_gap_subjects_v1: 20 audited subjects consisting of the 16 source families, Kalshi and Polymarket receipt sets, retrospective Yahoo-adjusted security prices, and warehouse-as-of factor coobservations. Each identifies original-source evidence still required.

The implementation deliberately distinguishes an upstream assertion of rights or a provider publication clock from an independent signed review. All independently_signed_clock and institutional_release_approved fields remain false. Venue capture_received_at is **not** a venue quote's original publication timestamp. Historical adjusted closes are **not** original as-published corporate-action vintages. A temporal-safe warehouse coobservation is **not** historical release-safe or an identified event-factor causal effect.

Failure conditions include missing venue coverage, invalid source hashes/probabilities, falsely approved venue source timestamps, malformed historical prices, missing/duplicated source-family inventory, any forward warehouse factor leakage and any falsely approved grid mapping or historical backtest row. Successful execution means only that these mechanical assertions passed. Source-family rows are from their last versioned inventory; other read aggregates may change during execution, so there is **no claim of a consistent immutable upstream snapshot**.

There is no scheduler, license toggle, API exposure, historical backtest release, credential creation or automatic regulatory approval. Any independent evidence must be separately sourced, attributed, timestamped, dual-reviewed, licensed and accepted through formal governance before changing institutional readiness flags.
