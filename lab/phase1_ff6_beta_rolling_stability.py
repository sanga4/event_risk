#!/usr/bin/env python3
"""Rolling out-of-window descriptive US FF5+Momentum beta stability.

SECURITY RETURN: Convert observed (retrospective-adjusted) security log return
bps back to daily simple return and subtract same-date French RF.
SIX FACTORS: FF Mkt-RF, SMB,HML,RMW,CMA,Mom, simple daily return bps.
Fitting in rolling 378-observation training windows, next 63 heldout, 63 step.
OLS full multivariate HAC(5) on TRAIN ONLY, training-only condition screen,
market-only holdout comparator. Adjacent beta instability requires review.
All original provider histories, security CA vintages, and rights unverified.
"""
from __future__ import annotations
from datetime import datetime,timezone
from collections import defaultdict
from pathlib import Path
import hashlib,math,os
import duckdb,numpy as np

P="eventrisk_factor_lab.main."
VERSION="phase1-style-beta-rolling-audit-v1.0.0"
FACTORS=("FF_US_MKT_RF","FF_US_SMB","FF_US_HML",
         "FF_US_RMW","FF_US_CMA","FF_US_MOM")
TRAIN=378
TEST=63
STEP=63
HAC=5
MAX_CONDITION=1000
BETA_CHANGE_THRESHOLD=.5
ERROR_RATIO_THRESHOLD=1.25

def train_window(rows):
    n=len(rows)
    if n!=TRAIN+TEST:raise ValueError("Missing complete sample")
    a=np.asarray([z[1:8] for z in rows],dtype=float)
    if a.shape!=(n,7) or not np.isfinite(a).all():
        raise ValueError("Incompatible non-finite simple-return sample")
    x=np.column_stack((np.ones(n),a[:,1:]))
    y=a[:,0]
    tr=x[:TRAIN];yh=y[TRAIN:]
    sds=np.std(tr[:,1:],axis=0,ddof=1)
    if np.any(sds<1e-8) or not np.isfinite(sds).all():return None
    tr_standard=tr.copy()
    tr_standard[:,1:]=(tr[:,1:]-tr[:,1:].mean(axis=0))/sds
    cond=float(np.linalg.cond(tr_standard))
    if cond>MAX_CONDITION or not np.isfinite(cond):return None
    coef,_,rank,_=np.linalg.lstsq(tr,y[:TRAIN],rcond=None)
    if rank!=7:return None
    resid=y[:TRAIN]-tr@coef
    score=tr*resid[:,None]
    omega=score.T@score
    for lag in range(1,HAC+1):
        part=score[lag:].T@score[:-lag]
        omega+=(1-lag/(HAC+1))*(part+part.T)
    gram_inv=np.linalg.inv(tr.T@tr)
    cov=gram_inv@omega@gram_inv*TRAIN/(TRAIN-7)
    ses=np.sqrt(np.maximum(np.diag(cov),0))
    if not np.isfinite(ses).all() or np.any(ses[1:]<1e-10):return None
    market_coef,_,mrank,_=np.linalg.lstsq(tr[:,:2],y[:TRAIN],rcond=None)
    if mrank!=2:return None
    err=float(np.sum((yh-x[TRAIN:]@coef)**2))
    baseline=float(np.sum((yh-x[TRAIN:,:2]@market_coef)**2))
    if baseline<=1e-8:return None
    return dict(
       betas=coef[1:].tolist(),se=ses[1:].tolist(),intercept=float(coef[0]),
       condition=cond,relative_test_sse=err/baseline,
       holdout_r2_vs_market=1-err/baseline,
       holdout_rmse=math.sqrt(err/TEST),
       baseline_rmse=math.sqrt(baseline/TEST),
       flagged_days=sum(bool(r[8]) for r in rows),
       high_heldout_error=err/baseline>ERROR_RATIO_THRESHOLD,
    )

def stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_style_last AS
    SELECT * EXCLUDE(rn) FROM (
      SELECT *,ROW_NUMBER() OVER(PARTITION BY factor_id,observed_date
        ORDER BY downloaded_at DESC,source_zip_sha256 DESC) rn
      FROM {P}lab_style_factor_returns_v1
      WHERE research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED'
        AND NOT approved_for_institutional_risk_use
    ) x WHERE rn=1
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_ff6_join AS
    WITH f AS (
      SELECT observed_date,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_MKT_RF') mkt,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_SMB') smb,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_HML') hml,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_RMW') rmw,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_CMA') cma,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_MOM') mom,
       MAX(factor_return) FILTER(WHERE factor_id='FF_US_RF') rf
      FROM p1_style_last GROUP BY observed_date
      HAVING COUNT(DISTINCT factor_id)=7
    )
    SELECT a.ticker,a.observed_date,
      10000.0*(EXP(a.return_bps/10000.0)-1-f.rf) asset_excess_bps,
      10000*f.mkt,10000*f.smb,10000*f.hml,10000*f.rmw,
      10000*f.cma,10000*f.mom,a.large_absolute_log_return
    FROM {P}lab_security_returns_retro_v1 a
    JOIN f USING(observed_date)
    WHERE a.currency='USD' AND a.ticker<>'SPY'
      AND isfinite(a.return_bps)
      AND isfinite(f.mkt) AND isfinite(f.smb) AND isfinite(f.hml)
      AND isfinite(f.rmw) AND isfinite(f.cma) AND isfinite(f.mom)
      AND isfinite(f.rf)
    ORDER BY ticker,observed_date
    """)

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("Full source SHA and internal research scope required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_ff6_rolling_beta_windows_v1(
          build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
          window_number INTEGER NOT NULL,train_start DATE NOT NULL,
          train_end DATE NOT NULL,test_start DATE NOT NULL,test_end DATE NOT NULL,
          n_train INTEGER NOT NULL,n_test INTEGER NOT NULL,
          train_condition DOUBLE NOT NULL,
          holdout_r2_vs_market_only DOUBLE NOT NULL,
          holdout_rmse_bps DOUBLE NOT NULL,
          market_baseline_holdout_rmse_bps DOUBLE NOT NULL,
          sample_flagged_large_security_returns BIGINT NOT NULL,
          adjacent_factor_beta_l2_change DOUBLE,
          adjacent_beta_change_requires_review BOOLEAN NOT NULL,
          poor_holdout_relative_error_requires_review BOOLEAN NOT NULL,
          original_source_publication_pit_verified BOOLEAN NOT NULL,
          security_original_corporate_actions_verified BOOLEAN NOT NULL,
          licensed_beta_for_portfolio_risk BOOLEAN NOT NULL)
        """)
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_ff6_rolling_beta_coefficients_v1(
          build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
          window_number INTEGER NOT NULL,factor_id VARCHAR NOT NULL,
          coef_simple_return_bp_per_factor_bp DOUBLE NOT NULL,
          hac5_se DOUBLE NOT NULL,
          original_source_pit_verified BOOLEAN NOT NULL,
          authorized_for_risk_model BOOLEAN NOT NULL)
        """)
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_ff6_rolling_beta_builds_v1(
          build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,script_sha256 VARCHAR NOT NULL,
          built_at TIMESTAMPTZ NOT NULL,security_count BIGINT NOT NULL,
          model_windows BIGINT NOT NULL,coefficients BIGINT NOT NULL,
          adjacent_beta_shift_review_windows BIGINT NOT NULL,
          poor_holdout_fit_review_windows BIGINT NOT NULL,
          windows_with_flagged_price_days BIGINT NOT NULL,
          median_adjacent_beta_l2_shift DOUBLE,
          median_holdout_r2_vs_market DOUBLE NOT NULL,
          source_pit_certified_models BIGINT NOT NULL,
          institutional_release_approved BOOLEAN NOT NULL,
          risk_release_state VARCHAR NOT NULL)
        """)
        stage(con)
        group=defaultdict(list)
        cursor=con.execute("SELECT * FROM p1_ff6_join")
        while chunk:=cursor.fetchmany(20000):
            for ticker,day,*values in chunk:
                if all(v is not None and math.isfinite(float(v)) for v in values[:7]):
                    group[ticker].append((day,*[float(v) for v in values[:7]],bool(values[7])))
        windows=[];coeffs=[]
        for ticker,obs in sorted(group.items()):
            obs.sort(key=lambda r:r[0])
            if len(obs)<TRAIN+TEST:continue
            prev=None
            for i,start in enumerate(range(0,len(obs)-TRAIN-TEST+1,STEP),1):
                rows=obs[start:start+TRAIN+TEST]
                fit=train_window(rows)
                if fit is None:continue
                beta=np.asarray(fit["betas"],dtype=float)
                # Relative beta instability is measured in original economic units
                # with a minimum norm floor; it is not "prediction performance".
                drift=None if prev is None else float(np.linalg.norm(beta-prev)/
                           max(np.linalg.norm(prev),.25))
                prev=beta
                big=drift is not None and drift>BETA_CHANGE_THRESHOLD
                windows.append((
                   build,ticker,i,rows[0][0],rows[TRAIN-1][0],
                   rows[TRAIN][0],rows[-1][0],TRAIN,TEST,fit["condition"],
                   fit["holdout_r2_vs_market"],fit["holdout_rmse"],fit["baseline_rmse"],
                   fit["flagged_days"],drift,bool(big),
                   fit["high_heldout_error"],False,False,False
                ))
                for factor,b,se in zip(FACTORS,fit["betas"],fit["se"]):
                    coeffs.append((build,ticker,i,factor,b,se,False,False))
        if len(windows)<200 or len(coeffs)!=6*len(windows):
            raise RuntimeError("Insufficient beta stability model history, refuse incomplete build")
        shifts=[w[14] for w in windows if w[14] is not None]
        mean_holdout=float(np.median([w[10] for w in windows]))
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(f"INSERT INTO {P}lab_ff6_rolling_beta_windows_v1 VALUES ({','.join(['?']*20)})",windows)
            con.executemany(f"INSERT INTO {P}lab_ff6_rolling_beta_coefficients_v1 VALUES ({','.join(['?']*8)})",coeffs)
            con.execute(f"""
              INSERT INTO {P}lab_ff6_rolling_beta_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,0,FALSE,
                'RESEARCH_ONLY_ROLLING_BETA_NOT_ORIGINAL_PIT_OR_LICENSED')
            """,[build,sha,digest,len({x[1] for x in windows}),len(windows),len(coeffs),
                 sum(w[15] for w in windows),sum(w[16] for w in windows),
                 sum(w[13]>0 for w in windows),
                 float(np.median(shifts)) if shifts else None,mean_holdout])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build} SECURITY_MODELS={len(set(w[1] for w in windows))}")
        print(f"ROLLING_WINDOW_MODELS={len(windows)} FACTOR_COEFFICIENTS={len(coeffs)}")
        print(f"ADJACENT_BETA_SHIFTS_NEEDING_REVIEW={sum(w[15] for w in windows)}")
        print(f"POOR_HOLDOUT_WINDOW_MODELS={sum(w[16] for w in windows)}")
        print(f"WINDOWS_WITH_FLAGGED_SECURITY_PRICE_MOVES={sum(w[13]>0 for w in windows)}")
        print(f"MEDIAN_HOLDOUT_R2_VS_MARKET={mean_holdout:.5f}")
        print("INSTITUTIONAL_BETA_APPROVED=FALSE ORIGINAL_PIT_AND_VENDOR_RIGHTS_VERIFIED=FALSE")
    finally:
        con.close()

if __name__=="__main__":
    main()
