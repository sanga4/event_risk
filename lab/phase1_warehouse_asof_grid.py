#!/usr/bin/env python3
"""Phase I prospective co-observation grid with strict warehouse-as-of checks.

Two separate timelines:
  1. event capture response receipt, not verified exchange-quote publication;
  2. factor source ingestion + declared availability, not independently verified
     economic release time.

Only factors already in the warehouse by the event receipt can join an event.
This is a *co-observation grid* across available factors, not reviewed causal
event->factor mappings, regression betas, or tradeable backtest data.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

DB = "eventrisk_factor_lab"
P = f"{DB}.main."
VERSION = "phase1-prospective-grid-v1.0.0"
ALLOWED_LICENSE_CLASSES = (
    "government_source_via_treasury",
    "government_source_via_fred",
    "derived_not_true_breakeven",
)


def setup(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_factor_warehouse_vintages_v1 (
      factor_id VARCHAR NOT NULL,
      factor_observed_date DATE NOT NULL,
      factor_value DOUBLE NOT NULL,
      factor_unit VARCHAR NOT NULL,
      provider VARCHAR NOT NULL,
      license_class VARCHAR NOT NULL,
      source_ingested_at TIMESTAMPTZ NOT NULL,
      source_availability_at TIMESTAMPTZ NOT NULL,
      availability_basis VARCHAR NOT NULL,
      source_url VARCHAR NOT NULL,
      source_record_sha256 VARCHAR NOT NULL,
      source_run_id VARCHAR NOT NULL,
      reconciliation_at TIMESTAMPTZ NOT NULL,
      independent_release_time_verified BOOLEAN NOT NULL,
      first_registered_by_build VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_prospective_event_factor_grid_v1 (
      proposition_id VARCHAR NOT NULL,
      venue VARCHAR NOT NULL,
      market_id VARCHAR NOT NULL,
      event_run_id VARCHAR NOT NULL,
      event_capture_at TIMESTAMPTZ NOT NULL,
      previous_event_capture_at TIMESTAMPTZ,
      event_probability DOUBLE NOT NULL,
      event_delta_pp DOUBLE,
      event_quote_basis VARCHAR NOT NULL,
      event_source_sha256 VARCHAR NOT NULL,
      factor_id VARCHAR NOT NULL,
      factor_observed_date DATE NOT NULL,
      factor_value DOUBLE NOT NULL,
      factor_unit VARCHAR NOT NULL,
      factor_available_at TIMESTAMPTZ NOT NULL,
      factor_ingested_at TIMESTAMPTZ NOT NULL,
      factor_source_sha256 VARCHAR NOT NULL,
      factor_provider VARCHAR NOT NULL,
      factor_license_class VARCHAR NOT NULL,
      factor_source_run_id VARCHAR NOT NULL,
      event_receipt_time_verified BOOLEAN NOT NULL,
      factor_warehouse_asof_verified BOOLEAN NOT NULL,
      exchange_quote_time_independently_verified BOOLEAN NOT NULL,
      factor_publication_time_independently_verified BOOLEAN NOT NULL,
      event_to_factor_mapping_approved BOOLEAN NOT NULL,
      historical_backtest_released BOOLEAN NOT NULL,
      relation_status VARCHAR NOT NULL,
      data_use_class VARCHAR NOT NULL,
      source_build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_prospective_grid_runs_v1 (
      build_id VARCHAR NOT NULL,
      version VARCHAR NOT NULL,
      full_git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,
      started_at TIMESTAMPTZ NOT NULL,
      finished_at TIMESTAMPTZ NOT NULL,
      new_factor_vintage_rows BIGINT NOT NULL,
      new_coobservation_rows BIGINT NOT NULL,
      event_captures_observed BIGINT NOT NULL,
      factor_vintages_observed BIGINT NOT NULL,
      future_warehouse_factor_rows BIGINT NOT NULL,
      externally_certified_pit_rows BIGINT NOT NULL,
      status VARCHAR NOT NULL
    )""")


