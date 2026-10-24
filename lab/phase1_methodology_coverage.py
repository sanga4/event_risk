#!/usr/bin/env python3
"""Versioned Phase I factor/data coverage and beta-identifiability assessment.

Pure diagnostic ELT; never invent missing market prices, factors or betas.
"""
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
import duckdb

P="eventrisk_factor_lab.main."
V="phase1-methodology-audit-v1.0.0"

def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Only internal research with pinned commit is allowed")
    build=V+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
          CREATE TABLE IF NOT EXISTS {P}lab_institutional_data_coverage_v1 (
          build_id VARCHAR NOT NULL, dimension VARCHAR NOT NULL,series_id VARCHAR NOT NULL,
          first_date DATE,last_date DATE,n_records BIGINT NOT NULL,
          n_distinct_dates BIGINT NOT NULL,n_market_ids BIGINT NOT NULL,
          data_class VARCHAR NOT NULL,source_time_verified BOOLEAN NOT NULL,
          beta_ready BOOLEAN NOT NULL,deficiency VARCHAR NOT NULL,
          recorded_at TIMESTAMPTZ NOT NULL,source_commit VARCHAR NOT NULL,
          script_sha256 VARCHAR NOT NULL)
        """)
        con.execute(f"""
          CREATE TABLE IF NOT EXISTS {P}lab_institutional_beta_readiness_v1 (
          build_id VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
          qualitative_factor_definitions BIGINT NOT NULL,
          factor_catalog_series BIGINT NOT NULL,
          active_factor_catalog_series BIGINT NOT NULL,
          quantitative_observed_factor_series BIGINT NOT NULL,
          source_vintage_verified_series BIGINT NOT NULL,
          historical_market_snapshots BIGINT NOT NULL,
          historical_market_days BIGINT NOT NULL,
          captured_forward_market_quotes BIGINT NOT NULL,
          warehouse_asof_event_factor_pairs BIGINT NOT NULL,
          independent_event_factor_mapping_approvals BIGINT NOT NULL,
          preliminary_venue_regressions BIGINT NOT NULL,
          robust_exploratory_regressions BIGINT NOT NULL,
          independently_validated_security_betas BIGINT NOT NULL,
          independently_validated_event_factor_responses BIGINT NOT NULL,
          approved_for_institutional_use BOOLEAN NOT NULL,
          status VARCHAR NOT NULL,source_commit VARCHAR NOT NULL,
          script_sha256 VARCHAR NOT NULL)
        """)
        # Count rates and other factors as they exist; never infer missing series.
        con.execute(f"""
          CREATE OR REPLACE TEMP TABLE temp_factor_coverage AS
          SELECT c.factor_id,c.family,c.license_class,c.unit,c.active,
                 min(f.observed_date) AS first_date,
                 max(f.observed_date) AS last_date,
                 count(f.value) AS n_records,
                 count(distinct f.observed_date) AS n_dates
          FROM {P}lab_factor_catalog c
          LEFT JOIN {P}lab_factor_observations f USING(factor_id)
          GROUP BY c.factor_id,c.family,c.license_class,c.unit,c.active
        """)
        con.execute(f"""
          CREATE OR REPLACE TEMP TABLE temp_market_coverage AS
          SELECT venue, min(CAST(ts AS DATE)) first_date,
                 max(CAST(ts AS DATE)) last_date,
                 count(*) n_records,
                 count(DISTINCT CAST(ts AS DATE)) n_dates,
                 count(DISTINCT market_id) n_markets
          FROM {P}market_snapshots GROUP BY venue
        """)
        counts=con.execute(f"""
          SELECT
           (SELECT COUNT(*) FROM temp_factor_coverage),
           (SELECT count(*) FROM temp_factor_coverage WHERE active),
           (SELECT count(*) FROM temp_factor_coverage WHERE n_records>0),
           (SELECT count(distinct factor_id) FROM {P}lab_factor_warehouse_vintages_v1 WHERE independent_release_time_verified),
           (SELECT count(*) FROM {P}market_snapshots),
           (SELECT count(*) FROM {P}lab_market_daily_historical_v1),
           (SELECT count(*) FROM {P}lab_live_market_captures_v1),
           (SELECT count(*) FROM {P}lab_prospective_event_factor_grid_v1),
           (SELECT count(*) FROM {P}lab_relations WHERE status IN ('approved','accepted') AND evidence_id IS NOT NULL),
           (SELECT count(*) FROM {P}lab_exploratory_regressions_v1),
           (SELECT count(*) FROM {P}lab_robust_regressions_v2)
        """).fetchone()
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""
               INSERT INTO {P}lab_institutional_data_coverage_v1
               SELECT ?, 'factor_series',factor_id,first_date,last_date,
                 n_records,n_dates,0,
                 CASE WHEN n_records=0 THEN 'not_loaded'
                   ELSE 'retrospective_warehouse_ingested' END,
                 FALSE,FALSE,
                 CASE WHEN license_class LIKE 'restricted%' THEN 'restricted_license'
                   WHEN license_class='check_fred_source_terms' THEN 'license_terms_unchecked'
                   WHEN n_records=0 THEN 'quantitative_history_missing'
                   ELSE 'independent_provider_publication_vintages_missing' END,
                 current_timestamp,?,?
               FROM temp_factor_coverage
            """,[build,commit,digest])
            con.execute(f"""
               INSERT INTO {P}lab_institutional_data_coverage_v1
               SELECT ?,'market_snapshots',venue,first_date,last_date,
                 n_records,n_dates,n_markets,'historical_backfill_uncertified',
                 FALSE,FALSE,'original_exchange_quote_first_available_at_unverified',
                 current_timestamp,?,?
               FROM temp_market_coverage
            """,[build,commit,digest])
            con.execute(f"""
               INSERT INTO {P}lab_institutional_beta_readiness_v1
               VALUES (?,current_timestamp,108,?,?,?,?,?,?,?,?,?,?,?,?,0,0,FALSE,
                       'BETA_UNESTIMABLE_INSTITUTIONAL_RELEASE_BLOCKED',?,?)
            """,[build,*counts,commit,digest])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build}")
        print(f"FACTOR_CATALOG={counts[0]} ACTIVE={counts[1]} OBSERVED_SERIES={counts[2]}")
        print(f"SOURCE_VINTAGE_CERTIFIED={counts[3]}")
        print(f"HISTORICAL_MARKET_SNAPSHOTS={counts[4]} HISTORICAL_DAYS={counts[5]}")
        print(f"FORWARD_MARKET_QUOTES={counts[6]} ASOF_RESEARCH_GRID={counts[7]}")
        print(f"EVIDENCED_MAPPINGS={counts[8]} OLS_FITS={counts[9]} ROBUST_FITS={counts[10]}")
        print("VALIDATED_SECURITY_BETAS=0 VALIDATED_EVENT_FACTOR_RESPONSES=0")
        print("INSTITUTIONAL_RELEASE=BLOCKED")
    finally:
        con.close()

if __name__=="__main__":
    main()
