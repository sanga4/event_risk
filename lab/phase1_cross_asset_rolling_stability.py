#!/usr/bin/env python3
"""Rolling seven-factor covariance stability and source-coverage ledger.

Research-only. Same-date intersection: Treasury nominal curve shocks,
ECB quote-per-EUR rate changes and French US daily simple factor returns.
Fit 252-day windows, compare disjoint forward 63 days, shift 21 days.
Every mean, standard deviation and fixed 10% covariance diagonal shrinkage
is learned from prior window ONLY. No evidence of original source PIT/license,
no valid portfolio P&L or executable FX observations.
"""
from __future__ import annotations
import hashlib
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import duckdb
import numpy as np

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-rolling-cross-asset-risk-v1.0.0"
FACTORS=("TREASURY_LEVEL","TREASURY_SLOPE","TREASURY_CURVATURE",
         "ECB_EUR_USD","ECB_EUR_JPY","FF_MKT_RF","FF_MOM")
TRAIN=252
TEST=63
STEP=21
SHRINK=.10
ALERT_DRIFT=.50
ALERT_VARIANCE=2.0


def validate_and_compute(m):
    m=np.asarray(m,dtype=float)
    if m.shape != (TRAIN+TEST,len(FACTORS)) or not np.isfinite(m).all():
        raise ValueError("Expected complete finite 315×7 window")
    x=m[:TRAIN]
    y=m[TRAIN:]
    center=np.mean(x,axis=0)
    scale=np.std(x,axis=0,ddof=1)
    if (not np.isfinite(scale).all()) or np.any(scale<=1.e-9):
        raise ValueError("Zero variance factor")
    normalized=(x-center)/scale
    scov=np.cov(normalized,rowvar=False,ddof=1)
    target=np.diag(np.diag(scov))
    shrunk=(1-SHRINK)*scov+SHRINK*target
    eig=np.linalg.eigvalsh(shrunk)
    if min(eig)<=1e-9:raise ValueError("Nonpositive training covariance")
    testcov=np.cov((y-center)/scale,rowvar=False,ddof=1)
    distance=float(np.linalg.norm(testcov-shrunk,ord="fro")/
                   np.linalg.norm(shrunk,ord="fro"))
    ratios=np.diag(testcov)/np.diag(shrunk)
    if np.any(ratios<=1.e-12):raise ValueError("Zero heldout variance")
    maxvar=float(max(max(ratios),max(1/ratios)))
    return {
        "drift":distance,
        "max_var":maxvar,
        "min_eig":float(min(eig)),
        "condition":float(max(eig)/min(eig)),
        "largest_cross_corr":float(
            np.max(np.abs(scov-np.diag(np.diag(scov))))
        ),
        "needs_review":distance>ALERT_DRIFT or maxvar>ALERT_VARIANCE,
    }


