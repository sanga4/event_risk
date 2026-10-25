#!/usr/bin/env python3
"""Fail-closed, read-only prospective event×factor source-lineage reconciliation.

Verifies the stored research grid is a reproducible copy of the actual recorded
venue captures and warehouse rate vintages; tests source clocks, hashes and
contract semantics. Does NOT prove the publisher's first-publication time,
legal data reuse, causal transmission or investable risk-factor exposure.
"""
from __future__ import annotations

import json
import sys

import duckdb

DB = "eventrisk_factor_lab"
PREFIX = DB + ".main."
ALLOWED_LICENSES = (
    "government_source_via_treasury",
    "government_source_via_fred",
    "derived_not_true_breakeven",
)


def inspect(con, prefix=PREFIX) -> dict:
    """Independent, SELECT-only snapshot of producer/source reconciliation."""
    counts = con.execute(
        f"""SELECT
          (SELECT count(*) FROM {prefix}lab_prospective_event_factor_grid_v1),
          (SELECT count(*) FROM (
            SELECT run_id, venue, market_id
            FROM {prefix}lab_live_event_features_v1
            GROUP BY 1,2,3 HAVING count(*)>1
          ) collisions),
          (SELECT count(*) FROM (
            SELECT factor_id,factor_observed_date,source_record_sha256,
                   source_ingested_at
            FROM {prefix}lab_factor_warehouse_vintages_v1
            GROUP BY 1,2,3,4 HAVING count(*)>1
          ) collisions)
        """
    ).fetchone()
    rows, duplicate_event_source_keys, duplicate_factor_vintage_keys = counts

    event_matches = con.execute(
        f"""SELECT count(*) AS joined,
          count(*) FILTER (WHERE e.run_id IS NULL) AS missing,
          count(*) FILTER (WHERE e.run_id IS NOT NULL AND (
              g.event_source_sha256 IS DISTINCT FROM e.source_record_sha256
              OR g.event_capture_at IS DISTINCT FROM e.known_at
              OR g.proposition_id IS DISTINCT FROM e.proposition_id
              OR g.event_probability IS DISTINCT FROM e.probability
          )) AS drift
        FROM {prefix}lab_prospective_event_factor_grid_v1 g
        LEFT JOIN {prefix}lab_live_event_features_v1 e
          ON g.event_run_id=e.run_id
         AND g.venue=e.venue
         AND g.market_id=e.market_id
        """
    ).fetchone()
    factor_matches = con.execute(
        f"""SELECT count(*) AS joined,
          count(*) FILTER (WHERE v.factor_id IS NULL) AS missing,
          count(*) FILTER (WHERE v.factor_id IS NOT NULL AND (
              g.factor_value IS DISTINCT FROM v.factor_value
              OR g.factor_unit IS DISTINCT FROM v.factor_unit
              OR g.factor_available_at IS DISTINCT FROM v.source_availability_at
              OR g.factor_license_class IS DISTINCT FROM v.license_class
              OR g.factor_provider IS DISTINCT FROM v.provider
              OR g.factor_source_run_id IS DISTINCT FROM v.source_run_id
          )) AS drift
        FROM {prefix}lab_prospective_event_factor_grid_v1 g
        LEFT JOIN {prefix}lab_factor_warehouse_vintages_v1 v
          ON g.factor_id=v.factor_id
         AND g.factor_observed_date=v.factor_observed_date
         AND g.factor_source_sha256=v.source_record_sha256
         AND g.factor_ingested_at=v.source_ingested_at
        """
    ).fetchone()
    allowed = ",".join("'" + v + "'" for v in ALLOWED_LICENSES)
    semantics = con.execute(
        f"""SELECT
          count(*) FILTER (WHERE
            g.factor_observed_date IS NULL OR g.event_capture_at IS NULL
            OR g.factor_ingested_at IS NULL OR g.factor_available_at IS NULL
            OR g.factor_observed_date > CAST(g.event_capture_at AS DATE)
            OR date_diff('day',g.factor_observed_date,
                 CAST(g.event_capture_at AS DATE)) NOT BETWEEN 0 AND 10
            OR g.factor_ingested_at > g.event_capture_at
            OR g.factor_available_at > g.event_capture_at
          ),
          count(*) FILTER (WHERE
            g.event_probability IS NULL
            OR NOT isfinite(g.event_probability)
            OR g.event_probability NOT BETWEEN 0 AND 1
            OR g.factor_value IS NULL OR NOT isfinite(g.factor_value)
            OR g.event_source_sha256 IS NULL
            OR NOT regexp_full_match(g.event_source_sha256,'[0-9a-f]{{64}}')
            OR g.factor_source_sha256 IS NULL
            OR NOT regexp_full_match(g.factor_source_sha256,'[0-9a-f]{{64}}')
            OR g.factor_unit IS DISTINCT FROM 'percent'
            OR g.factor_license_class IS NULL
            OR g.factor_license_class NOT IN ({allowed})
          ),
          count(*) FILTER (WHERE
            g.event_receipt_time_verified IS DISTINCT FROM TRUE
            OR g.factor_warehouse_asof_verified IS DISTINCT FROM TRUE
            OR g.exchange_quote_time_independently_verified IS DISTINCT FROM FALSE
            OR g.factor_publication_time_independently_verified IS DISTINCT FROM FALSE
            OR g.event_to_factor_mapping_approved IS DISTINCT FROM FALSE
            OR g.historical_backtest_released IS DISTINCT FROM FALSE
            OR g.data_use_class IS DISTINCT FROM 'internal_research_only'
            OR g.relation_status IS DISTINCT FROM 'unreviewed_factor_coobservation_grid'
          ),
          min(date_diff('day',g.factor_observed_date,
                   CAST(g.event_capture_at AS DATE))),
          max(date_diff('day',g.factor_observed_date,
                   CAST(g.event_capture_at AS DATE)))
        FROM {prefix}lab_prospective_event_factor_grid_v1 g
        """
    ).fetchone()
    bad_time, bad_source, false_claims, age_min, age_max = semantics

    violations = {
        "duplicate_event_capture_source_keys": duplicate_event_source_keys,
        "duplicate_factor_source_vintage_keys": duplicate_factor_vintage_keys,
        "event_capture_source_rows_missing": event_matches[1],
        "event_capture_identity_or_payload_drift": event_matches[2],
        "factor_vintage_source_rows_missing": factor_matches[1],
        "factor_vintage_value_or_metadata_drift": factor_matches[2],
        "invalid_warehouse_timing_or_age_rows": bad_time,
        "invalid_factor_source_payload_or_license_rows": bad_source,
        "unsupported_provenance_or_release_claim_rows": false_claims,
        "source_join_row_amplification": max(0, event_matches[0] - rows)
            + max(0, factor_matches[0] - rows),
    }
    report = {
        "status": ("BLOCKED_NO_PERSISTED_GRID" if rows <= 0 else
                   "BLOCKED_RESEARCH_SOURCE_LINEAGE" if any(violations.values())
                   else "PASS_RESEARCH_WAREHOUSE_LINEAGE_ONLY"),
        "persisted_grid_rows": rows,
        "factor_observed_lag_min_calendar_days": age_min,
        "factor_observed_lag_max_calendar_days": age_max,
        **violations,
        "original_publisher_first_available_at_verified": False,
        "data_redistribution_approved": False,
        "identified_event_factor_causality_approved": False,
        "historical_pit_backtest_released": False,
        "institutional_risk_beta_released": False,
        "message": "Only immutable internal warehouse/source reconciliation; no external provider chronology or rights attested",
    }
    return report


def main():
    # Unconditionally SELECT-only SQL; use a genuinely read-only scoped MotherDuck token.
    con = duckdb.connect(f"md:{DB}?attach_mode=single")
    try:
        result = inspect(con)
    finally:
        con.close()
    print(json.dumps(result, sort_keys=True, indent=2))
    return 2 if result["status"].startswith("BLOCKED") else 0


if __name__ == "__main__":
    sys.exit(main())
