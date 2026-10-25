#!/usr/bin/env python3
"""Predeclared daily walk-forward 7-factor covariance forecast experiment.

Purpose: assess whether fixed EWMA covariance estimates beat a prespecified
252-day equal-weight/shrunk historical comparator on genuinely held-out
SEQUENTIAL observations. Every forecast uses only earlier observed dates;
but all source historical revisions were retrieved ex post, so this is NOT a
publication-time PIT backtest or licensed portfolio/VaR model.

The test slice is final 25% of 655 strict same-date source observations.
Methods all use identical trailing 252-day *training-only* means/sds, with
fixed diagonal-shrinkage 10% or 50%; EWMA decay 0.94/0.97 is prespecified.
No holdout-driven retuning; a post-hoc winner is NOT approved for production.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib,math,os
import duckdb
import numpy as np

P="eventrisk_factor_lab.main."
VERSION="phase1-walk-forward-regime-cov-v1.0.0"
SOURCE_FACTORS=("TREASURY_LEVEL_BPS","TREASURY_SLOPE_BPS","TREASURY_CURVATURE_BPS",
 "ECB_EUR_USD_QUOTE_BPS","ECB_EUR_JPY_QUOTE_BPS",
 "FF_US_MKT_RF_RETURN_BPS","FF_US_MOM_RETURN_BPS")
TRAIN=252
SHRINK_BASE=.10
METHODS=(("eq252_shrink10","equal",0.0,.10),
         ("eq252_shrink50","equal",0.0,.50),
         ("ewma094_shrink10","ewma",.94,.10),
         ("ewma097_shrink10","ewma",.97,.10))
BOOT_SEED=20261025
BOOT_BLOCK=10
BOOT_RESAMPLES=500

def fit_covariance(train,mode,decay,shrink):
    data=np.asarray(train,dtype=float)
    if data.shape!=(TRAIN,7) or not np.isfinite(data).all():
        raise ValueError("Expected 252 complete original-unit factor observations")
    mu=data.mean(axis=0)
    scale=data.std(axis=0,ddof=1)
    if not np.isfinite(scale).all() or np.any(scale<1e-8):
        raise ValueError("Zero/unavailable factor variability")
    z=(data-mu)/scale
    if mode=="equal":
        C=np.cov(z,rowvar=False,ddof=1)
    elif mode=="ewma" and .80<decay<1:
        # Fixed sample mean applies to ALL methods; EWMA second moment
        # is a recency-weighted shock covariance about that common mean.
        w=decay**np.arange(TRAIN-1,-1,-1,dtype=float)
        w/=np.sum(w)
        C=(z*w[:,None]).T@z
    else:
        raise ValueError("Method not predeclared")
    C=(1-shrink)*C+shrink*np.diag(np.diag(C))
    C=(C+C.T)/2.
    eig=np.linalg.eigvalsh(C)
    if eig[0]<1e-8 or not np.isfinite(eig).all():
        raise ValueError("Nonpositive covariance")
    return mu,scale,C,float(eig[-1]/eig[0])

def score_one(today,mu,scale,C):
    v=(np.asarray(today,dtype=float)-mu)/scale
    sign,ld=np.linalg.slogdet(C)
    if sign<=0:raise ValueError("Bad covariance determinant")
    q=float(v@np.linalg.solve(C,v))
    # Twice negative Gaussian logscore, minus common constant 7 log(2pi)
    return float(ld+q),float(np.max(np.abs(v))),q

def paired_block_ci(diff,seed=BOOT_SEED,resamples=BOOT_RESAMPLES,block=BOOT_BLOCK):
    v=np.asarray(diff,dtype=float)
    n=len(v)
    if n<120 or np.any(~np.isfinite(v)):raise ValueError("Insufficient paired holdout")
    rng=np.random.default_rng(seed)
    means=np.empty(resamples)
    nblocks=math.ceil(n/block)
    for b in range(resamples):
        starts=rng.integers(0,n,size=nblocks)
        idx=np.concatenate([(i+np.arange(block))%n for i in starts])[:n]
        means[b]=float(v[idx].mean())
    return float(np.percentile(means,2.5)),float(np.percentile(means,97.5))

def build_stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE p1_walk_cov_input AS
    WITH curve AS (
      SELECT observed_date,level_shock_bps l,slope_shock_bps s,curvature_shock_bps c
      FROM {P}lab_curve_factor_retro_v1
      WHERE build_id=(SELECT build_id FROM {P}lab_security_curve_builds_retro_v1
        ORDER BY created_at DESC LIMIT 1)
    ), fx AS (
      SELECT observed_date,
        MAX(quote_per_eur_log_change_bps) FILTER (WHERE quote_currency='USD') usd,
        MAX(quote_per_eur_log_change_bps) FILTER (WHERE quote_currency='JPY') jpy
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
         ORDER BY downloaded_at DESC,source_zip_sha256 DESC) rn
        FROM {P}lab_style_factor_returns_v1
        WHERE factor_id IN ('FF_US_MKT_RF','FF_US_MOM')
          AND research_status='EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED'
      ) v
      WHERE rn=1 GROUP BY observed_date
      HAVING COUNT(DISTINCT factor_id)=2
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

def setup(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_regime_cov_daily_scores_v1(
      build_id VARCHAR NOT NULL,
      factor_observed_date DATE NOT NULL,
      model_id VARCHAR NOT NULL,
      training_start DATE NOT NULL,
      training_end DATE NOT NULL,
      historical_train_observations INTEGER NOT NULL,
      twice_negative_gaussian_logscore_no_constant DOUBLE NOT NULL,
      largest_train_scaled_factor_move DOUBLE NOT NULL,
      quadratic_mahalanobis_score DOUBLE NOT NULL,
      training_cov_condition DOUBLE NOT NULL,
      training_only_factor_standardization BOOLEAN NOT NULL,
      original_historic_source_pit_verified BOOLEAN NOT NULL,
      licensed_for_portfolio_risk BOOLEAN NOT NULL,
      approved_institutional_risk_model BOOLEAN NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_regime_cov_model_comparisons_v1(
      build_id VARCHAR NOT NULL,model_id VARCHAR NOT NULL,
      training_observations_per_day INTEGER NOT NULL,
      holdout_start DATE NOT NULL,holdout_end DATE NOT NULL,
      evaluated_days INTEGER NOT NULL,
      mean_twice_neg_logscore DOUBLE NOT NULL,
      mean_paired_loss_difference_vs_fixed_baseline DOUBLE NOT NULL,
      pairwise_block_bootstrap_lower95 DOUBLE NOT NULL,
      pairwise_block_bootstrap_upper95 DOUBLE NOT NULL,
      fraction_test_days_better_than_baseline DOUBLE NOT NULL,
      dates_with_absolute_training_scaled_move_over_4 BIGINT NOT NULL,
      posthoc_winner_selection_for_production BOOLEAN NOT NULL,
      source_historic_publication_asof_verified BOOLEAN NOT NULL,
      risk_model_independently_validated BOOLEAN NOT NULL,
      licensed_risk_use_approved BOOLEAN NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_regime_cov_research_builds_v1(
      build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      strict_source_joint_dates BIGINT NOT NULL,
      holdout_days BIGINT NOT NULL,holdout_first DATE NOT NULL,
      holdout_last DATE NOT NULL,factor_count INTEGER NOT NULL,
      prespecified_model_count INTEGER NOT NULL,
      daily_model_scores BIGINT NOT NULL,
      effective_train_days INTEGER NOT NULL,
      methods_with_better_mean_logscore_than_baseline INTEGER NOT NULL,
      methods_with_block_bootstrap_upper95_below_zero INTEGER NOT NULL,
      original_publication_vintages_verified BOOLEAN NOT NULL,
      external_source_rights_cleared BOOLEAN NOT NULL,
      portfolio_risk_model_released BOOLEAN NOT NULL,
      release_status VARCHAR NOT NULL
    )""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Require pinned immutable Git source and internal scope")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        setup(con);build_stage(con)
        rows=con.execute("SELECT * FROM p1_walk_cov_input").fetchall()
        n=len(rows)
        start=max(TRAIN,int(n*.75))
        if n<600 or n-start<125:raise RuntimeError("Not enough untouched chronological evaluation observations")
        data=np.array([r[1:] for r in rows],dtype=float)
        bymethod={name:[] for name,*_ in METHODS}
        out=[]
        for k in range(start,n):
            train=data[k-TRAIN:k]
            for name,mode,decay,shrink in METHODS:
                mu,sd,C,condition=fit_covariance(train,mode,decay,shrink)
                loss,maxz,q=score_one(data[k],mu,sd,C)
                bymethod[name].append(loss)
                out.append((build,rows[k][0],name,rows[k-TRAIN][0],
                            rows[k-1][0],TRAIN,loss,maxz,q,condition,
                            True,False,False,False))
        baseline=np.asarray(bymethod[METHODS[0][0]],dtype=float)
        summaries=[]
        for name,mode,decay,shrink in METHODS:
            scores=np.asarray(bymethod[name],dtype=float)
            differences=scores-baseline
            ci=paired_block_ci(differences)
            improved=float(np.mean(differences<-1e-10)) if name!=METHODS[0][0] else 0.
            nlarge=sum(row[7]>4 and row[2]==name for row in out)
            summaries.append((
                build,name,TRAIN,rows[start][0],rows[-1][0],len(scores),
                float(scores.mean()),float(differences.mean()),
                ci[0],ci[1],improved,nlarge,False,False,False,False))
        better=sum(z[7]<-1e-8 for z in summaries)
        statistically_better=sum(z[9]<0 for z in summaries)
        if len(out)!=len(METHODS)*(n-start):
            raise RuntimeError("Source/score counts mismatched")
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(
                f"INSERT INTO {P}lab_regime_cov_daily_scores_v1 VALUES ({','.join(['?']*14)})",out)
            con.executemany(
                f"INSERT INTO {P}lab_regime_cov_model_comparisons_v1 VALUES ({','.join(['?']*16)})",summaries)
            con.execute(f"""
                INSERT INTO {P}lab_regime_cov_research_builds_v1
                VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,
                 'RETROSPECTIVE_SOURCE_VINTAGES_LICENSES_MODEL_APPROVAL_NOT_CERTIFIED')
            """,[build,sha,script_hash,n,len(baseline),rows[start][0],
                 rows[-1][0],len(SOURCE_FACTORS),len(METHODS),len(out),
                 TRAIN,better,statistically_better])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK");raise
        print(f"BUILD_ID={build} JOINT_DATES={n} EVALUATION_DAYS={len(baseline)} MODEL_SCORES={len(out)}")
        for v in summaries:
            print(f"MODEL={v[1]} MEAN_GAUSSIAN_LOGSCORE={v[6]:.4f} VS_BASELINE={v[7]:.4f} BLOCK_CI95=[{v[8]:.4f},{v[9]:.4f}]")
        print(f"BETTER_AVERAGE_METHODS={better} BLOCK_CI_BELOW_ZERO={statistically_better}")
        print("PRODUCTION_RISK_MODEL_APPROVED=FALSE HISTORIC_PROVIDER_PIT_VERIFIED=FALSE")
    finally:con.close()

if __name__=="__main__":main()
