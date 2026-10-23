#!/usr/bin/env python3
"""EventRisk Factor Lab: historical market daily loading and exploratory regressions.

Backfilled snapshots are NOT point-in-time evidence. All output is explicitly
retrospective and research-only; never market-factor trading signals.
"""
from __future__ import annotations
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import duckdb

DB = "eventrisk_factor_lab"
P = DB + ".main."
VERSION = "phase1-history-v1.0.0"

def exec_sql(conn, sql, args=None):
    if args is None:
        return conn.execute(sql)
    return conn.execute(sql, args)

def main():
    if os.environ.get("LAB_RESEARCH_SCOPE") != "internal-only":
        raise SystemExit("Refusing data build without LAB_RESEARCH_SCOPE=internal-only")
    sha = os.environ.get("LAB_PIPELINE_COMMIT", "")
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise SystemExit("Full source Git commit SHA required")
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_id = VERSION + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    conn = duckdb.connect(f"md:{DB}?attach_mode=single")
    exec_sql(conn, "SET TimeZone = 'UTC'")
    try:
        exec_sql(conn, f"""
        CREATE TABLE IF NOT EXISTS {P}lab_market_daily_historical_v1 (
          venue VARCHAR NOT NULL,
          market_id VARCHAR NOT NULL,
          observed_date DATE NOT NULL,
          probability DOUBLE NOT NULL,
          probability_delta_pp DOUBLE,
          previous_observed_date DATE,
          last_quote_at TIMESTAMPTZ NOT NULL,
          snapshot_count BIGINT NOT NULL,
          snapshot_source VARCHAR NOT NULL,
          observation_provenance VARCHAR NOT NULL,
          point_in_time_verified BOOLEAN NOT NULL,
          build_id VARCHAR NOT NULL
        )""")
        exec_sql(conn, f"""
        CREATE TABLE IF NOT EXISTS {P}lab_venue_daily_features_v1 (
          venue VARCHAR NOT NULL,
          observed_date DATE NOT NULL,
          n_markets BIGINT NOT NULL,
          n_comparable_markets BIGINT NOT NULL,
          mean_absolute_delta_pp DOUBLE,
          mean_signed_delta_pp DOUBLE,
          snapshot_provenance VARCHAR NOT NULL,
          point_in_time_verified BOOLEAN NOT NULL,
          build_id VARCHAR NOT NULL
        )""")
        exec_sql(conn, f"""
        CREATE TABLE IF NOT EXISTS {P}lab_exploratory_regressions_v1 (
          factor_id VARCHAR NOT NULL,
          factor_unit VARCHAR NOT NULL,
          venue VARCHAR NOT NULL,
          predictor VARCHAR NOT NULL,
          response VARCHAR NOT NULL,
          n_sessions BIGINT NOT NULL,
          distinct_months BIGINT NOT NULL,
          first_date DATE,
          last_date DATE,
          slope DOUBLE,
          intercept DOUBLE,
          r_squared DOUBLE,
          correlation DOUBLE,
          model_class VARCHAR NOT NULL,
          point_in_time_verified BOOLEAN NOT NULL,
          approved_for_decision_use BOOLEAN NOT NULL,
          interpretation_warning VARCHAR NOT NULL,
          build_id VARCHAR NOT NULL
        )""")
        exec_sql(conn, f"""
        CREATE TABLE IF NOT EXISTS {P}lab_history_build_runs_v1 (
          build_id VARCHAR NOT NULL,
          pipeline_version VARCHAR NOT NULL,
          source_commit VARCHAR NOT NULL,
          script_sha256 VARCHAR NOT NULL,
          built_at TIMESTAMPTZ NOT NULL,
          raw_snapshot_rows BIGINT NOT NULL,
          daily_market_rows BIGINT NOT NULL,
          venue_daily_rows BIGINT NOT NULL,
          exploratory_regression_rows BIGINT NOT NULL,
          point_in_time_eligible_rows BIGINT NOT NULL,
          release_state VARCHAR NOT NULL
        )""")
        # Use snapshot timestamps only as event-time labels. Backfill lacks
        # verifiable "available-at" timestamps, so PIT eligibility is FALSE.
        # A bounded price is midpoint of valid bid/ask, otherwise valid last.
        # Never use snapshots' market-version text added in October 2026 to
        # retroactively classify 2021-2025 historical topics.
        exec_sql(conn, f"""
        CREATE OR REPLACE TEMP TABLE phase1_daily_snapshot AS
        WITH valid AS (
          SELECT venue, market_id, CAST(ts AS DATE) AS observed_date, ts,
                 CASE WHEN yes_bid BETWEEN 0 AND 1
                            AND yes_ask BETWEEN 0 AND 1
                            AND yes_ask >= yes_bid
                            THEN (yes_bid + yes_ask) / 2
                      WHEN last BETWEEN 0 AND 1 THEN last
                      ELSE NULL END AS px,
                 COALESCE(source,'unknown') AS snapshot_source
          FROM {P}market_snapshots
          WHERE ts IS NOT NULL AND venue IS NOT NULL AND market_id IS NOT NULL
        )
        SELECT venue, market_id, observed_date,
               arg_max(px,ts) AS probability,
               arg_max(ts,ts) AS last_quote_at,
               count(*) AS snapshot_count,
               arg_max(snapshot_source,ts) AS snapshot_source
        FROM valid
        WHERE px IS NOT NULL
        GROUP BY venue, market_id, observed_date
        """)
        exec_sql(conn, """
        CREATE OR REPLACE TEMP TABLE phase1_market_history AS
        WITH lagged AS (
          SELECT *,
            lag(probability) OVER (
               PARTITION BY venue, market_id ORDER BY observed_date
            ) AS prev_probability,
            lag(observed_date) OVER (
               PARTITION BY venue, market_id ORDER BY observed_date
            ) AS previous_observed_date
          FROM phase1_daily_snapshot
        )
        SELECT venue, market_id, observed_date, probability,
          CASE WHEN date_diff('day',previous_observed_date,observed_date) BETWEEN 1 AND 7
                    THEN 100.0 * (probability - prev_probability)
               ELSE NULL END AS probability_delta_pp,
          previous_observed_date,last_quote_at,snapshot_count,snapshot_source,
          'event_time_only_snapshot_capture_unverified' AS observation_provenance,
          FALSE AS point_in_time_verified
        FROM lagged
        """)
        exec_sql(conn, """
        CREATE OR REPLACE TEMP TABLE phase1_venue_daily AS
        SELECT venue,observed_date,
          count(*) AS n_markets,
          count(probability_delta_pp) AS n_comparable_markets,
          avg(abs(probability_delta_pp)) AS mean_absolute_delta_pp,
          avg(probability_delta_pp) AS mean_signed_delta_pp,
          'historical_event_time_not_availability_time' AS snapshot_provenance,
          FALSE AS point_in_time_verified
        FROM phase1_market_history GROUP BY venue, observed_date
        """)
        # Factor observations are historical values not historical vintages;
        # provenance timestamps stay later than event cutoffs. No PIT release.
        exec_sql(conn, f"""
        CREATE OR REPLACE TEMP TABLE phase1_factor_daily AS
        WITH latest AS (
          SELECT f.factor_id, f.observed_date, f.value, f.unit,
            row_number() OVER (
              PARTITION BY f.factor_id,f.observed_date
              ORDER BY f.ingested_at DESC,f.record_sha256 DESC
            ) AS rk
          FROM {P}lab_factor_observations f
          JOIN {P}lab_factor_catalog c USING(factor_id)
          WHERE c.active=TRUE AND c.license_class NOT LIKE 'restricted%'
            AND f.unit=c.unit AND isfinite(f.value)
        ), aligned AS (
          SELECT factor_id, observed_date, value, unit,
            lag(value) OVER (PARTITION BY factor_id ORDER BY observed_date) AS prev_value,
            lag(observed_date) OVER (PARTITION BY factor_id ORDER BY observed_date) AS prev_date
          FROM latest WHERE rk=1
        )
        SELECT factor_id, observed_date, unit,
          CASE WHEN date_diff('day',prev_date,observed_date) BETWEEN 1 AND 7
               THEN CASE WHEN unit='percent' THEN 100.0*(value-prev_value)
                         ELSE value-prev_value END
               ELSE NULL END AS factor_change
        FROM aligned
        """)
        exec_sql(conn, """
        CREATE OR REPLACE TEMP TABLE phase1_pairs AS
        SELECT f.factor_id, f.unit, v.venue, v.observed_date,
               v.mean_absolute_delta_pp AS x,
               f.factor_change AS y
        FROM phase1_factor_daily f JOIN phase1_venue_daily v USING(observed_date)
        WHERE v.n_comparable_markets >= 10 AND f.factor_change IS NOT NULL
              AND v.mean_absolute_delta_pp IS NOT NULL
              AND isfinite(f.factor_change)
              AND isfinite(v.mean_absolute_delta_pp)
        """)
        exec_sql(conn, """
        CREATE OR REPLACE TEMP TABLE phase1_regressions AS
        SELECT factor_id, unit AS factor_unit, venue,
          'mean_absolute_market_probability_change_pp' AS predictor,
          CASE WHEN unit='percent' THEN 'factor_daily_change_bps'
               ELSE 'factor_daily_change_native_unit' END AS response,
          count(*) AS n_sessions,
          count(DISTINCT date_trunc('month',observed_date)) AS distinct_months,
          min(observed_date) AS first_date,
          max(observed_date) AS last_date,
          regr_slope(y,x) AS slope,
          regr_intercept(y,x) AS intercept,
          regr_r2(y,x) AS r_squared,
          corr(x,y) AS correlation,
          'EXPLORATORY_CONTEMPORANEOUS_ASSOCIATION' AS model_class,
          FALSE AS point_in_time_verified,
          FALSE AS approved_for_decision_use,
          'backfilled events; revised factor values; same-day association; no event-level identification or significance claims' AS interpretation_warning
        FROM phase1_pairs
        GROUP BY factor_id,unit,venue
        HAVING count(*) >= 120
           AND count(DISTINCT date_trunc('month',observed_date)) >= 12
           AND var_samp(x) > 0 AND var_samp(y) > 0
        """)
        c = conn.execute("""
          SELECT
           (SELECT count(*) FROM phase1_market_history),
           (SELECT count(*) FROM phase1_venue_daily),
           (SELECT count(*) FROM phase1_regressions)
        """).fetchone()
        print("HISTORICAL_MARKET_DAILY_ROWS=", c[0])
        print("VENUE_DAILY_ROWS=", c[1])
        print("EXPLORATORY_MODELS=", c[2])
        # Insert all new outputs atomically. Source and prior v3 panel unchanged.
        exec_sql(conn, "BEGIN TRANSACTION")
        try:
            exec_sql(conn,f"DELETE FROM {P}lab_market_daily_historical_v1")
            exec_sql(conn,f"DELETE FROM {P}lab_venue_daily_features_v1")
            exec_sql(conn,f"DELETE FROM {P}lab_exploratory_regressions_v1")
            exec_sql(conn, f"""
              INSERT INTO {P}lab_market_daily_historical_v1
              SELECT *,? AS build_id FROM phase1_market_history
            """,[build_id])
            exec_sql(conn, f"""
              INSERT INTO {P}lab_venue_daily_features_v1
              SELECT *,? AS build_id FROM phase1_venue_daily
            """,[build_id])
            exec_sql(conn, f"""
              INSERT INTO {P}lab_exploratory_regressions_v1
              SELECT *,? AS build_id FROM phase1_regressions
            """,[build_id])
            exec_sql(conn, f"""
              INSERT INTO {P}lab_history_build_runs_v1
              SELECT ?,?,?,?,current_timestamp,
                (SELECT count(*) FROM {P}market_snapshots),
                ?,?,?,0,'RETROSPECTIVE_RESEARCH_NOT_RELEASED'
            """,[build_id,VERSION,sha,script_sha,c[0],c[1],c[2]])
            exec_sql(conn,"COMMIT")
        except Exception:
            exec_sql(conn,"ROLLBACK")
            raise
        print("BUILD_ID=", build_id)
        print("RESULT=HISTORICAL_RESEARCH_MATERIALIZED_NOT_PIT_VALIDATED")
    finally:
        conn.close()

if __name__=="__main__":
    main()