def build_stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_roll_source AS
    WITH curve AS (
      SELECT observed_date,level_shock_bps l,slope_shock_bps s,curvature_shock_bps c
      FROM {P}lab_curve_factor_retro_v1
      WHERE build_id=(SELECT build_id FROM {P}lab_security_curve_builds_retro_v1
        ORDER BY created_at DESC LIMIT 1)
    ), fx AS (
      SELECT observed_date,
        MAX(quote_per_eur_log_change_bps) FILTER(WHERE quote_currency='USD') usd,
        MAX(quote_per_eur_log_change_bps) FILTER(WHERE quote_currency='JPY') jpy
      FROM {P}lab_fx_returns_retro_v1
      WHERE build_id=(SELECT build_id FROM {P}lab_fx_backfill_builds_v1
         ORDER BY built_at DESC LIMIT 1)
      GROUP BY 1
      HAVING COUNT(DISTINCT quote_currency) FILTER(WHERE quote_currency IN ('USD','JPY'))=2
    ), ff AS (
      SELECT observed_date,
        MAX(factor_return) FILTER(WHERE factor_id='FF_US_MKT_RF')*10000 market,
        MAX(factor_return) FILTER(WHERE factor_id='FF_US_MOM')*10000 momentum
      FROM (
        SELECT observed_date,factor_id,factor_return,
          ROW_NUMBER() OVER(PARTITION BY observed_date,factor_id
            ORDER BY downloaded_at DESC,source_zip_sha256 DESC) rn
        FROM {P}lab_style_factor_returns_v1
        WHERE factor_id IN ('FF_US_MKT_RF','FF_US_MOM')
          AND research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED'
      ) ver
      WHERE rn=1
      GROUP BY observed_date
      HAVING COUNT(DISTINCT factor_id)=2
    )
    SELECT curve.observed_date, l,s,c,fx.usd,fx.jpy,ff.market,ff.momentum
    FROM curve JOIN fx USING(observed_date)
    JOIN ff USING(observed_date)
    WHERE isfinite(l) AND isfinite(s) AND isfinite(c)
      AND isfinite(fx.usd) AND isfinite(fx.jpy)
      AND isfinite(ff.market) AND isfinite(ff.momentum)
    ORDER BY observed_date
    """)


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(x not in "0123456789abcdef" for x in sha):
        raise RuntimeError("Immutable Git SHA and internal-only research scope required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
          CREATE TABLE IF NOT EXISTS {P}lab_cross_asset_rolling_windows_v1 (
          build_id VARCHAR NOT NULL, window_number BIGINT NOT NULL,
          training_start DATE NOT NULL,training_end DATE NOT NULL,
          holdout_start DATE NOT NULL,holdout_end DATE NOT NULL,
          training_observations BIGINT NOT NULL,holdout_observations BIGINT NOT NULL,
          covariance_shrinkage DOUBLE NOT NULL,
          relative_holdout_covariance_drift DOUBLE NOT NULL,
          largest_holdout_variance_ratio DOUBLE NOT NULL,
          min_training_eigenvalue DOUBLE NOT NULL,
          training_condition_number DOUBLE NOT NULL,
          largest_training_cross_correlation DOUBLE NOT NULL,
          requires_independent_regime_review BOOLEAN NOT NULL,
          source_pit_independently_verified BOOLEAN NOT NULL,
          licensed_for_portfolio_risk BOOLEAN NOT NULL,
          risk_model_approved BOOLEAN NOT NULL)
        """)
        con.execute(f"""
          CREATE TABLE IF NOT EXISTS {P}lab_cross_asset_rolling_builds_v1 (
            build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
            code_sha256 VARCHAR NOT NULL,created_at TIMESTAMPTZ NOT NULL,
            source_joint_days BIGINT NOT NULL,
            seven_factors BIGINT NOT NULL,
            rolling_train_days BIGINT NOT NULL,forward_test_days BIGINT NOT NULL,
            step_days BIGINT NOT NULL,n_windows BIGINT NOT NULL,
            windows_flagged_regime_review BIGINT NOT NULL,
            median_covariance_relative_drift DOUBLE NOT NULL,
            p90_covariance_relative_drift DOUBLE NOT NULL,
            max_covariance_relative_drift DOUBLE NOT NULL,
            max_variance_ratio DOUBLE NOT NULL,
            original_source_publication_certified BOOLEAN NOT NULL,
            institutional_risk_release BOOLEAN NOT NULL,
            release_state VARCHAR NOT NULL)
        """)
        build_stage(con)
        rows=con.execute("SELECT * FROM p1_roll_source ORDER BY observed_date").fetchall()
        if len(rows)<560:raise RuntimeError("Not enough matched dates for rolling risk validation")
        arr=np.asarray([r[1:] for r in rows],dtype=float)
        windows=[]
        for start in range(0,len(rows)-TRAIN-TEST+1,STEP):
            end=start+TRAIN+TEST
            z=validate_and_compute(arr[start:end])
            windows.append((
                build,len(windows)+1,rows[start][0],
                rows[start+TRAIN-1][0],rows[start+TRAIN][0],
                rows[end-1][0],TRAIN,TEST,SHRINK,
                z["drift"],z["max_var"],z["min_eig"],z["condition"],
                z["largest_cross_corr"],z["needs_review"],False,False,False
            ))
        if len(windows)<10:raise RuntimeError("Insufficient rolling windows")
        drifts=np.asarray([w[9] for w in windows],dtype=float)
        flagged=sum(bool(w[14]) for w in windows)
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(
              f"INSERT INTO {P}lab_cross_asset_rolling_windows_v1 VALUES ({','.join(['?']*18)})",windows)
            con.execute(f"""
              INSERT INTO {P}lab_cross_asset_rolling_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,?,FALSE,FALSE,
                      'ROLLING_RESEARCH_ONLY_REGIME_AND_SOURCE_PIT_REVIEW_REQUIRED')
            """,[build,sha,digest,len(rows),len(FACTORS),TRAIN,TEST,STEP,
                 len(windows),flagged,float(np.median(drifts)),
                 float(np.quantile(drifts,.90)),float(max(drifts)),
                 float(max(w[10] for w in windows))])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build} MATCHED_DAYS={len(rows)} ROLLING_WINDOWS={len(windows)}")
        print(f"WINDOWS_REQUIRING_REGIME_REVIEW={flagged}")
        print(f"MEDIAN_RELATIVE_HOLDOUT_COVARIANCE_DRIFT={np.median(drifts):.4f}")
        print(f"P90_RELATIVE_HOLDOUT_COVARIANCE_DRIFT={np.quantile(drifts,.90):.4f}")
        print(f"MAX_RELATIVE_HOLDOUT_COVARIANCE_DRIFT={max(drifts):.4f}")
        print("SOURCE_PIT_VERIFIED=FALSE PRODUCTION_RISK_APPROVED=FALSE")
    finally:
        con.close()


if __name__=="__main__":
    main()
