#!/usr/bin/env python3
"""Fail-closed capture-to-grid operational handoff; research-only.

Run AFTER source-native capture, feature refresh and warehouse-as-of grid build.
Do NOT treat receipt time as provider original quote published_at, and do not
advance production approval from successful collector receipts.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

EXPECTED_VENUES=frozenset(("kalshi","polymarket"))
MAX_AGE_MINUTES=720
MAX_GRID_CAPTURE_LAG_SECONDS=120

def assess(feeds, source_runs, grid_runs, grid_integrity):
    """All counts are from independently queried warehouse tables.

    feeds: venue, state, reported latest count, age_minutes, operational flag,
           independently certified provider quote clock
    source_runs: venue, run_id, stored records, latest source receipt, bad flags
    grid_runs: venue, event_run_id, co-observation rows, unique markets,
               max grid event receipt, future factor rows, false approvals
    grid_integrity: duplicate event/factor keys, future joins, false approvals
    """
    if len(feeds)!=2 or {x[0] for x in feeds}!=EXPECTED_VENUES:
        raise ValueError("Both venue collector status records required")
    if len(source_runs)!=2 or {x[0] for x in source_runs}!=EXPECTED_VENUES:
        raise ValueError("Both venue original stored capture runs required")
    if len(grid_runs)!=2 or {x[0] for x in grid_runs}!=EXPECTED_VENUES:
        raise ValueError("Both captured runs must be materialized into factor grid")
    if len(grid_integrity)!=3 or any(x!=0 for x in grid_integrity):
        raise ValueError("Future factor, duplicate as-of keys, or unsupported model approval")
    by_feed={x[0]:x for x in feeds}
    by_grid={x[0]:x for x in grid_runs}
    total_capture=total_grid=0
    for venue,run_id,n,received_at,bad in source_runs:
        f=by_feed[venue]
        g=by_grid[venue]
        if (not run_id or len(f)!=6 or len(g)!=7
            or f[1]!="ok" or f[2]<1 or f[3] is None
            or not 0<=f[3]<=MAX_AGE_MINUTES or f[4] is not True
            or f[5] is not False or n<1 or n!=f[2] or bad
            or received_at is None or received_at.tzinfo is None
            or g[1]!=run_id or g[2]<n or g[3]!=n
            or g[4] is None or g[4].tzinfo is None
            or g[5]!=0 or g[6]!=0
            or g[4]>received_at
            or (received_at-g[4]).total_seconds()>MAX_GRID_CAPTURE_LAG_SECONDS):
            raise ValueError("Collector-to-grid source run, freshness or calendar mismatch")
        total_capture+=n
        total_grid+=g[2]
    return dict(venues=2,latest_capture_rows=total_capture,
                latest_capture_grid_rows=total_grid,
                warehouse_grid_reconciled=True,
                original_quote_clock_verified=False,
                institutional_risk_release=False)

def inspect(con):
    feeds=con.execute("""SELECT venue,venue_state,reported_capture_count,
       age_minutes,collector_operational_recently,
       institutional_quote_freshness_certified
       FROM eventrisk_factor_lab.main.lab_capture_feed_freshness_v1
       WHERE venue IN ('kalshi','polymarket') ORDER BY venue""").fetchall()
    source=con.execute("""WITH latest AS (
        SELECT venue,arg_max(run_id,capture_received_at) AS run_id
        FROM eventrisk_factor_lab.main.lab_live_market_captures_v1
        GROUP BY venue)
      SELECT c.venue,c.run_id,count(*),max(c.capture_received_at),
        count(*) FILTER(WHERE NOT c.capture_time_verified
           OR c.provider_quote_freshness_verified
           OR c.historical_point_in_time_released
           OR c.provider_quote_at IS NOT NULL
           OR c.data_use_class<>'internal_research_only'
           OR length(c.source_record_sha256)<>64
           OR length(c.source_response_sha256)<>64
           OR c.capture_received_at>current_timestamp+INTERVAL 5 MINUTE)
      FROM eventrisk_factor_lab.main.lab_live_market_captures_v1 c
      JOIN latest l ON c.venue=l.venue AND c.run_id=l.run_id
      GROUP BY c.venue,c.run_id ORDER BY c.venue""").fetchall()
    grid=con.execute("""WITH latest AS (
        SELECT venue,arg_max(run_id,capture_received_at) AS run_id
        FROM eventrisk_factor_lab.main.lab_live_market_captures_v1
        GROUP BY venue)
      SELECT g.venue,g.event_run_id,count(*),
        count(DISTINCT g.market_id),max(g.event_capture_at),
        count(*) FILTER(WHERE g.factor_ingested_at>g.event_capture_at
          OR g.factor_available_at>g.event_capture_at),
        count(*) FILTER(WHERE g.exchange_quote_time_independently_verified
          OR g.factor_publication_time_independently_verified
          OR g.event_to_factor_mapping_approved
          OR g.historical_backtest_released)
      FROM eventrisk_factor_lab.main.lab_prospective_event_factor_grid_v1 g
      JOIN latest l ON g.venue=l.venue AND g.event_run_id=l.run_id
      GROUP BY g.venue,g.event_run_id ORDER BY g.venue""").fetchall()
    global_grid=con.execute("""SELECT
       count(*) FROM (
         SELECT event_run_id,venue,market_id,factor_id,count(*) n
         FROM eventrisk_factor_lab.main.lab_prospective_event_factor_grid_v1
         GROUP BY 1,2,3,4 HAVING n>1
       )""").fetchone()[0]
    integrity=con.execute("""SELECT count(*) FILTER(WHERE
       factor_ingested_at>event_capture_at OR
       factor_available_at>event_capture_at),
       count(*) FILTER(WHERE exchange_quote_time_independently_verified OR
       factor_publication_time_independently_verified OR
       event_to_factor_mapping_approved OR historical_backtest_released)
       FROM eventrisk_factor_lab.main.lab_prospective_event_factor_grid_v1""").fetchone()
    return feeds,source,grid,(global_grid,*integrity)

def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40
        or any(ch not in "0123456789abcdef" for ch in commit)):
        raise RuntimeError("Pinned source SHA and internal-only research scope required")
    import duckdb
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        result=assess(*inspect(con))
    print(f"PINNED_COMMIT={commit}")
    print(f"LATEST_CAPTURE_ROWS={result['latest_capture_rows']}")
    print(f"LATEST_GRID_ROWS={result['latest_capture_grid_rows']}")
    print("TWO_VENUE_RECEIPT_TO_ASOF_GRID=RECONCILED")
    print("PROVIDER_QUOTE_PUBLISHED_AT=UNVERIFIED INSTITUTIONAL_RELEASE=FALSE")

if __name__=="__main__":
    main()
