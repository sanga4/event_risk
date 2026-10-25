#!/usr/bin/env python3
"""Append-only original-publication-clock gap audit, never source certification.

All current public-venue timestamps are local HTTP receipt times unless an
independent original provider published-at record is separately verified.
Historical equity prices and factor observations are retrospective research.
"""
from __future__ import annotations
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

DB = 'eventrisk_factor_lab'
P = DB + '.main.'
VERSION = 'phase1-source-clock-gap-v1.0.0'


def inspect(con, prefix=P):
    """Aggregate existing evidence; avoid copying licensed source records."""
    fb = con.execute(f"SELECT build_id FROM {prefix}lab_source_family_evidence_builds_v1 ORDER BY created_at DESC LIMIT 1").fetchone()
    if fb is None:
        raise RuntimeError('No versioned source-family inventory')
    families = con.execute(f"""SELECT domain, source_row_count, provider_original_publication_verified,
          commercial_reuse_approved, institutional_factor_model_approved, next_required_evidence
        FROM {prefix}lab_source_family_evidence_v1 WHERE build_id=? ORDER BY domain""", [fb[0]]).fetchall()
    venues = con.execute(f"""SELECT venue,COUNT(*),
        COUNT(*) FILTER(WHERE provider_quote_at IS NOT NULL),
        COUNT(*) FILTER(WHERE capture_received_at>current_timestamp+INTERVAL 5 MINUTE
          OR capture_received_at<TIMESTAMPTZ '2020-01-01'
          OR length(source_response_sha256)<>64
          OR length(source_record_sha256)<>64
          OR length(contract_sha256)<>64
          OR NOT yes_probability BETWEEN 0 AND 1
          OR (provider_quote_freshness_verified AND provider_quote_at IS NULL)
          OR historical_point_in_time_released),
        MAX(capture_received_at)
      FROM {prefix}lab_live_market_captures_v1 GROUP BY venue ORDER BY venue""").fetchall()
    prices = con.execute(f"""SELECT COUNT(*),COUNT(*) FILTER(WHERE
       fetched_at IS NULL OR fetched_at<CAST(date AS TIMESTAMPTZ)
       OR close<=0 OR adj_close<=0 OR NOT isfinite(close) OR NOT isfinite(adj_close)),
       COUNT(DISTINCT ticker) FROM {prefix}security_prices""").fetchone()
    grid = con.execute(f"""SELECT COUNT(*),COUNT(*) FILTER(WHERE
        factor_ingested_at>event_capture_at OR factor_available_at>event_capture_at),
        COUNT(*) FILTER(WHERE exchange_quote_time_independently_verified
        OR factor_publication_time_independently_verified
        OR event_to_factor_mapping_approved OR historical_backtest_released)
        FROM {prefix}lab_prospective_event_factor_grid_v1""").fetchone()
    return fb[0],families,venues,prices,grid


def assess(inventory, families, venues, prices, grid):
    """Integrity failure blocks materialization; a valid report is not approval."""
    if len(families)!=16 or len({r[0] for r in families})!=16:
        raise RuntimeError('Incomplete or duplicate source-family inventory')
    if sorted(v[0] for v in venues)!=['kalshi','polymarket']:
        raise RuntimeError('Unexpected venue set')
    if any(v[1]<=0 or v[3]!=0 for v in venues):
        raise RuntimeError('Malformed or falsely approved venue source records')
    if prices[0]<50000 or prices[1]!=0 or prices[2]<50:
        raise RuntimeError('Invalid security price source coverage')
    if grid[0]<=0 or grid[1]!=0 or grid[2]!=0:
        raise RuntimeError('Future warehouse factor leakage or false release')
    if any(f[1]<0 for f in families):
        raise RuntimeError('Invalid source-family row count')
    details=[]
    for domain,n,original_time,rights,model_approved,evidence in families:
        state='MISSING_SOURCE' if not n else 'SOURCE_CLOCK_AND_RIGHTS_REVIEW_REQUIRED'
        if original_time or rights or model_approved:
            state='UPSTREAM_ASSERTION_REQUIRES_INDEPENDENT_REVIEW'
        details.append(('SOURCE_FAMILY',domain,int(n),bool(original_time),bool(rights),
                        False,False,state,evidence or 'Independent original publication and reuse evidence'))
    for venue,n,known_quote_time,bad,latest in venues:
        details.append(('VENUE_HTTP_RECEIPT',venue,int(n),False,False,False,False,
            'ORIGINAL_QUOTE_TIME_NOT_CERTIFIED',
            f'Official first-published quote clock and rights; stored provider quote timestamps {known_quote_time}/{n}'))
    details.append(('RETROSPECTIVE_SECURITY_PRICES','yahoo_adjusted',int(prices[0]),
      False,False,False,False,'ORIGINAL_ISSUER_ACTION_VINTAGES_MISSING',
      'Permanent issuer identifiers, original closes, split/dividend revisions, rights and dual review'))
    details.append(('WAREHOUSE_ASOF_GRID','event_factor_coobservations',int(grid[0]),
      False,False,False,False,'WAREHOUSE_KNOWN_NOT_PROVIDER_PIT',
      'Original quote and macro publication clocks, revision history and approved economic mappings'))
    assert len(details)==20
    return dict(inventory=inventory,family_count=16,loaded=sum(f[1]>0 for f in families),
        market_receipts=sum(int(v[1]) for v in venues),quote_time_present=sum(int(v[2]) for v in venues),
        bad_receipts=sum(int(v[3]) for v in venues),price_rows=int(prices[0]),
        bad_prices=int(prices[1]),grid_rows=int(grid[0]),future_grid_rows=int(grid[1]),
        falsely_approved=int(grid[2]),details=details)


