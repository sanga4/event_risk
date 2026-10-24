#!/usr/bin/env python3
"""Factor units, source license/provenance status and collinearity diagnostics.

Only existing retrospective Treasury yield shocks are used. No factor scores,
beta approvals, causal event links, forecasts or source backfills are invented.
"""
import hashlib
import os
from datetime import datetime,timezone
from pathlib import Path

import duckdb

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-factor-risk-diagnostics-v1.0.0"

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("Require internal research scope and immutable full Git SHA")
    code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect(f"md:{DB}?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_factor_exposure_specifications_v1(
          build_id VARCHAR NOT NULL,factor_id VARCHAR NOT NULL,
          name VARCHAR NOT NULL,factor_family VARCHAR NOT NULL,
          level_unit VARCHAR NOT NULL,provider VARCHAR NOT NULL,
          provider_series VARCHAR NOT NULL,license_class VARCHAR NOT NULL,
          active BOOLEAN NOT NULL,observations BIGINT NOT NULL,
          observed_date_min DATE,observed_date_max DATE,
          shock_transform VARCHAR NOT NULL,shock_unit VARCHAR NOT NULL,
          independence_assumption VARCHAR NOT NULL,
          independently_verified_source_vintage BOOLEAN NOT NULL,
          eligible_for_independent_production_model BOOLEAN NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_factor_collinearity_pairs_v1(
          build_id VARCHAR NOT NULL,
          factor_a VARCHAR NOT NULL,factor_b VARCHAR NOT NULL,
          factor_a_family VARCHAR NOT NULL,factor_b_family VARCHAR NOT NULL,
          matched_dates BIGINT NOT NULL,observed_date_min DATE,
          observed_date_max DATE,
          pearson_daily_shock_corr DOUBLE,
          abs_corr_gt_095 BOOLEAN NOT NULL,
          derived_identity_component_risk BOOLEAN NOT NULL,
          inference_status VARCHAR NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_factor_diagnostics_builds_v1(
          build_id VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
          source_git_sha VARCHAR NOT NULL,source_sha256 VARCHAR NOT NULL,
          factor_definitions BIGINT NOT NULL,eligible_shock_series BIGINT NOT NULL,
          pairwise_factor_tests BIGINT NOT NULL,strong_corr_pairs BIGINT NOT NULL,
          derived_component_overlap_pairs BIGINT NOT NULL,
          source_vintage_certified_series BIGINT NOT NULL,
          model_risk_approved BOOLEAN NOT NULL,
          release_state VARCHAR NOT NULL
        )""")
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE p1_specs AS
        SELECT c.factor_id,c.name,c.family,c.unit,c.provider,
          c.provider_series,c.license_class,c.active,
          count(f.factor_id) AS observations,
          min(f.observed_date) AS observed_date_min,
          max(f.observed_date) AS observed_date_max,
          CASE WHEN c.unit='percent' THEN '100*(level_t-level_previous_valid_business_date)'
               WHEN c.unit='bps' THEN 'level_t-level_previous_valid_business_date'
               WHEN c.unit='index' THEN 'DIFFERENCE_WITH_EXPLICIT_HORIZON_REQUIRED'
               ELSE 'NOT_SPECIFIED' END AS shock_transform,
          CASE WHEN c.unit='percent' THEN 'yield_basis_points'
               WHEN c.unit='bps' THEN 'spread_basis_points'
               ELSE 'native_unit_pending_review' END AS shock_unit,
          CASE WHEN c.family='inflation_proxy' THEN
            'NOMINAL_MINUS_REAL_PAR_YIELD_PROXY_IS_ALGEBRAICALLY_DERIVED_NOT_TRUE_BREAKEVEN'
            ELSE 'COVARIANCE_AND_SHARED_RISK_DRIVER_REVIEW_REQUIRED' END AS independence_assumption,
          FALSE AS independently_verified_source_vintage,
          FALSE AS eligible_for_independent_production_model
        FROM {P}lab_factor_catalog c
        LEFT JOIN {P}lab_factor_observations f USING(factor_id)
        GROUP BY c.factor_id,c.name,c.family,c.unit,c.provider,
                 c.provider_series,c.license_class,c.active
        """)
        con.execute(f"""
        CREATE OR REPLACE TEMP TABLE p1_factor_pairwise AS
        WITH factor AS (
          SELECT factor_id,observed_date,shock_bps
          FROM {P}lab_rate_shocks_retro_v1
          WHERE shock_bps IS NOT NULL AND isfinite(shock_bps)
        ), joined AS (
          SELECT a.factor_id AS factor_a,b.factor_id AS factor_b,
            a.observed_date,a.shock_bps AS a_shock,b.shock_bps AS b_shock
          FROM factor a JOIN factor b
          ON a.observed_date=b.observed_date AND a.factor_id<b.factor_id
        )
        SELECT
          j.factor_a,j.factor_b,sa.factor_family AS factor_a_family,
          sb.factor_family AS factor_b_family,
          count(*) AS matched_dates,
          min(j.observed_date) AS observed_date_min,
          max(j.observed_date) AS observed_date_max,
          corr(a_shock,b_shock) AS pearson_daily_shock_corr,
          abs(corr(a_shock,b_shock))>=.95 AS abs_corr_gt_095,
          (sa.factor_family='inflation_proxy' OR sb.factor_family='inflation_proxy')
             AS derived_identity_component_risk,
          'RETROSPECTIVE_ASSOCIATION_AND_MULTIFACTOR_RANK_REVIEW_REQUIRED'
            AS inference_status
        FROM joined j
        JOIN (SELECT factor_id,family AS factor_family FROM p1_specs) sa
          ON sa.factor_id=j.factor_a
        JOIN (SELECT factor_id,family AS factor_family FROM p1_specs) sb
          ON sb.factor_id=j.factor_b
        GROUP BY j.factor_a,j.factor_b,sa.factor_family,sb.factor_family
        HAVING count(*)>=250
          AND corr(a_shock,b_shock) IS NOT NULL
          AND isfinite(corr(a_shock,b_shock))
        """)
        counts=con.execute("""
        SELECT
         (SELECT count(*) FROM p1_specs),
         (SELECT count(*) FROM p1_specs WHERE observations>0 AND unit='percent'),
         (SELECT count(*) FROM p1_factor_pairwise),
         (SELECT count(*) FROM p1_factor_pairwise WHERE abs_corr_gt_095),
         (SELECT count(*) FROM p1_factor_pairwise WHERE derived_identity_component_risk)
        """).fetchone()
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""
              INSERT INTO {P}lab_factor_exposure_specifications_v1
              SELECT ?,* FROM p1_specs
            """,[build])
            con.execute(f"""
              INSERT INTO {P}lab_factor_collinearity_pairs_v1
              SELECT ?,* FROM p1_factor_pairwise
            """,[build])
            con.execute(f"""
              INSERT INTO {P}lab_factor_diagnostics_builds_v1
              VALUES (?,current_timestamp,?,?,?,?,?,?,?,0,FALSE,
                      'RESEARCH_ONLY_COLLINEARITY_AND_VINTAGE_REVIEW_REQUIRED')
            """,[build,sha,code_sha,*counts])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build}")
        print(f"CATALOG_SERIES={counts[0]} RATE_SHOCK_SERIES={counts[1]}")
        print(f"PAIRWISE_CORRELATIONS={counts[2]} HIGH_ABS_CORR_GE_0_95={counts[3]}")
        print(f"PROXY_COMPONENT_RISK_PAIRS={counts[4]}")
        print("SOURCE_VINTAGE_CERTIFIED=0; PRODUCTION_FACTOR_MODEL=BLOCKED")
    finally:
        con.close()


if __name__=="__main__":
    main()
