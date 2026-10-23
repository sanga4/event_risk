#!/usr/bin/env python3
"""Construct forward-collected, no-lookahead event quote feature views.

Views update as new capture runs arrive. A venue's provider quote time is
unverified; receipt-time provenance is a DIFFERENT claim. No backtesting release.
"""
import hashlib
import os
from pathlib import Path

import duckdb

DB = "eventrisk_factor_lab"
P = DB + ".main."


def main():
    if os.getenv("LAB_RESEARCH_SCOPE") != "internal-only":
        raise RuntimeError("Internal-only research scope required")
    commit = os.getenv("LAB_PIPELINE_COMMIT", "")
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Source must be pinned to an immutable full SHA")
    print("SOURCE_COMMIT=" + commit)
    print("SCRIPT_SHA256=" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        con.execute(f"""
        CREATE OR REPLACE VIEW {P}lab_live_event_features_v1 AS
        WITH ordered AS (
          SELECT
            'prop:' || venue || ':' || market_id AS proposition_id,
            venue, market_id, event_id, event_title, question,
            run_id, yes_probability, quote_basis,
            source_record_sha256, contract_sha256,
            capture_received_at,
            provider_quote_at,
            capture_time_verified,
            provider_quote_freshness_verified,
            historical_point_in_time_released,
            lag(yes_probability) OVER (
              PARTITION BY venue, market_id
              ORDER BY capture_received_at, run_id
            ) AS previous_probability,
            lag(capture_received_at) OVER (
              PARTITION BY venue, market_id
              ORDER BY capture_received_at, run_id
            ) AS previous_capture_at
          FROM {P}lab_live_market_captures_v1
          WHERE yes_probability BETWEEN 0 AND 1
        )
        SELECT
          proposition_id, venue, market_id, event_id, event_title, question,
          run_id,
          CAST(timezone('UTC',capture_received_at) AS DATE) AS observed_date_utc,
          capture_received_at AS known_at,
          capture_received_at AS observed_at,
          yes_probability AS probability,
          previous_probability,
          previous_capture_at,
          CASE WHEN previous_capture_at IS NOT NULL
                     AND date_diff('second',previous_capture_at,capture_received_at) BETWEEN 1 AND 172800
               THEN 100.0*(yes_probability-previous_probability)
               ELSE NULL
          END AS probability_delta_pp,
          quote_basis, contract_sha256, source_record_sha256,
          capture_time_verified, provider_quote_freshness_verified,
          historical_point_in_time_released,
          'captured_from_public_http_response_not_provider_quote_time'::VARCHAR
            AS capture_provenance,
          FALSE AS released_for_historical_backtesting
        FROM ordered
        """)
        con.execute(f"""
        CREATE OR REPLACE VIEW {P}lab_live_market_latest_v1 AS
        WITH ordered AS (
          SELECT *,
                 ROW_NUMBER() OVER (
                   PARTITION BY venue,market_id
                   ORDER BY known_at DESC,run_id DESC
                 ) AS rn
          FROM {P}lab_live_event_features_v1
        )
        SELECT * EXCLUDE(rn)
        FROM ordered WHERE rn = 1
        """)
        con.execute(f"""
        CREATE OR REPLACE VIEW {P}lab_capture_feed_freshness_v1 AS
        WITH venue_runs AS (
          SELECT run_id, finished_at AS last_run_at,
                 je.key::VARCHAR AS venue,
                 je.value->>'state' AS venue_state,
                 try_cast(je.value->>'captured' AS BIGINT) AS reported_capture_count
          FROM {P}lab_live_capture_runs_v1 r,
               json_each(r.venue_results) AS je
        ), ranked AS (
          SELECT *,ROW_NUMBER() OVER (
              PARTITION BY venue ORDER BY last_run_at DESC,run_id DESC
          ) AS rk FROM venue_runs
        )
        SELECT venue,last_run_at,venue_state,reported_capture_count,
               date_diff('minute',last_run_at,current_timestamp) AS age_minutes,
               (venue_state = 'ok' AND
                date_diff('minute',last_run_at,current_timestamp) BETWEEN 0 AND 90
                AND reported_capture_count > 0) AS collector_operational_recently,
               FALSE AS institutional_quote_freshness_certified
        FROM ranked WHERE rk=1
        """)
        rows=con.execute(f"""
           SELECT venue,COUNT(*) AS captured,
             COUNT(*) FILTER (WHERE probability_delta_pp IS NOT NULL) AS transitions,
             MAX(known_at) AS latest
           FROM {P}lab_live_event_features_v1 GROUP BY venue
        """).fetchall()
    for venue,n,transitions,latest in rows:
        print(f"VENUE={venue} CAPTURED={n} TRANSITIONS={transitions} LAST={latest}")
    print("HISTORICAL_BACKTEST_RELEASE=FALSE")


if __name__ == "__main__":
    main()
