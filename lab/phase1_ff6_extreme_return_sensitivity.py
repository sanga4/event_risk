#!/usr/bin/env python3
"""Sensitivity of six-factor research beta to extreme security return observations.

Does not decide whether any observation is erroneous or represent a real split,
dividend or price. Compare SAME original chronological 70/30 split:
OLS(FF5+Mom, all training days) vs OLS(excluding independently already-flagged
>25% absolute adjusted log-return days FROM TRAIN ONLY). Both are scored on
the same untouched holdout, including its flagged observations. No source
value is deleted/modified; no original vendor publication PIT or rights.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import hashlib,math,os
import duckdb,numpy as np

P="eventrisk_factor_lab.main."
VERSION="phase1-ff6-extreme-return-sensitivity-v1.0.0"
FACTORS=("FF_US_MKT_RF","FF_US_SMB","FF_US_HML","FF_US_RMW","FF_US_CMA","FF_US_MOM")
DELTA_THRESHOLD=.10
MIN_N=280

def compare(rows):
    n=len(rows)
    train=int(n*.70)
    if n<MIN_N or train<195 or n-train<80:return None
    data=np.asarray([r[1:8] for r in rows],dtype=float)
    if not np.isfinite(data).all():return None
    flags=np.asarray([bool(r[8]) for r in rows])
    X=np.column_stack((np.ones(n),data[:,1:]))
    y=data[:,0]
    trX,trY=X[:train],y[:train]
    trflags=flags[:train]
    if int((~trflags).sum())<195:return None
    full,_,rank,_=np.linalg.lstsq(trX,trY,rcond=None)
    clean,_,rankclean,_=np.linalg.lstsq(trX[~trflags],trY[~trflags],rcond=None)
    if rank!=7 or rankclean!=7:return None
    def full_condition(x):
        sd=x[:,1:].std(axis=0,ddof=1)
        if np.any(sd<=1e-9):return float("inf")
        z=x.copy();z[:,1:]=(x[:,1:]-x[:,1:].mean(axis=0))/sd
        return float(np.linalg.cond(z))
    cf=full_condition(trX);cc=full_condition(trX[~trflags])
    if not np.isfinite(cf+cc) or cf>1000 or cc>1000:return None
    relative=float(np.linalg.norm(clean[1:]-full[1:])/
        max(np.linalg.norm(full[1:]),.25))
    hX=X[train:];hy=y[train:]
    fullsse=float(np.sum((hy-hX@full)**2))
    cleansse=float(np.sum((hy-hX@clean)**2))
    if fullsse<1.e-8:return None
    return {
      "n":n,"train":train,"holdout":n-train,"flagged_train":int(trflags.sum()),
      "flagged_holdout":int(flags[train:].sum()),
      "full_beta":full.tolist(),"excluded_beta":clean.tolist(),
      "relative_beta_shift":relative,
      "holdout_sse_change_ratio":cleansse/fullsse,
      "holdout_baseline_rmse":math.sqrt(fullsse/(n-train)),
      "holdout_exclusion_rmse":math.sqrt(cleansse/(n-train)),
      "full_condition":cf,"excluded_condition":cc
    }

def stage(con):
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE p1_style_latest AS
      SELECT * EXCLUDE(rn) FROM (
        SELECT *,ROW_NUMBER() OVER(PARTITION BY observed_date,factor_id
          ORDER BY downloaded_at DESC,source_zip_sha256 DESC) rn
        FROM {P}lab_style_factor_returns_v1
        WHERE research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED'
      ) x WHERE rn=1
    """)
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE p1_ff6_outlier AS
      WITH f AS (
        SELECT observed_date,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_MKT_RF') mkt,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_SMB') smb,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_HML') hml,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_RMW') rmw,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_CMA') cma,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_MOM') mom,
          MAX(factor_return) FILTER(WHERE factor_id='FF_US_RF') rf
        FROM p1_style_latest GROUP BY observed_date
        HAVING COUNT(DISTINCT factor_id)=7
      )
      SELECT s.ticker,s.observed_date,
        10000.0*(EXP(s.return_bps/10000.0)-1-f.rf) y,
        10000*f.mkt mkt,10000*f.smb smb,10000*f.hml hml,
        10000*f.rmw rmw,10000*f.cma cma,10000*f.mom mom,
        s.large_absolute_log_return
      FROM {P}lab_security_returns_retro_v1 s
      JOIN f USING(observed_date)
      WHERE s.currency='USD' AND s.ticker<>'SPY'
        AND isfinite(s.return_bps)
        AND isfinite(f.mkt) AND isfinite(f.smb) AND isfinite(f.hml)
        AND isfinite(f.rmw) AND isfinite(f.cma) AND isfinite(f.mom)
        AND isfinite(f.rf)
      ORDER BY s.ticker,s.observed_date
    """)

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("Pinned source SHA and research-only scope required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
         CREATE TABLE IF NOT EXISTS {P}lab_ff6_price_extreme_sensitivity_v1(
           build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
           earliest_date DATE NOT NULL,latest_date DATE NOT NULL,
           matched_days BIGINT NOT NULL,original_train_days BIGINT NOT NULL,
           untouched_holdout_days BIGINT NOT NULL,
           flagged_train_returns_excluded_from_sensitivity_fit BIGINT NOT NULL,
           flagged_holdout_days_not_excluded BIGINT NOT NULL,
           original_full_betas_train_condition DOUBLE NOT NULL,
           counterfactual_excluding_train_flags_condition DOUBLE NOT NULL,
           relative_six_beta_l2_shift DOUBLE NOT NULL,
           full_training_holdout_rmse_bps DOUBLE NOT NULL,
           excluding_flagged_training_holdout_rmse_bps DOUBLE NOT NULL,
           counterfactual_heldout_squared_error_ratio_vs_full DOUBLE NOT NULL,
           beta_shift_review_threshold_exceeded BOOLEAN NOT NULL,
           price_error_or_corporate_action_independently_verified BOOLEAN NOT NULL,
           source_revision_pit_certified BOOLEAN NOT NULL,
           licensed_institutional_beta_approved BOOLEAN NOT NULL
         )""")
        con.execute(f"""
         CREATE TABLE IF NOT EXISTS {P}lab_ff6_price_extreme_beta_components_v1(
           build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
           factor_id VARCHAR NOT NULL,
           beta_original_full_training DOUBLE NOT NULL,
           beta_counterfactual_excluding_flagged_training_days DOUBLE NOT NULL,
           independently_approved_cleaned_security_beta BOOLEAN NOT NULL
         )""")
        con.execute(f"""
         CREATE TABLE IF NOT EXISTS {P}lab_ff6_price_extreme_builds_v1(
           build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
           code_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
           eligible_security_models BIGINT NOT NULL,
           matched_factor_coefficients BIGINT NOT NULL,
           securities_with_training_outliers BIGINT NOT NULL,
           securities_with_heldout_outliers BIGINT NOT NULL,
           securities_exceeding_10pct_relative_beta_change BIGINT NOT NULL,
           securities_exclusion_reduced_same_holdout_sse BIGINT NOT NULL,
           largest_relative_beta_change DOUBLE NOT NULL,
           source_price_corrections_made BIGINT NOT NULL,
           original_corporate_actions_independently_verified BIGINT NOT NULL,
           risk_betas_approved BIGINT NOT NULL,
           release_state VARCHAR NOT NULL
         )""")
        stage(con)
        observations=defaultdict(list)
        cur=con.execute("SELECT * FROM p1_ff6_outlier")
        while block:=cur.fetchmany(15000):
            for ticker,day,*data in block:
                if all(v is not None and math.isfinite(float(v)) for v in data[:7]):
                    observations[ticker].append((day,*[float(v) for v in data[:7]],bool(data[7])))
        result=[];components=[]
        for ticker,rows in sorted(observations.items()):
            rows.sort(key=lambda r:r[0])
            m=compare(rows)
            if m is None:continue
            result.append((build,ticker,rows[0][0],rows[-1][0],m["n"],m["train"],
             m["holdout"],m["flagged_train"],m["flagged_holdout"],
             m["full_condition"],m["excluded_condition"],m["relative_beta_shift"],
             m["holdout_baseline_rmse"],m["holdout_exclusion_rmse"],
             m["holdout_sse_change_ratio"],m["relative_beta_shift"]>=DELTA_THRESHOLD,
             False,False,False))
            for i,f in enumerate(FACTORS):
                components.append((build,ticker,f,m["full_beta"][i+1],
                         m["excluded_beta"][i+1],False))
        if len(result)<45 or len(components)!=6*len(result):
            raise RuntimeError("Unexpected factor/survivor universe")
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(f"INSERT INTO {P}lab_ff6_price_extreme_sensitivity_v1 VALUES ({','.join(['?']*19)})",result)
            con.executemany(f"INSERT INTO {P}lab_ff6_price_extreme_beta_components_v1 VALUES ({','.join(['?']*6)})",components)
            con.execute(f"""
               INSERT INTO {P}lab_ff6_price_extreme_builds_v1
               VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,0,0,0,
                 'EX_POST_COUNTERFACTUAL_SENSITIVITY_NO_SOURCE_CORRECTIONS_OR_PIT_APPROVAL')
            """,[build,sha,digest,len(result),len(components),
                 sum(x[7]>0 for x in result),sum(x[8]>0 for x in result),
                 sum(x[15] for x in result),sum(x[14]<1 for x in result),
                 max(x[11] for x in result)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK");raise
        print(f"BUILD_ID={build} USD_SECURITIES={len(result)} SIX_FACTOR_EXPOSURES={len(components)}")
        print(f"WITH_FLAGGED_TRAINING_PRICE_DAYS={sum(x[7]>0 for x in result)}")
        print(f"WITH_FLAGGED_HELDOUT_PRICE_DAYS={sum(x[8]>0 for x in result)}")
        print(f"BETA_RELATIVE_SHIFT_AT_LEAST_10PCT={sum(x[15] for x in result)}")
        print(f"EXCLUSION_IMPROVED_UNTOUCHED_HELDOUT_SSE={sum(x[14]<1 for x in result)}")
        print(f"MAX_SIX_BETA_SHIFT={max(x[11] for x in result):.4f}")
        print("SOURCE_PRICES_DELETED=0 VERIFIED_CORPORATE_ACTIONS=0 RISK_MODEL_APPROVED=FALSE")
    finally:con.close()

if __name__=="__main__":main()
