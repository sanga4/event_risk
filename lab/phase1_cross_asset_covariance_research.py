#!/usr/bin/env python3
"""Cross-asset factor risk-research covariance diagnostic, NOT a risk engine.

Date-intersection of EUR-quoted reference FX log changes, three nominal
Treasury par-yield curve components and two US FF portfolio simple returns.
Basis-point units are different kinds of shocks/returns; covariance computed
only AFTER training-window centering/scaling, never on mixed raw units.
No PIT provenance, original releases, legally distributable input or
risk portfolio scenario is certified. No prediction or real holdings.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import math
import os
import duckdb
import numpy as np

P="eventrisk_factor_lab.main."
VERSION="phase1-cross-asset-risk-matrix-v1.0.0"
IDS=("CURVE_LEVEL_BPS","CURVE_SLOPE_BPS","CURVE_CURVATURE_BPS",
     "ECB_EUR_USD_QUOTE_BPS","ECB_EUR_JPY_QUOTE_BPS",
     "FF_US_MKT_RF_RETURN_BPS","FF_US_MOM_RETURN_BPS")
UNITS=("yield_delta_bp","yield_delta_bp","yield_delta_bp",
       "quote_per_eur_log_delta_bp","quote_per_eur_log_delta_bp",
       "daily_simple_factor_return_bp","daily_simple_factor_return_bp")
SHRINK=0.10
MIN_OBSERVATIONS=360


def covariance_estimator(matrix,shrink=SHRINK):
    """Training-only sample standardization + fixed diagonal target shrinkage."""
    m=np.asarray(matrix,dtype=float)
    if m.ndim!=2 or m.shape[0]<MIN_OBSERVATIONS or m.shape[1]!=len(IDS):
        raise ValueError("Insufficient complete 7-factor training coverage")
    if not np.isfinite(m).all():raise ValueError("Nonfinite source inputs")
    mu=np.mean(m,axis=0)
    sd=np.std(m,axis=0,ddof=1)
    if np.any(sd<=1.e-10):raise ValueError("Zero-variation cross-asset factor")
    z=(m-mu)/sd
    cov=np.cov(z,rowvar=False,ddof=1)
    if not np.all(np.isfinite(cov)):raise ValueError("Nonfinite covariance")
    shrinked=(1-shrink)*cov+shrink*np.diag(np.diag(cov))
    eig=np.linalg.eigvalsh(shrinked)
    if not np.isfinite(eig).all() or eig.min()<=1e-8:
        raise ValueError("Non-positive shrinkage covariance")
    return mu,sd,cov,shrinked,float(eig.min()),float(eig.max()/eig.min())


def setup(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_cross_asset_factor_covariance_v1 (
       build_id VARCHAR NOT NULL,factor_a VARCHAR NOT NULL,
       factor_b VARCHAR NOT NULL,source_unit_a VARCHAR NOT NULL,
       source_unit_b VARCHAR NOT NULL,
       standardized_train_sample_covariance DOUBLE NOT NULL,
       fixed_diag_shrunk_train_covariance DOUBLE NOT NULL,
       holdout_standardized_sample_covariance DOUBLE NOT NULL,
       train_only_center_a DOUBLE NOT NULL,
       train_only_scale_a DOUBLE NOT NULL,
       train_only_center_b DOUBLE NOT NULL,
       train_only_scale_b DOUBLE NOT NULL,
       source_pit_vintages_certified BOOLEAN NOT NULL,
       provider_rights_approved BOOLEAN NOT NULL,
       approved_portfolio_risk_covariance BOOLEAN NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_cross_asset_risk_diagnostics_v1 (
       build_id VARCHAR NOT NULL,
       git_sha VARCHAR NOT NULL,script_sha256 VARCHAR NOT NULL,
       built_at TIMESTAMPTZ NOT NULL,
       first_matching_date DATE NOT NULL,last_matching_date DATE NOT NULL,
       training_end DATE NOT NULL,holdout_start DATE NOT NULL,
       n_joint_observations BIGINT NOT NULL,n_train BIGINT NOT NULL,
       n_holdout BIGINT NOT NULL,n_factors BIGINT NOT NULL,
       diagonal_shrinkage DOUBLE NOT NULL,
       min_shrunk_eigenvalue DOUBLE NOT NULL,
       shrunk_condition_number DOUBLE NOT NULL,
       holdout_covariance_relative_frobenius_error DOUBLE NOT NULL,
       max_holdout_univariate_variance_ratio DOUBLE NOT NULL,
       sourced_rights_verified BOOLEAN NOT NULL,
       original_pit_publications_verified BOOLEAN NOT NULL,
       institutional_factor_risk_model_released BOOLEAN NOT NULL,
       release_status VARCHAR NOT NULL
    )""")


def stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_joint_risk_factors AS
    WITH curve AS (
      SELECT observed_date,level_shock_bps AS l,
        slope_shock_bps AS s,curvature_shock_bps AS c
      FROM {P}lab_curve_factor_retro_v1
      WHERE build_id=(SELECT build_id FROM {P}lab_security_curve_builds_retro_v1
                      ORDER BY created_at DESC LIMIT 1)
    ), fx AS (
      SELECT observed_date,
        MAX(quote_per_eur_log_change_bps) FILTER(WHERE quote_currency='USD') AS usd,
        MAX(quote_per_eur_log_change_bps) FILTER(WHERE quote_currency='JPY') AS jpy
      FROM {P}lab_fx_returns_retro_v1
      WHERE build_id=(SELECT build_id FROM {P}lab_fx_backfill_builds_v1
                      ORDER BY built_at DESC LIMIT 1)
      GROUP BY observed_date
      HAVING COUNT(DISTINCT quote_currency) FILTER
        (WHERE quote_currency IN ('USD','JPY'))=2
    ), styles AS (
      SELECT observed_date,
        MAX(factor_return) FILTER(WHERE factor_id='FF_US_MKT_RF')*10000 AS market,
        MAX(factor_return) FILTER(WHERE factor_id='FF_US_MOM')*10000 AS momentum
      FROM (
        SELECT observed_date,factor_id,factor_return,
          ROW_NUMBER() OVER(PARTITION BY observed_date,factor_id
            ORDER BY downloaded_at DESC,source_zip_sha256 DESC) rank_latest
        FROM {P}lab_style_factor_returns_v1
        WHERE factor_id IN ('FF_US_MKT_RF','FF_US_MOM')
          AND research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED'
      ) s
      WHERE rank_latest=1
      GROUP BY observed_date HAVING COUNT(DISTINCT factor_id)=2
    )
    SELECT curve.observed_date,curve.l,curve.s,curve.c,
      fx.usd,fx.jpy,styles.market,styles.momentum
    FROM curve JOIN fx USING(observed_date)
    JOIN styles USING(observed_date)
    WHERE isfinite(curve.l) AND isfinite(curve.s) AND isfinite(curve.c)
      AND isfinite(fx.usd) AND isfinite(fx.jpy)
      AND isfinite(styles.market) AND isfinite(styles.momentum)
    ORDER BY curve.observed_date
    """)


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Internal-only research and immutable full source SHA required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        setup(con)
        stage(con)
        rows=con.execute("SELECT * FROM p1_joint_risk_factors").fetchall()
        n=len(rows)
        train_n=int(n*.7)
        if n<525 or train_n<MIN_OBSERVATIONS or n-train_n<120:
            raise RuntimeError("Insufficient joint FX/Treasury/style calendar rows")
        matrix=np.asarray([r[1:] for r in rows],dtype=float)
        mu,sd,cov,shrunk,min_eig,condition=covariance_estimator(matrix[:train_n])
        test=(matrix[train_n:]-mu)/sd
        test_cov=np.cov(test,rowvar=False,ddof=1)
        fro=float(np.linalg.norm(test_cov-shrunk,ord="fro")/
                  np.linalg.norm(shrunk,ord="fro"))
        ratios=np.diag(test_cov)/np.diag(shrunk)
        max_ratio=float(np.max(np.maximum(ratios,1/ratios)))
        items=[]
        for i,a in enumerate(IDS):
            for j,b in enumerate(IDS):
                items.append((
                   build,a,b,UNITS[i],UNITS[j],
                   float(cov[i,j]),float(shrunk[i,j]),float(test_cov[i,j]),
                   float(mu[i]),float(sd[i]),float(mu[j]),float(sd[j]),
                   False,False,False
                ))
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(
              f"INSERT INTO {P}lab_cross_asset_factor_covariance_v1 "
              f"VALUES ({','.join(['?']*15)})",items)
            con.execute(f"""
              INSERT INTO {P}lab_cross_asset_risk_diagnostics_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,?,?,FALSE,
                FALSE,FALSE,'RETROSPECTIVE_NOT_A_LICENSED_OR_PIT_PORTFOLIO_RISK_MODEL')
            """,[build,sha,digest,rows[0][0],rows[-1][0],rows[train_n-1][0],
                 rows[train_n][0],n,train_n,n-train_n,len(IDS),SHRINK,
                 min_eig,condition,fro,max_ratio])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print("BUILD_ID="+build)
    print(f"EX_POST_JOINT_TRADING_DATES={n} TRAIN={train_n} HOLDOUT={n-train_n}")
    print("CROSS_ASSET_FACTOR_GROUPS=TREASURY_CURVE;EUR_FX_REFERENCES;US_FRENCH_STYLES")
    print(f"FACTOR_COUNT={len(IDS)} MATRIX_CELLS={len(items)}")
    print(f"TRAIN_SHRUNK_COV_MIN_EIG={min_eig:.6f} CONDITION={condition:.3f}")
    print(f"HOLDOUT_COV_FROBENIUS_RELATIVE_ERROR={fro:.4f}")
    print(f"LARGEST_HOLDOUT_VARIANCE_RATIO={max_ratio:.3f}")
    print("RELEASED_INSTITUTIONAL_FACTOR_COVARIANCE=FALSE")
    print("SOURCE_PIT_AND_LICENSE_GOVERNANCE=BLOCKED")


if __name__=="__main__":
    main()
