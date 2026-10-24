#!/usr/bin/env python3
"""Reproducible *research-only* source price exceptions and rate-beta sensitivity.

Does NOT claim a >25% price change is an error. Original closes/adjustments,
FX quote orientation, exchange events and historical first availability must
be independently verified before resolving cases. No source tables modified.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import math
import os
from pathlib import Path
from collections import defaultdict

import duckdb
from phase1_security_rate_beta_backfill import fit_regression

DB="eventrisk_factor_lab"
P=f"{DB}.main."
VERSION="phase1-security-source-exceptions-v1.0.0"


def stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_price_exceptions AS
    WITH latest_raw AS (
      SELECT ticker,date,close,adj_close,volume,currency,
             fetched_at,source,run_id,
             ROW_NUMBER() OVER(PARTITION BY ticker,date
               ORDER BY fetched_at DESC NULLS LAST,run_id DESC,
                        adj_close DESC) AS rn
      FROM {P}security_prices
    ), clustered AS (
      SELECT observed_date,COUNT(DISTINCT ticker) AS
        independent_symbols_with_flagged_moves
      FROM {P}lab_security_returns_retro_v1
      WHERE large_absolute_log_return GROUP BY observed_date
    )
    SELECT r.ticker,r.observed_date,r.previous_observed_date,
      r.previous_close,r.adjusted_close,r.return_bps,
      raw.close AS unadjusted_source_close,
      raw.adj_close AS source_adjusted_close,
      raw.volume,raw.currency,raw.source AS source_vendor,
      raw.fetched_at AS source_retrieved_at,raw.run_id AS source_run_id,
      cl.independent_symbols_with_flagged_moves,
      CASE WHEN cl.independent_symbols_with_flagged_moves>1
        THEN 'CROSS_SECURITY_DATE_CLUSTER_REQUIRES_SOURCE_EVIDENCE'
        ELSE 'SINGLE_SECURITY_LARGE_MOVE_REQUIRES_SOURCE_EVIDENCE'
      END AS exception_category,
      'PENDING_ORIGINAL_PRICE_CORPORATE_ACTION_AND_EVENT_REVIEW'::VARCHAR
        AS review_state,
      FALSE AS original_price_quote_time_verified,
      FALSE AS adjustment_vintage_verified,
      FALSE AS external_data_rights_approved,
      FALSE AS eligible_for_production_release
    FROM {P}lab_security_returns_retro_v1 r
    JOIN latest_raw raw ON raw.ticker=r.ticker AND
      raw.date=r.observed_date AND raw.rn=1
    JOIN clustered cl USING (observed_date)
    WHERE r.large_absolute_log_return
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_duplicate_prices AS
    SELECT ticker,date,
      count(*) AS source_records,min(adj_close) AS min_adjusted_close,
      max(adj_close) AS max_adjusted_close,
      count(DISTINCT run_id) AS distinct_source_runs,
      count(DISTINCT fetched_at) AS distinct_fetch_times,
      any_value(currency) AS currency,
      any_value(source) AS source_vendor,
      'PENDING_QUOTE_CONVENTION_AND_SOURCE_RECONCILIATION'::VARCHAR
        AS review_state,
      FALSE AS resolved_to_trusted_original_quote,
      FALSE AS production_use_approved
    FROM {P}security_prices
    GROUP BY ticker,date
    HAVING count(*)>1
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_beta_audit_inputs AS
    SELECT a.ticker,a.observed_date,a.return_bps,
      b.return_bps AS spy_return_bps,
      f.factor_id,f.shock_bps,a.large_absolute_log_return
    FROM {P}lab_security_returns_retro_v1 a
    JOIN {P}lab_security_returns_retro_v1 b
       ON b.ticker='SPY' AND b.observed_date=a.observed_date
    JOIN {P}lab_rate_shocks_retro_v1 f
       ON f.observed_date=a.observed_date
    WHERE a.ticker IN (
      SELECT DISTINCT ticker FROM tmp_price_exceptions
    )
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_model_reference AS
    SELECT ticker,factor_id,beta_rate,rate_bh_fdr_q,
      test_r2_vs_spy_only,large_return_observations
    FROM {P}lab_security_rate_betas_retro_v1
    WHERE ticker IN (SELECT DISTINCT ticker FROM tmp_price_exceptions)
    """)


