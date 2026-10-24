#!/usr/bin/env python3
"""Historical security vs Treasury-yield sensitivity — NOT production exposure.

Backfills recorded adjusted-close USD instrument returns and government/derived
factor changes in bps; estimates market-controlled, descriptive retrospective
loadings with HAC(5), chronological OOS and global Benjamini-Hochberg FDR.

Not PIT-certified; adjusted Yahoo series have ex-post corporate-action revisions.
Not an event innovation/response beta, causal estimate or trading signal.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import duckdb

P="eventrisk_factor_lab.main."
VERSION="phase1-security-rates-research-v1.0.0"
LICENSE=("government_source_via_treasury","government_source_via_fred",
         "derived_not_true_breakeven")
MIN_N=250
HAC_LAGS=5

def bh_adjust(values):
    valid=sorted((max(0.,min(1.,p)),i) for i,p in enumerate(values)
                 if p is not None and math.isfinite(p))
    q=[None]*len(values)
    lowest=1.
    for pos in range(len(valid)-1,-1,-1):
        p,i=valid[pos]
        lowest=min(lowest,p*len(valid)/(pos+1))
        q[i]=lowest
    return q

def fit_regression(rows, lag=HAC_LAGS):
    """y = intercept + beta_SPY*m + beta_rate*x; HAC for partial rate slope.

    y,m are USD instrument and SPY daily log returns in *basis points*;
    x is a Treasury/derived yield daily change in basis points.
    β_rate has units [asset-return bps]/[yield-change bp].
    """
    n=len(rows)
    nt=int(.70*n)
    if n<MIN_N or nt<175 or n-nt<60:
        return None
    train=rows[:nt]
    y=[float(z[2]) for z in train]
    m=[float(z[3]) for z in train]
    x=[float(z[4]) for z in train]
    ym=sum(y)/nt; mm=sum(m)/nt; xm=sum(x)/nt
    dm=[v-mm for v in m]
    dx=[v-xm for v in x]
    dy=[v-ym for v in y]
    s_mm=sum(v*v for v in dm)
    if s_mm <= 1.e-10: return None
    b_x_on_m=sum(a*b for a,b in zip(dm,dx))/s_mm
    xr=[a-b_x_on_m*b for a,b in zip(dx,dm)]
    xx=sum(a*a for a in xr)
    if xx<=1.e-10: return None
    beta_r=sum(a*b for a,b in zip(xr,dy))/xx
    beta_m=(sum(a*b for a,b in zip(dm,dy))/s_mm)-beta_r*b_x_on_m
    alpha=ym-beta_m*mm-beta_r*xm
    resid=[yy-alpha-beta_m*mt-beta_r*xt for yy,mt,xt in zip(y,m,x)]
    sse=sum(r*r for r in resid)
    sst=sum((yy-ym)**2 for yy in y)
    r2=1-sse/sst if sst>1e-12 else None
    scores=[a*b for a,b in zip(xr,resid)]
    meat=sum(s*s for s in scores)
    for h in range(1,min(lag,nt-1)+1):
        w=1-h/(lag+1)
        meat+=2*w*sum(scores[t]*scores[t-h] for t in range(h,nt))
    se=math.sqrt(max(0.,meat)*nt/(nt-3))/xx
    z=beta_r/se if se>1e-12 else None
    p=math.erfc(abs(z)/math.sqrt(2)) if z is not None else None
    b_market_only=sum(a*b for a,b in zip(dm,dy))/s_mm
    a_market_only=ym-b_market_only*mm
    holdout=rows[nt:]
    fullerr=sum((yy-(alpha+beta_m*mt+beta_r*xt))**2
                for _,_,yy,mt,xt,_ in holdout)
    baseerr=sum((yy-(a_market_only+b_market_only*mt))**2
                for _,_,yy,mt,xt,_ in holdout)
    oos=1-fullerr/baseerr if baseerr>1e-12 else None
    return {"n":n,"train":nt,"test":n-nt,"slope":beta_r,"market_beta":beta_m,
            "intercept":alpha,"r2":r2,"hac_se":se,"z":z,"p":p,
            "oos_r2_vs_market_only":oos,
            "oos_rmse":math.sqrt(fullerr/(n-nt)),
            "baseline_rmse":math.sqrt(baseerr/(n-nt)),
            "outliers":sum(bool(z[5]) for z in rows)}

def setup(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_security_returns_retro_v1 (
      ticker VARCHAR NOT NULL,observed_date DATE NOT NULL,
      adjusted_close DOUBLE NOT NULL,previous_close DOUBLE NOT NULL,
      previous_observed_date DATE NOT NULL,return_bps DOUBLE NOT NULL,
      currency VARCHAR NOT NULL,source VARCHAR NOT NULL,
      fetched_at TIMESTAMPTZ NOT NULL,source_run_id VARCHAR NOT NULL,
      large_absolute_log_return BOOLEAN NOT NULL,
      source_availability_pit_verified BOOLEAN NOT NULL,
      corporate_action_vintage_verified BOOLEAN NOT NULL,
      data_use_class VARCHAR NOT NULL,build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_rate_shocks_retro_v1 (
      factor_id VARCHAR NOT NULL,observed_date DATE NOT NULL,
      yield_level_pct DOUBLE NOT NULL,previous_yield_level_pct DOUBLE NOT NULL,
      previous_observed_date DATE NOT NULL,shock_bps DOUBLE NOT NULL,
      provider VARCHAR NOT NULL,source_record_sha256 VARCHAR NOT NULL,
      source_ingested_at TIMESTAMPTZ NOT NULL,
      source_availability_at TIMESTAMPTZ NOT NULL,
      published_vintage_independently_verified BOOLEAN NOT NULL,
      data_use_class VARCHAR NOT NULL,build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_security_rate_betas_retro_v1 (
      ticker VARCHAR NOT NULL,market_benchmark VARCHAR NOT NULL,
      factor_id VARCHAR NOT NULL,
      response_unit VARCHAR NOT NULL,predictor_unit VARCHAR NOT NULL,
      beta_unit VARCHAR NOT NULL,n_observations BIGINT NOT NULL,
      n_train BIGINT NOT NULL,n_test BIGINT NOT NULL,
      first_date DATE NOT NULL,last_date DATE NOT NULL,
      beta_rate DOUBLE, beta_spy DOUBLE,intercept DOUBLE,
      train_r_squared DOUBLE,hac_lags INTEGER NOT NULL,
      hac_rate_se DOUBLE,rate_z_approx DOUBLE,
      rate_p_normal DOUBLE,rate_bh_fdr_q DOUBLE,
      rate_ci95_lower DOUBLE,rate_ci95_upper DOUBLE,
      test_r2_vs_spy_only DOUBLE,test_rmse_bps DOUBLE,
      baseline_spy_only_rmse_bps DOUBLE,
      large_return_observations BIGINT NOT NULL,
      point_in_time_verified BOOLEAN NOT NULL,
      independent_data_rights_verified BOOLEAN NOT NULL,
      released_for_risk_use BOOLEAN NOT NULL,
      model_status VARCHAR NOT NULL,build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_security_beta_builds_retro_v1 (
      build_id VARCHAR NOT NULL,pipeline_version VARCHAR NOT NULL,
      source_commit VARCHAR NOT NULL,source_script_sha256 VARCHAR NOT NULL,
      built_at TIMESTAMPTZ NOT NULL,price_source_records BIGINT NOT NULL,
      price_duplicate_ticker_dates BIGINT NOT NULL,
      transformed_security_returns BIGINT NOT NULL,
      percent_rate_shock_rows BIGINT NOT NULL,
      retrospective_beta_models BIGINT NOT NULL,
      fdr_below_5pct BIGINT NOT NULL,
      positive_oos_vs_spy_only BIGINT NOT NULL,
      large_price_moves_flagged BIGINT NOT NULL,
      validated_pit_betas BIGINT NOT NULL,
      research_release_state VARCHAR NOT NULL
    )""")

def stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_sec_returns AS
    WITH dedup AS (
      SELECT ticker,date,adj_close,currency,source,fetched_at,run_id,
        row_number() OVER (PARTITION BY ticker,date
          ORDER BY fetched_at DESC NULLS LAST, run_id DESC NULLS LAST,
                   adj_close DESC) AS rank_latest
      FROM {P}security_prices
      WHERE ticker IS NOT NULL AND date IS NOT NULL AND adj_close IS NOT NULL
        AND isfinite(adj_close) AND adj_close > 0 AND currency='USD'
        AND source='yahoo' AND fetched_at IS NOT NULL
    ), daily AS (
      SELECT *,
        lag(adj_close) OVER (PARTITION BY ticker ORDER BY date) AS prev_price,
        lag(date) OVER (PARTITION BY ticker ORDER BY date) AS prev_date
      FROM dedup WHERE rank_latest=1
    )
    SELECT ticker,date AS observed_date,adj_close AS adjusted_close,
      prev_price AS previous_close,prev_date AS previous_observed_date,
      10000.0*ln(adj_close/prev_price) AS return_bps,
      currency,source,fetched_at,run_id AS source_run_id,
      (ABS(ln(adj_close/prev_price))>0.25) AS large_absolute_log_return,
      FALSE AS source_availability_pit_verified,
      FALSE AS corporate_action_vintage_verified,
      'retrospective_research_only'::VARCHAR AS data_use_class
    FROM daily
    WHERE prev_price IS NOT NULL
      AND date_diff('day',prev_date,date) BETWEEN 1 AND 7
      AND isfinite(ln(adj_close/prev_price))
    """)
    allowed=",".join("'"+s+"'" for s in LICENSE)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_rate_shocks AS
    WITH eligible AS (
      SELECT f.factor_id,f.observed_date,f.value,f.unit,f.provider,
        f.record_sha256,f.ingested_at,f.availability_at,
        row_number() OVER (PARTITION BY f.factor_id,f.observed_date
          ORDER BY f.ingested_at DESC,f.record_sha256 DESC) AS rk
      FROM {P}lab_factor_observations f
      JOIN {P}lab_factor_catalog c USING (factor_id)
      WHERE c.active AND c.license_class IN ({allowed})
        AND f.unit=c.unit AND f.unit='percent'
        AND f.value IS NOT NULL AND isfinite(f.value)
    ), dedup AS(
      SELECT * EXCLUDE(rk) FROM eligible WHERE rk=1
    ), lagged AS (
      SELECT *,
        lag(value) OVER(PARTITION BY factor_id ORDER BY observed_date)
          AS prev_value,
        lag(observed_date) OVER(PARTITION BY factor_id ORDER BY observed_date)
          AS prev_date
      FROM dedup
    )
    SELECT factor_id,observed_date,value AS yield_level_pct,
      prev_value AS previous_yield_level_pct,
      prev_date AS previous_observed_date,
      100.0*(value-prev_value) AS shock_bps,
      provider,record_sha256 AS source_record_sha256,
      ingested_at AS source_ingested_at,
      availability_at AS source_availability_at,
      FALSE AS published_vintage_independently_verified,
      'retrospective_research_only'::VARCHAR AS data_use_class
    FROM lagged
    WHERE prev_value IS NOT NULL
      AND date_diff('day',prev_date,observed_date) BETWEEN 1 AND 7
      AND isfinite(value-prev_value)
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE tmp_asset_factor_join AS
    SELECT a.ticker,f.factor_id,a.observed_date,a.return_bps,
      b.return_bps AS spy_return_bps,f.shock_bps,
      a.large_absolute_log_return
    FROM tmp_sec_returns a
    JOIN tmp_sec_returns b
      ON b.ticker='SPY' AND b.observed_date=a.observed_date
    JOIN tmp_rate_shocks f ON f.observed_date=a.observed_date
    WHERE a.ticker<>'SPY'
    ORDER BY a.ticker,f.factor_id,a.observed_date
    """)

