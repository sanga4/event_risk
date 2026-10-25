#!/usr/bin/env python3
"""Source-UNVERIFIED close/adjusted-close reconciliation audit.

Detect vendor adjustment-ratio changes without declaring issuer split,
dividend, exchange halt or vendor error. The mathematical identity:
log(adj_t/adj_prev)-log(close_t/close_prev) =
log[(adj_t/close_t)/(adj_prev/close_prev)].
Original security and corporate-action vintages, raw quote timestamps,
rights, issuer permanent identifiers and historical reconstitution absent.
No original prices changed or exceptions automatically closed.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib,os
import duckdb

P="eventrisk_factor_lab.main."
VERSION="phase1-security-adjustment-source-audit-v1.0.0"
RATIO_STEP_BPS=50.
MATERIAL_STEP_BPS=200.


def stage(con):
    # Exclude conflicting vendor ticker/date rows altogether; never
    # "choose" one duplicate FX quote or create phantom adjustment evidence.
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE p1_adjust_inputs AS
      WITH grouped AS (
       SELECT ticker,date,COUNT(*) n_key,
         COUNT(DISTINCT run_id) n_runs,
         MIN(close) min_close,MAX(close) max_close,
         MIN(adj_close) min_adj,MAX(adj_close) max_adj
       FROM {P}security_prices GROUP BY ticker,date
      ), originals AS (
       SELECT p.*,ROW_NUMBER() OVER(PARTITION BY p.ticker,p.date
          ORDER BY p.fetched_at DESC,p.run_id DESC) rn
       FROM {P}security_prices p
       JOIN grouped g ON g.ticker=p.ticker AND g.date=p.date
       WHERE g.n_key=1
         AND p.close>0 AND p.adj_close>0
         AND isfinite(p.close) AND isfinite(p.adj_close)
      )
      SELECT ticker,date,close,adj_close,volume,currency,source,
        fetched_at,run_id,ln(adj_close/close)*10000 AS adjustment_log_bps
      FROM originals WHERE rn=1
    """)
    con.execute("""
      CREATE OR REPLACE TEMP TABLE p1_adj_diffs AS
      WITH prev AS (
       SELECT *,
         LAG(date) OVER(PARTITION BY ticker ORDER BY date) prev_date,
         LAG(close) OVER(PARTITION BY ticker ORDER BY date) prev_close,
         LAG(adj_close) OVER(PARTITION BY ticker ORDER BY date) prev_adj_close,
         LAG(adjustment_log_bps) OVER(PARTITION BY ticker ORDER BY date) prev_adj_log
       FROM p1_adjust_inputs
      )
      SELECT *,
        10000*LN(close/prev_close) raw_close_return_bps,
        10000*LN(adj_close/prev_adj_close) adjusted_close_return_bps,
        adjustment_log_bps-prev_adj_log ratio_step_bps,
        CAST(date_diff('day',prev_date,date) AS INT) calendar_gap_days
      FROM prev
      WHERE prev_close>0 AND prev_adj_close>0
        AND date_diff('day',prev_date,date) BETWEEN 1 AND 14
    """)


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Internal-only and immutable source SHA required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_security_adjustment_ratio_changes_v1(
           build_id VARCHAR NOT NULL,candidate_id VARCHAR NOT NULL,
           ticker VARCHAR NOT NULL,observed_date DATE NOT NULL,
           previous_observed_date DATE NOT NULL,
           original_vendor_close DOUBLE NOT NULL,
           prior_vendor_close DOUBLE NOT NULL,
           original_vendor_adjusted_close DOUBLE NOT NULL,
           prior_vendor_adjusted_close DOUBLE NOT NULL,
           close_to_adjusted_ratio DOUBLE NOT NULL,
           log_adjustment_ratio_step_bps DOUBLE NOT NULL,
           raw_close_return_bps DOUBLE NOT NULL,
           adjusted_close_return_bps DOUBLE NOT NULL,
           return_difference_identity_residual_bps DOUBLE NOT NULL,
           source_vendor VARCHAR,source_currency VARCHAR,
           source_fetched_at TIMESTAMPTZ,
           source_run_id VARCHAR,
           large_ratio_step_requires_source_review BOOLEAN NOT NULL,
           original_issuer_action_verified BOOLEAN NOT NULL,
           original_vendor_revision_asof_verified BOOLEAN NOT NULL,
           external_data_rights_approved BOOLEAN NOT NULL,
           approved_for_institutional_beta BOOLEAN NOT NULL,
           candidate_label VARCHAR NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_security_exception_adjustment_joins_v1(
           build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
           observed_date DATE NOT NULL,
           outlier_adjusted_log_return_bps DOUBLE NOT NULL,
           vendor_unadjusted_day_close DOUBLE,
           vendor_adjusted_day_close DOUBLE,
           same_day_adjustment_step_bps DOUBLE,
           same_day_unadjusted_return_bps DOUBLE,
           mathematically_adjustment_step_explains_return_difference BOOLEAN NOT NULL,
           original_vendor_quote_time_verified BOOLEAN NOT NULL,
           issuer_corporate_action_original_evidence_verified BOOLEAN NOT NULL,
           problem_cause_unambiguously_identified BOOLEAN NOT NULL,
           reviewer_or_approver_decision VARCHAR
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_security_adjustment_audit_builds_v1(
           build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
           script_sha256 VARCHAR NOT NULL,created_at TIMESTAMPTZ NOT NULL,
           valid_unique_source_price_rows BIGINT NOT NULL,
           duplicate_security_date_groups_excluded BIGINT NOT NULL,
           ticker_series_covered BIGINT NOT NULL,
           price_ratio_step_candidates BIGINT NOT NULL,
           material_adjustment_ratio_candidates BIGINT NOT NULL,
           flagged_price_exception_joined BIGINT NOT NULL,
           exception_cases_with_material_adjustment_step BIGINT NOT NULL,
           max_abs_return_identity_residual_bps DOUBLE NOT NULL,
           independently_verified_issuer_actions BIGINT NOT NULL,
           approved_security_adjustment_vintages BIGINT NOT NULL,
           model_release_authorized BOOLEAN NOT NULL,
           release_state VARCHAR NOT NULL
        )""")
        stage(con)
        ninputs,ntickers=con.execute(
            "SELECT COUNT(*),COUNT(DISTINCT ticker) FROM p1_adjust_inputs"
        ).fetchone()
        ndups=con.execute(f"""
        SELECT COUNT(*) FROM (SELECT ticker,date FROM {P}security_prices
          GROUP BY ticker,date HAVING COUNT(*)>1) d
        """).fetchone()[0]
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE p1_candidates AS
        SELECT ?,sha256(ticker||':'||CAST(date AS VARCHAR)||':'||run_id),
          ticker,date,prev_date,close,prev_close,adj_close,prev_adj_close,
          adj_close/close,ratio_step_bps,raw_close_return_bps,
          adjusted_close_return_bps,
          adjusted_close_return_bps-raw_close_return_bps-ratio_step_bps,
          source,currency,fetched_at,run_id,
          ABS(ratio_step_bps)>=?,FALSE,FALSE,FALSE,FALSE,
          'PROVIDER_ADJUSTMENT_RATIO_DISCONTINUITY_NOT_VERIFIED_ACTION'
        FROM p1_adj_diffs
        WHERE ABS(ratio_step_bps)>=?
        """,[build,MATERIAL_STEP_BPS,RATIO_STEP_BPS])
        candidates,material,residual=con.execute("""
           SELECT COUNT(*),
             COUNT(*) FILTER(WHERE column19),
             COALESCE(MAX(ABS(column14)),0)
           FROM p1_candidates
        """).fetchone()
        if ninputs<50000 or ntickers<50:
            raise RuntimeError("Source price history unexpectedly small")
        if residual>1e-6:
            raise RuntimeError("Close/adjusted-close identity did not reconcile")
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE p1_cases_linked AS
        SELECT ?,e.ticker,e.observed_date,e.log_return_bps,
          e.source_unadjusted_close,e.source_adjusted_close,
          p.ratio_step_bps,p.raw_close_return_bps,
          CASE WHEN p.ratio_step_bps IS NOT NULL AND
             ABS((p.adjusted_close_return_bps-p.raw_close_return_bps)-
                  p.ratio_step_bps)<0.000001
          THEN TRUE ELSE FALSE END,
          FALSE,FALSE,FALSE,NULL
        FROM {P}lab_security_price_exception_cases_v1 e
        LEFT JOIN p1_adj_diffs p
          ON p.ticker=e.ticker AND p.date=e.observed_date
        WHERE e.build_id=(SELECT build_id FROM
          {P}lab_security_price_exception_builds_v1
          ORDER BY built_at DESC LIMIT 1)
        """,[build])
        ncases,material_in_cases=con.execute("""
           SELECT COUNT(*),COUNT(*) FILTER(WHERE ABS(column7)>=?)
           FROM p1_cases_linked
        """,[MATERIAL_STEP_BPS]).fetchone()
        if ncases!=12:
            raise RuntimeError("Expected 12 existing abnormal returns")
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"INSERT INTO {P}lab_security_adjustment_ratio_changes_v1 SELECT * FROM p1_candidates")
            con.execute(f"INSERT INTO {P}lab_security_exception_adjustment_joins_v1 SELECT * FROM p1_cases_linked")
            con.execute(f"""
            INSERT INTO {P}lab_security_adjustment_audit_builds_v1
            VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,0,0,FALSE,
              'SOURCE_VENDOR_ADJUSTMENT_FACTOR_RESEARCH_NOT_VERIFIED_CORPORATE_ACTION')
            """,[build,sha,digest,ninputs,ndups,ntickers,
                candidates,material,ncases,material_in_cases,residual])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build} UNIQUE_SOURCE_PRICES={ninputs} SYMBOLS={ntickers}")
        print(f"DUPLICATE_SOURCE_DATE_GROUPS_EXCLUDED={ndups}")
        print(f"RATIO_STEP_CANDIDATES_GE_50BP={candidates} MATERIAL_GE_200BP={material}")
        print(f"LARGE_RETURN_CASES_RECONCILED={ncases} SAME_DAY_MATERIAL_STEPS={material_in_cases}")
        print(f"MAX_LOG_RETURN_ADJUSTMENT_IDENTITY_ERROR_BPS={residual:.10f}")
        print("CORPORATE_ACTION_SOURCE_VERIFIED=0 INSTITUTIONAL_RELEASE=FALSE")
    finally:
        con.close()

if __name__=="__main__":
    main()