def setup(con, prefix=P):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {prefix}lab_source_clock_gap_builds_v1(
      build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,script_sha256 VARCHAR NOT NULL,
      built_at TIMESTAMPTZ NOT NULL, source_family_build VARCHAR NOT NULL,
      source_families BIGINT NOT NULL, loaded_families BIGINT NOT NULL,
      missing_families BIGINT NOT NULL,market_receipts BIGINT NOT NULL,
      provider_quote_timestamp_present BIGINT NOT NULL, invalid_market_receipts BIGINT NOT NULL,
      vendor_security_price_rows BIGINT NOT NULL,invalid_security_price_rows BIGINT NOT NULL,
      warehouse_asof_grid_rows BIGINT NOT NULL, future_warehouse_rows BIGINT NOT NULL,
      false_upstream_approvals BIGINT NOT NULL, independently_signed_original_clocks BIGINT NOT NULL,
      institutional_release_approved BOOLEAN NOT NULL, release_state VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {prefix}lab_source_clock_gap_subjects_v1(
      build_id VARCHAR NOT NULL,subject_class VARCHAR NOT NULL,subject_id VARCHAR NOT NULL,
      n_observations BIGINT NOT NULL,upstream_source_time_asserted BOOLEAN NOT NULL,
      upstream_rights_asserted BOOLEAN NOT NULL, independently_signed_clock BOOLEAN NOT NULL,
      institutional_release_approved BOOLEAN NOT NULL, acceptance_state VARCHAR NOT NULL,
      next_required_evidence VARCHAR NOT NULL)""")


def main():
    sha=os.getenv('LAB_PIPELINE_COMMIT','')
    if (os.getenv('LAB_RESEARCH_SCOPE')!='internal-only' or len(sha)!=40
         or any(c not in '0123456789abcdef' for c in sha)):
        raise RuntimeError('Pinned Git SHA and internal research-only scope required')
    import duckdb
    build=VERSION+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect('md:eventrisk_factor_lab?attach_mode=single') as con:
        con.execute("SET TimeZone='UTC'")
        r=assess(*inspect(con))
        setup(con)
        con.execute('BEGIN TRANSACTION')
        try:
            con.execute(f"""INSERT INTO {P}lab_source_clock_gap_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,?,?,0,FALSE,
                     'GAP_AUDIT_ONLY_SOURCE_PIT_AND_RIGHTS_NOT_INDEPENDENTLY_ATTESTED')""",
              [build,sha,digest,r['inventory'],r['family_count'],r['loaded'],
               r['family_count']-r['loaded'],r['market_receipts'],r['quote_time_present'],
               r['bad_receipts'],r['price_rows'],r['bad_prices'],r['grid_rows'],
               r['future_grid_rows'],r['falsely_approved']])
            con.executemany(f"""INSERT INTO {P}lab_source_clock_gap_subjects_v1
              VALUES (?,?,?,?,?,?,?,?,?,?)""",[(build,*row) for row in r['details']])
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise
    print('BUILD_ID='+build)
    print(f"SOURCE_FAMILIES=16 LOADED={r['loaded']} MISSING={16-r['loaded']}")
    print(f"MARKET_RECEIPTS={r['market_receipts']} ORIGINAL_QUOTE_TIMES_PRESENT={r['quote_time_present']}")
    print(f"SECURITY_PRICES={r['price_rows']} GRID={r['grid_rows']} FUTURE_WAREHOUSE={r['future_grid_rows']}")
    print('INDEPENDENT_SOURCE_CLOCK_SIGNOFFS=0 INSTITUTIONAL_RELEASE=FALSE')


if __name__=='__main__':
    main()
