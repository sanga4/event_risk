#!/usr/bin/env python3
"""Retrospective FF5 + Mom security factor loadings, *never* production risk betas.

Dependent variable is Yahoo adjusted-price *simple* return minus daily French
RF, all in basis points. Regressors: French daily US Mkt-RF, SMB, HML,
RMW, CMA, Mom *simple return* bps. French returns are not price levels and
must never be differenced as Treasury yields or converted to log returns.

Historical factor files and security adjustments were collected in 2026,
so this is a same-day ex-post association, NOT an independently valid
as-of PIT backtest, tradable prediction, investment strategy or event beta.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import math
import os
from pathlib import Path

import duckdb
import numpy as np

P="eventrisk_factor_lab.main."
VERSION="phase1-ff6-security-research-v1.0.0"
REGRESSORS=("FF_US_MKT_RF","FF_US_SMB","FF_US_HML","FF_US_RMW",
            "FF_US_CMA","FF_US_MOM")
ALL=REGRESSORS+("FF_US_RF",)
MIN_N=280
HAC_LAGS=5
MAX_CONDITION=1000.0


def bh_adjust(ps):
    indices=sorted((float(p),i) for i,p in enumerate(ps)
                   if p is not None and math.isfinite(float(p)) and 0<=p<=1)
    out=[None]*len(ps)
    last=1.
    for j in range(len(indices)-1,-1,-1):
        p,i=indices[j]
        last=min(last,p*len(indices)/(j+1))
        out[i]=last
    return out


def fit_ff6(rows):
    """(day, dependent excess simple return bps, six FF simple-return bps, anomalous)."""
    n=len(rows)
    split=int(n*.7)
    p=7
    if n<MIN_N or split<195 or n-split<80:return None
    a=np.asarray([row[1:8] for row in rows],dtype=float)
    if not np.isfinite(a).all():return None
    y=a[:,0]
    X=np.column_stack((np.ones(n),a[:,1:]))
    Xt, Xh=X[:split],X[split:]
    yt,yh=y[:split],y[split:]
    sd=np.std(Xt[:,1:],axis=0,ddof=1)
    if not np.isfinite(sd).all() or np.any(sd<1e-10):
        return None
    z=Xt.copy()
    z[:,1:]=(Xt[:,1:]-Xt[:,1:].mean(axis=0))/sd
    cond=float(np.linalg.cond(z))
    if not math.isfinite(cond) or cond>MAX_CONDITION:return None
    b,_,rank,_=np.linalg.lstsq(Xt,yt,rcond=None)
    if rank!=p:return None
    residual=yt-Xt@b
    scores=Xt*residual[:,None]
    omega=scores.T@scores
    for lag in range(1,min(HAC_LAGS,split-1)+1):
        s=scores[lag:].T@scores[:-lag]
        omega+=(1-lag/(HAC_LAGS+1))*(s+s.T)
    XXinv=np.linalg.inv(Xt.T@Xt)
    covariance=XXinv@omega@XXinv*split/(split-p)
    se=np.sqrt(np.maximum(np.diag(covariance),0))
    if not np.isfinite(se).all() or np.any(se[1:]<1e-12):return None
    zv=[float(b[j]/se[j]) for j in range(1,7)]
    pv=[math.erfc(abs(zj)/math.sqrt(2)) for zj in zv]
    b_market=np.linalg.lstsq(Xt[:,:2],yt,rcond=None)[0]
    full_sse=float(np.sum((yh-Xh@b)**2))
    market_sse=float(np.sum((yh-Xh[:,:2]@b_market)**2))
    train_sst=float(np.sum((yt-yt.mean())**2))
    return {
        "n":n,"train":split,"test":n-split,"first":rows[0][0],
        "last":rows[-1][0],"train_through":rows[split-1][0],
        "test_from":rows[split][0],
        "b":b.tolist(),"se":se.tolist(),"z":zv,"p":pv,
        "condition":cond,
        "train_r2":1-float(np.sum(residual**2))/train_sst if train_sst>1e-10 else None,
        "holdout_r2":1-full_sse/market_sse if market_sse>1e-10 else None,
        "holdout_rmse":math.sqrt(full_sse/(n-split)),
        "market_rmse":math.sqrt(market_sse/(n-split)),
        "flagged":sum(bool(r[8]) for r in rows)
    }


def setup(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_ff6_security_models_retro_v1(
      build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
      benchmark VARCHAR NOT NULL,first_date DATE NOT NULL,
      last_date DATE NOT NULL,train_through DATE NOT NULL,
      test_from DATE NOT NULL,n_matched_dates BIGINT NOT NULL,
      n_train BIGINT NOT NULL,n_holdout BIGINT NOT NULL,
      train_standardized_condition DOUBLE NOT NULL,
      intercept_simple_return_bps DOUBLE NOT NULL,
      train_r2 DOUBLE,holdout_r2_vs_market_only DOUBLE,
      holdout_rmse_bps DOUBLE NOT NULL,
      market_only_holdout_rmse_bps DOUBLE NOT NULL,
      anomalous_security_return_days BIGINT NOT NULL,
      hac_lags INTEGER NOT NULL,dependent_unit VARCHAR NOT NULL,
      independent_source_pit_verified BOOLEAN NOT NULL,
      security_adjustments_independently_verified BOOLEAN NOT NULL,
      vendor_rights_cleared BOOLEAN NOT NULL,
      released_as_institutional_beta BOOLEAN NOT NULL,
      model_status VARCHAR NOT NULL)
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_ff6_security_coefficients_retro_v1(
      build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
      factor_id VARCHAR NOT NULL,coef_simple_bps_per_factor_bp DOUBLE NOT NULL,
      hac5_se DOUBLE NOT NULL,z_normal DOUBLE NOT NULL,
      p_normal DOUBLE NOT NULL,bh_global_q DOUBLE,
      ci95_lower DOUBLE NOT NULL,ci95_upper DOUBLE NOT NULL,
      factor_unit VARCHAR NOT NULL,dependent_unit VARCHAR NOT NULL,
      independently_validated BOOLEAN NOT NULL,
      production_exposure_approved BOOLEAN NOT NULL)
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_ff6_research_builds_v1(
      build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      seven_factor_joint_dates BIGINT NOT NULL,
      source_snapshot_first_ingested_at TIMESTAMPTZ,
      source_snapshot_latest_ingested_at TIMESTAMPTZ,
      included_security_models BIGINT NOT NULL,
      factor_coefficients BIGINT NOT NULL,
      global_bh_q_under_05 BIGINT NOT NULL,
      holdout_improved_over_market BIGINT NOT NULL,
      excluded_or_unfit_securities BIGINT NOT NULL,
      anomalous_price_exposed_models BIGINT NOT NULL,
      largest_training_condition DOUBLE,
      certified_source_vintages BIGINT NOT NULL,
      licensed_released_betas BIGINT NOT NULL,
      release_state VARCHAR NOT NULL)
    """)


def stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_latest_style AS
    SELECT * EXCLUDE(rn) FROM (
      SELECT *,ROW_NUMBER() OVER(
        PARTITION BY factor_id,observed_date
        ORDER BY downloaded_at DESC,source_zip_sha256 DESC) rn
      FROM {P}lab_style_factor_returns_v1
      WHERE research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED'
        AND NOT historical_point_in_time_verified
        AND NOT licensed_for_distribution
    ) s WHERE rn=1
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_ff6_joint AS
    SELECT observed_date,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_MKT_RF') AS mkt,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_SMB') AS smb,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_HML') AS hml,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_RMW') AS rmw,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_CMA') AS cma,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_MOM') AS mom,
      MAX(factor_return) FILTER(WHERE factor_id='FF_US_RF') AS rf,
      MIN(downloaded_at) AS earliest_snapshot_retrieved,
      MAX(downloaded_at) AS latest_snapshot_retrieved
    FROM p1_latest_style
    WHERE factor_id IN ('FF_US_MKT_RF','FF_US_SMB','FF_US_HML',
                        'FF_US_RMW','FF_US_CMA','FF_US_MOM','FF_US_RF')
      AND unit='daily_simple_return_decimal' AND currency='USD'
    GROUP BY observed_date
    HAVING COUNT(DISTINCT factor_id)=7
      AND COUNT(*) FILTER (WHERE factor_return IS NULL
        OR NOT isfinite(factor_return))=0
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_ff6_merged AS
    SELECT a.ticker,a.observed_date,
      10000.0*(EXP(a.return_bps/10000.0)-1.0-f.rf) AS excess_simple_bps,
      10000.0*f.mkt AS market_bps,
      10000.0*f.smb AS size_bps,
      10000.0*f.hml AS value_bps,
      10000.0*f.rmw AS profitability_bps,
      10000.0*f.cma AS investment_bps,
      10000.0*f.mom AS momentum_bps,
      a.large_absolute_log_return
    FROM {P}lab_security_returns_retro_v1 a
    JOIN p1_ff6_joint f ON f.observed_date=a.observed_date
    WHERE a.ticker<>'SPY' AND a.currency='USD'
    ORDER BY a.ticker,a.observed_date
    """)


def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit)):
        raise RuntimeError("Internal scope and immutable Git SHA required")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        setup(con)
        stage(con)
        n_days,earliest,latest=con.execute(
            "SELECT COUNT(*),MIN(earliest_snapshot_retrieved),"
            "MAX(latest_snapshot_retrieved) FROM p1_ff6_joint"
        ).fetchone()
        if n_days<600 or latest is None:
            raise RuntimeError("Not enough seven-factor daily source overlap")
        grouped=defaultdict(list)
        cur=con.execute("SELECT * FROM p1_ff6_merged")
        while batch:=cur.fetchmany(15000):
            for ticker,day,y,mkt,size,val,prof,inv,mom,flag in batch:
                nums=(y,mkt,size,val,prof,inv,mom)
                if all(v is not None and math.isfinite(float(v)) for v in nums):
                    grouped[ticker].append((day,*[float(v) for v in nums],bool(flag)))
        models,coefficients=[],[]
        for ticker,rows in sorted(grouped.items()):
            rows.sort(key=lambda r:r[0])
            if len({(r[0].year,r[0].month) for r in rows})<18:
                continue
            m=fit_ff6(rows)
            if m is None:continue
            models.append((
                build,ticker,"FF_US_MKT_RF",m["first"],m["last"],
                m["train_through"],m["test_from"],m["n"],m["train"],m["test"],
                m["condition"],m["b"][0],m["train_r2"],m["holdout_r2"],
                m["holdout_rmse"],m["market_rmse"],m["flagged"],HAC_LAGS,
                "usd_security_daily_excess_simple_return_bps",
                False,False,False,False,
                "RETROSPECTIVE_FF6_EXPLANATORY_NOT_PIT_OR_LICENSED"
            ))
            for j,name in enumerate(REGRESSORS):
                b=m["b"][j+1]
                se=m["se"][j+1]
                coefficients.append((
                    build,ticker,name,b,se,m["z"][j],m["p"][j],
                    None,b-1.96*se,b+1.96*se,
                    "style_daily_simple_return_bps",
                    "usd_security_daily_excess_simple_return_bps",
                    False,False
                ))
        q=bh_adjust([row[6] for row in coefficients])
        coefficients=[(*r[:7],qv,*r[8:]) for r,qv in zip(coefficients,q)]
        sig=sum(z is not None and z<.05 for z in q)
        improved=sum(row[13] is not None and row[13]>0 for row in models)
        flagged=sum(row[16]>0 for row in models)
        max_condition=max((row[10] for row in models),default=None)
        if len(models)<25:
            raise RuntimeError("Insufficient fitted security models; refuse write")
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(
                f"INSERT INTO {P}lab_ff6_security_models_retro_v1 "
                f"VALUES ({','.join(['?']*24)})",models
            )
            con.executemany(
                f"INSERT INTO {P}lab_ff6_security_coefficients_retro_v1 "
                f"VALUES ({','.join(['?']*14)})",coefficients
            )
            con.execute(f"""
             INSERT INTO {P}lab_ff6_research_builds_v1
             VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,0,0,
               'RETROSPECTIVE_SOURCE_RIGHTS_PIT_AND_MODEL_RISK_NOT_APPROVED')
            """,[
                build,commit,digest,n_days,earliest,latest,len(models),
                len(coefficients),sig,improved,len(grouped)-len(models),
                flagged,max_condition
            ])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build)
        print("SEVEN_FACTOR_JOINT_DATES="+str(n_days))
        print("FITTED_SECURITY_MODELS="+str(len(models)))
        print("RESEARCH_BETA_COEFFICIENTS="+str(len(coefficients)))
        print("GLOBAL_BH_Q_BELOW_5PCT="+str(sig))
        print("HOLDOUT_IMPROVED_VS_MARKET_ONLY="+str(improved))
        print("MODELS_WITH_FLAGGED_PRICE_DAYS="+str(flagged))
        print("MAX_STANDARDIZED_TRAIN_CONDITION="+str(max_condition))
        print("INDEPENDENTLY_VERIFIED_SOURCE_VINTAGES=0")
        print("LICENSED_PRODUCTION_SECURITY_BETAS=0")
    finally:
        con.close()


if __name__=="__main__":
    main()