def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("Internal research and 40-character immutable source SHA required")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        setup(con)
        stage(con)
        quality=con.execute(f"""
          SELECT
            (SELECT count(*) FROM {P}security_prices),
            (SELECT count(*)-count(DISTINCT ticker||':'||CAST(date AS VARCHAR))
               FROM {P}security_prices),
            (SELECT count(*) FROM tmp_sec_returns),
            (SELECT count(*) FROM tmp_rate_shocks),
            (SELECT count(*) FROM tmp_sec_returns WHERE large_absolute_log_return)
        """).fetchone()
        groups=defaultdict(list)
        cursor=con.execute("SELECT * FROM tmp_asset_factor_join")
        while True:
            chunk=cursor.fetchmany(15000)
            if not chunk:break
            for ticker,factor_id,day,y,market,shock,outlier in chunk:
                if all(math.isfinite(v) for v in (y,market,shock)):
                    groups[(ticker,factor_id)].append(
                        (ticker,day,float(y),float(market),float(shock),bool(outlier))
                    )
        modeled=[]
        for (ticker,factor_id),rows in sorted(groups.items()):
            rows.sort(key=lambda z:z[1])
            if len({(day.year,day.month) for _,day,*_ in rows})<18:
                continue
            m=fit_regression(rows)
            if m is not None:
                modeled.append((ticker,factor_id,rows[0][1],rows[-1][1],m))
        adjusted=bh_adjust([r[-1]["p"] for r in modeled])
        model_rows=[]
        for (ticker,factor_id,first,last,m),q in zip(modeled,adjusted):
            lower=m["slope"]-1.96*m["hac_se"]
            upper=m["slope"]+1.96*m["hac_se"]
            model_rows.append((
              ticker,"SPY",factor_id,"asset_log_return_bps",
              "yield_change_bps","asset_return_bps_per_1bp_yield",
              m["n"],m["train"],m["test"],first,last,
              m["slope"],m["market_beta"],m["intercept"],m["r2"],
              HAC_LAGS,m["hac_se"],m["z"],m["p"],q,lower,upper,
              m["oos_r2_vs_market_only"],m["oos_rmse"],m["baseline_rmse"],
              m["outliers"],False,False,False,
              "EX_POST_MARKET_CONTROLLED_SENSITIVITY_NOT_PIT",build))
        n_sig=sum(q is not None and q < .05 for q in adjusted)
        n_oos=sum(r[-1]["oos_r2_vs_market_only"] is not None and
                  r[-1]["oos_r2_vs_market_only"]>0 for r in modeled)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"DELETE FROM {P}lab_security_returns_retro_v1")
            con.execute(f"DELETE FROM {P}lab_rate_shocks_retro_v1")
            con.execute(f"DELETE FROM {P}lab_security_rate_betas_retro_v1")
            con.execute(f"INSERT INTO {P}lab_security_returns_retro_v1 SELECT *,? FROM tmp_sec_returns",[build])
            con.execute(f"INSERT INTO {P}lab_rate_shocks_retro_v1 SELECT *,? FROM tmp_rate_shocks",[build])
            if model_rows:
                placeholders=",".join(["?"]*31)
                con.executemany(f"INSERT INTO {P}lab_security_rate_betas_retro_v1 VALUES ({placeholders})",model_rows)
            con.execute(f"""
              INSERT INTO {P}lab_security_beta_builds_retro_v1
              VALUES (?,?,?,?,current_timestamp,?,?,?,?,?,?,?,?,0,
                      'RETROSPECTIVE_PIT_AND_DATA_RIGHTS_UNVERIFIED')
            """,[build,VERSION,commit,digest,quality[0],quality[1],quality[2],
                  quality[3],len(model_rows),n_sig,n_oos,quality[4]])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build)
        print(f"RAW_SECURITY_PRICES={quality[0]} DUPLICATE_TICKER_DATES={quality[1]}")
        print(f"USD_ADJUSTED_RETURN_ROWS={quality[2]} FLAGGED_ABNORMAL_MOVES={quality[4]}")
        print(f"RATE_CHANGE_BPS_ROWS={quality[3]} RETROSPECTIVE_BETA_MODELS={len(model_rows)}")
        print(f"FDR_BELOW_5PCT={n_sig} POSITIVE_OOS_VS_SPY_ONLY={n_oos}")
        print("INSTITUTIONALLY_VALIDATED_BETAS=0")
        print("DATA_PIT_OR_LICENSE_RELEASE=BLOCKED")
    finally:
        con.close()

if __name__=="__main__":
    main()