def stage(con):
    # Never import restricted_ice_bofa or unreviewed sources like T10YIE:
    # source licensing is an explicit allowlist.
    labels = ", ".join("'" + x + "'" for x in ALLOWED_LICENSE_CLASSES)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_factor_source AS
    WITH eligible AS (
      SELECT f.factor_id, f.observed_date AS factor_observed_date,
        f.value AS factor_value, f.unit AS factor_unit,
        f.provider, c.license_class, f.ingested_at AS source_ingested_at,
        f.availability_at AS source_availability_at,
        f.availability_basis, f.source_url,
        f.record_sha256 AS source_record_sha256,
        f.run_id AS source_run_id,
        row_number() OVER (
          PARTITION BY f.factor_id,f.observed_date,
                       f.record_sha256,f.ingested_at
          ORDER BY f.availability_at DESC, f.run_id DESC
        ) AS rn
      FROM {P}lab_factor_observations AS f
      JOIN {P}lab_factor_catalog AS c USING (factor_id)
      WHERE c.active
        AND c.license_class IN ({labels})
        AND f.unit=c.unit AND isfinite(f.value)
        AND f.ingested_at <= current_timestamp
        AND f.availability_at <= current_timestamp
        AND length(f.record_sha256)=64
    )
    SELECT * EXCLUDE (rn) FROM eligible WHERE rn=1
    """)
    # Pair each capture ONLY with factor vintages ingested+available before
    # the event was recorded by OUR collector. A provider's original publication
    # timestamp has not been independently checked.
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_candidate_grid AS
    WITH joined AS (
      SELECT
        e.proposition_id,e.venue,e.market_id,e.run_id AS event_run_id,
        e.known_at AS event_capture_at,
        e.previous_capture_at AS previous_event_capture_at,
        e.probability AS event_probability,
        e.probability_delta_pp AS event_delta_pp,
        e.quote_basis AS event_quote_basis,
        e.source_record_sha256 AS event_source_sha256,
        f.factor_id,f.factor_observed_date,f.factor_value,f.factor_unit,
        f.source_availability_at AS factor_available_at,
        f.source_ingested_at AS factor_ingested_at,
        f.source_record_sha256 AS factor_source_sha256,
        f.provider AS factor_provider,f.license_class AS factor_license_class,
        f.source_run_id AS factor_source_run_id,
        e.capture_time_verified AS event_receipt_time_verified,
        TRUE AS factor_warehouse_asof_verified,
        FALSE AS exchange_quote_time_independently_verified,
        FALSE AS factor_publication_time_independently_verified,
        FALSE AS event_to_factor_mapping_approved,
        FALSE AS historical_backtest_released,
        'unreviewed_factor_coobservation_grid'::VARCHAR AS relation_status,
        'internal_research_only'::VARCHAR AS data_use_class,
        row_number() OVER (
          PARTITION BY e.run_id,e.venue,e.market_id,f.factor_id
          ORDER BY f.factor_observed_date DESC,
                   f.source_ingested_at DESC,
                   f.source_record_sha256 DESC
        ) AS rn
      FROM {P}lab_live_event_features_v1 AS e
      JOIN p1_factor_source AS f
        ON f.factor_observed_date <= CAST(e.known_at AS DATE)
       AND date_diff('day',f.factor_observed_date,CAST(e.known_at AS DATE))
           BETWEEN 0 AND 10
       AND f.source_ingested_at <= e.known_at
       AND f.source_availability_at <= e.known_at
      WHERE e.capture_time_verified
        AND e.probability BETWEEN 0 AND 1
        AND length(e.source_record_sha256)=64
    )
    SELECT * EXCLUDE (rn) FROM joined WHERE rn=1
    """)


def main():
    if os.getenv("LAB_RESEARCH_SCOPE") != "internal-only":
        raise RuntimeError("Internal research scope is required")
    commit = os.getenv("LAB_PIPELINE_COMMIT", "")
    if len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Require a pinned full 40-character Git commit SHA")
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_id = VERSION + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    start = datetime.now(timezone.utc)
    con = duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        setup(con)
        stage(con)
        source_vintages = con.execute("SELECT count(*) FROM p1_factor_source").fetchone()[0]
        observed_events = con.execute(f"SELECT count(*) FROM {P}lab_live_event_features_v1").fetchone()[0]
        candidates, future = con.execute("""
          SELECT count(*),
            count(*) FILTER (WHERE factor_ingested_at>event_capture_at
                               OR factor_available_at>event_capture_at)
          FROM p1_candidate_grid
        """).fetchone()
        if future:
            raise RuntimeError("Future warehouse factor leakage detected: no data written")
        if not observed_events or not source_vintages:
            raise RuntimeError("Missing prospective events or available factor vintages")
        # A full run may be rerun: existing source vintages and prospective
        # market×capture×factor pairs are never duplicated or silently revised.
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE p1_missing_vintages AS
        SELECT s.* FROM p1_factor_source s
        WHERE NOT EXISTS (
          SELECT 1 FROM {P}lab_factor_warehouse_vintages_v1 p
          WHERE p.factor_id=s.factor_id
            AND p.factor_observed_date=s.factor_observed_date
            AND p.source_record_sha256=s.source_record_sha256
            AND p.source_ingested_at=s.source_ingested_at
        )""")
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE p1_missing_grid AS
        SELECT s.* FROM p1_candidate_grid s
        WHERE NOT EXISTS (
          SELECT 1 FROM {P}lab_prospective_event_factor_grid_v1 p
          WHERE p.event_run_id=s.event_run_id AND p.venue=s.venue
            AND p.market_id=s.market_id AND p.factor_id=s.factor_id
        )""")
        missing_v=con.execute("SELECT count(*) FROM p1_missing_vintages").fetchone()[0]
        missing_g=con.execute("SELECT count(*) FROM p1_missing_grid").fetchone()[0]
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""
            INSERT INTO {P}lab_factor_warehouse_vintages_v1
            SELECT *,current_timestamp,FALSE,? FROM p1_missing_vintages
            """,[build_id])
            con.execute(f"""
            INSERT INTO {P}lab_prospective_event_factor_grid_v1
            SELECT *,? FROM p1_missing_grid
            """,[build_id])
            con.execute(f"""
            INSERT INTO {P}lab_prospective_grid_runs_v1
            VALUES (?,?,?,?,?,current_timestamp,?,?,?,?,0,0,
                    'MATERIALIZED_RESEARCH_ONLY')
            """,[build_id,VERSION,commit,script_hash,start,
                  missing_v,missing_g,observed_events,source_vintages])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build_id)
        print("SOURCE_FACTOR_VINTAGES="+str(source_vintages))
        print("EVENT_CAPTURES="+str(observed_events))
        print("ELIGIBLE_WAREHOUSE_ASOF_GRID_ROWS="+str(candidates))
        print("NEW_FACTOR_VINTAGES="+str(missing_v))
        print("NEW_GRID_ROWS="+str(missing_g))
        print("WAREHOUSE_FUTURE_FACTOR_LEAKAGE="+str(future))
        print("PROVIDER_RELEASE_TIME_INDEPENDENTLY_VERIFIED=FALSE")
        print("EVENT_FACTOR_RELATIONSHIPS_APPROVED=FALSE")
        print("INSTITUTIONAL_HISTORICAL_PIT_RELEASE=BLOCKED")
    finally:
        con.close()


if __name__ == "__main__":
    main()