def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("Internal-only scope and full source SHA required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect(f"md:{DB}?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_security_price_exception_cases_v1(
          build_id VARCHAR NOT NULL,
          ticker VARCHAR NOT NULL,observed_date DATE NOT NULL,
          previous_observed_date DATE NOT NULL,
          previous_adjusted_close DOUBLE NOT NULL,
          adjusted_close DOUBLE NOT NULL,
          log_return_bps DOUBLE NOT NULL,
          source_unadjusted_close DOUBLE,
          source_adjusted_close DOUBLE,
          source_volume DOUBLE,source_currency VARCHAR,
          source_vendor VARCHAR,source_retrieved_at TIMESTAMPTZ,
          source_run_id VARCHAR,
          other_symbols_same_move_day BIGINT NOT NULL,
          exception_category VARCHAR NOT NULL,
          review_state VARCHAR NOT NULL,
          original_price_quote_time_verified BOOLEAN NOT NULL,
          adjustment_vintage_verified BOOLEAN NOT NULL,
          external_data_rights_approved BOOLEAN NOT NULL,
          eligible_for_production_release BOOLEAN NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_security_duplicate_quote_cases_v1(
          build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
          observed_date DATE NOT NULL,
          source_records BIGINT NOT NULL,
          min_adjusted_close DOUBLE,max_adjusted_close DOUBLE,
          distinct_source_runs BIGINT NOT NULL,
          distinct_fetch_times BIGINT NOT NULL,
          source_currency VARCHAR,source_vendor VARCHAR,
          review_state VARCHAR NOT NULL,
          resolved_to_trusted_original_quote BOOLEAN NOT NULL,
          production_use_approved BOOLEAN NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_beta_price_exception_sensitivity_v1(
          build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
          factor_id VARCHAR NOT NULL,
          original_beta_rate DOUBLE,
          baseline_recomputed_beta_rate DOUBLE,
          without_flagged_days_beta_rate DOUBLE,
          absolute_delta_beta DOUBLE,
          relative_delta_beta DOUBLE,
          original_train_n BIGINT,
          research_exclusion_train_n BIGINT,
          flagged_joint_observations BIGINT,
          original_q_value DOUBLE,
          original_holdout_r2 DOUBLE,
          sensitivity_state VARCHAR NOT NULL,
          source_pit_verified BOOLEAN NOT NULL,
          production_beta_release BOOLEAN NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_security_price_exception_builds_v1(
          build_id VARCHAR NOT NULL,
          git_sha VARCHAR NOT NULL,source_script_sha256 VARCHAR NOT NULL,
          built_at TIMESTAMPTZ NOT NULL,
          source_exception_rows BIGINT NOT NULL,
          duplicated_security_date_keys BIGINT NOT NULL,
          beta_sensitivity_models BIGINT NOT NULL,
          models_with_beta_shift_ge_20pct BIGINT NOT NULL,
          source_reconciled_exceptions BIGINT NOT NULL,
          research_use_only BOOLEAN NOT NULL
        )""")
        stage(con)
        n_exc=con.execute("SELECT count(*) FROM tmp_price_exceptions").fetchone()[0]
        n_dup=con.execute("SELECT count(*) FROM tmp_duplicate_prices").fetchone()[0]
        references={
          (ticker,factor):(slope,q,oos,nflag)
          for ticker,factor,slope,q,oos,nflag in con.execute(
              "SELECT * FROM tmp_model_reference"
          ).fetchall()
        }
        groups=defaultdict(list)
        for ticker,day,ret,market,factor,shock,flag in con.execute(
            "SELECT * FROM tmp_beta_audit_inputs "
            "ORDER BY ticker,factor_id,observed_date"
        ).fetchall():
            if all(z is not None and math.isfinite(z) for z in (ret,market,shock)):
                groups[(ticker,factor)].append(
                    (ticker,day,float(ret),float(market),float(shock),bool(flag))
                )
        diagnostic_rows=[]
        for pair,rows in sorted(groups.items()):
            if pair not in references:continue
            ticker,factor=pair
            ref_beta,q,oos,ref_flags=references[pair]
            total_flags=sum(int(z[-1]) for z in rows)
            if total_flags==0:continue
            base=fit_regression(rows)
            filtered=fit_regression([r for r in rows if not r[-1]])
            if base is None or filtered is None:continue
            delta=filtered["slope"]-base["slope"]
            relative=abs(delta)/max(abs(base["slope"]),0.1)
            diagnostic_rows.append((
                build,ticker,factor,ref_beta,base["slope"],
                filtered["slope"],abs(delta),relative,
                base["train"],filtered["train"],total_flags,q,oos,
                "OUTLIER_EXCLUSION_SENSITIVITY_ONLY_NOT_VALIDATION",
                False,False
            ))
        strong=sum(z[7]>=0.2 for z in diagnostic_rows)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""
            INSERT INTO {P}lab_security_price_exception_cases_v1
            SELECT ?,* FROM tmp_price_exceptions
            """,[build])
            con.execute(f"""
            INSERT INTO {P}lab_security_duplicate_quote_cases_v1
            SELECT ?,* FROM tmp_duplicate_prices
            """,[build])
            if diagnostic_rows:
                placeholders=",".join(["?"]*16)
                con.executemany(
                    f"INSERT INTO {P}lab_beta_price_exception_sensitivity_v1 "
                    f"VALUES ({placeholders})",diagnostic_rows
                )
            con.execute(f"""
            INSERT INTO {P}lab_security_price_exception_builds_v1
            VALUES (?,?,?,current_timestamp,?,?,?,?,0,TRUE)
            """,[build,commit,digest,n_exc,n_dup,len(diagnostic_rows),strong])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build)
        print(f"PRICE_EXCEPTION_CASES={n_exc}")
        print(f"DUPLICATE_PRICE_DATE_KEYS={n_dup}")
        print(f"AFFECTED_BETA_MODELS_TESTED={len(diagnostic_rows)}")
        print(f"BETA_SHIFT_OVER_20PCT_RELATIVE_TO_ORIGINAL={strong}")
        print("VERIFIED_CORPORATE_ACTIONS=0")
        print("PRODUCTION_BETAS_APPROVED=FALSE")
    finally:
        con.close()


if __name__=="__main__":
    main()
