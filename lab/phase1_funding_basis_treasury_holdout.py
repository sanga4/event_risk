#!/usr/bin/env python3
"""Retrospective NYFed funding-basis / Treasury shock quality and holdout study.

Source-normalized SOFR-EFFR basis in bps, and two *contemporaneous* factor
comovement diagnostics (basis change; SOFR rate-level change). One next-date
funding change is a deliberately unavailable placebo. No source provider PIT
clock, Fed policy surprise, causal event response, asset beta, or rights claim.
"""
from __future__ import annotations
from datetime import datetime,timezone,date
from pathlib import Path
import hashlib,math,os

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-funding-basis-treasury-retro-v1.0.0"
FEATURES=frozenset(("basis_change_bps","sofr_change_bps"))
FACTOR_COUNT=18
TRAIN_FRACTION=.70
MIN_HISTORY=450
MIN_TRAIN=300
MIN_HOLDOUT=120
MIN_MONTHS=18

def review_source(rate_check,factor_check,build_check):
    """Fail before any persistent write on duplicated keys or implied PIT claims.

    rate_check: total day pairs, distinct dates, earliest, latest, bad source flags.
    factor_check: distinct active factor IDs, invalid values/units or source IDs.
    build_check: rate-source audit rows and original approval flags.
    """
    if len(rate_check)!=5 or len(factor_check)!=2 or len(build_check)!=4:
        raise ValueError("Source preflight contract changed")
    dates,distinct,first,last,bad=rate_check
    count,invalid=factor_check
    source_rows,overlap,revisions,approved=build_check
    if (dates<1500 or dates!=distinct or first is None or last is None
        or first>date(2018,12,31) or last<date(2024,1,1)
        or bad or count!=FACTOR_COUNT or invalid
        or source_rows<4000 or overlap<500 or revisions!=0 or approved):
        raise ValueError("Original funding source integrity, coverage, or rights failed")
    return True

def review_models(rows,source_days):
    """Do not misinterpret 36 contemporaneous OLS fits as causal betas."""
    if len(rows)!=FACTOR_COUNT*len(FEATURES) or source_days<1500:
        raise ValueError("Missing Treasury factor/funding feature model combinations")
    seen=set()
    for r in rows:
        if len(r)!=17:
            raise ValueError("Model result schema changed")
        (fid,feature,n,train,test,months,first,last_train,first_test,last,
         in_r2,out_r2,placebo_r2,var_y,mse_baseline,max_gap_days,bad)=r
        if ((fid,feature) in seen or not fid or feature not in FEATURES):
            raise ValueError("Duplicated or unsupported feature/factor model")
        seen.add((fid,feature))
        if (n<MIN_HISTORY or months<MIN_MONTHS or train+test!=n
            or train!=math.floor(n*TRAIN_FRACTION) or train<MIN_TRAIN
            or test<MIN_HOLDOUT or not(first<=last_train<first_test<=last)
            or max_gap_days>7 or max_gap_days<0):
            raise ValueError("Insufficient or temporally invalid independent days")
        if (bad!=0 or var_y is None or var_y<=0 or mse_baseline is None
            or mse_baseline<=0 or any(not isinstance(x,(int,float))
            or not math.isfinite(x) for x in (in_r2,out_r2,placebo_r2,
                                               var_y,mse_baseline))
            or not -1e-9<=in_r2<=1.000000001):
            raise ValueError("Nonfinite or falsely approved funding-factor research fit")
    if len({r[0] for r in rows})!=FACTOR_COUNT:
        raise ValueError("Incomplete rate factor universe")
    return {"model_pairs":len(rows),
            "positive_same_day":sum(r[11]>0 for r in rows),
            "positive_future_placebo":sum(r[12]>0 for r in rows),
            "min_holdout":min(r[4] for r in rows),
            "min_distinct_dates":min(r[2] for r in rows)}

def build(con):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE fund_levels AS
      SELECT effective_date,
        max(annual_rate_percent) FILTER(WHERE series_id='SOFR') AS sofr_percent,
        max(annual_rate_percent) FILTER(WHERE series_id='EFFR') AS effr_percent,
        max(source_json_sha256) FILTER(WHERE series_id='SOFR') AS sofr_sha,
        max(source_json_sha256) FILTER(WHERE series_id='EFFR') AS effr_sha,
        max(source_response_received_at) FILTER(WHERE series_id='SOFR') AS sofr_received_at,
        max(source_response_received_at) FILTER(WHERE series_id='EFFR') AS effr_received_at,
        count(*) AS rate_rows,
        count(*) FILTER(WHERE original_provider_published_at IS NOT NULL
          OR first_published_timestamp_verified
          OR provider_historical_revision_asof_verified
          OR downstream_license_approved OR production_risk_input_approved
          OR NOT research_only OR length(source_json_sha256)<>64) AS bad_claims
      FROM {P}lab_nyfed_rate_levels_latest_retro_v1
      GROUP BY 1 HAVING count(*)=2""")
    con.execute("""CREATE OR REPLACE TEMP TABLE fund_lagged AS
      SELECT *,100.0*(sofr_percent-effr_percent) AS basis_bps,
        lag(effective_date) OVER(ORDER BY effective_date) AS previous_day,
        lag(100.0*(sofr_percent-effr_percent))
          OVER(ORDER BY effective_date) AS prior_basis,
        lag(sofr_percent) OVER(ORDER BY effective_date) AS prior_sofr_percent
      FROM fund_levels""")
    con.execute("""CREATE OR REPLACE TEMP TABLE fund_basis AS
      SELECT effective_date,sofr_percent,effr_percent,basis_bps,
        previous_day,prior_basis AS prior_basis_bps,
        CASE WHEN date_diff('day',previous_day,effective_date)
          BETWEEN 1 AND 7 THEN basis_bps-prior_basis END AS basis_change_bps,
        CASE WHEN date_diff('day',previous_day,effective_date)
          BETWEEN 1 AND 7 THEN 100.0*(sofr_percent-prior_sofr_percent)
          END AS sofr_change_bps,
        sofr_sha,effr_sha,sofr_received_at,effr_received_at,
        bad_claims
      FROM fund_lagged""")
    # The *next date* market value below is explicitly forbidden as a live
    # model input. It is used only as an out-of-time negative control.
    con.execute("""CREATE OR REPLACE TEMP TABLE fund_with_future_placebo AS
      WITH leaded AS (
        SELECT *,
          lead(effective_date) OVER(ORDER BY effective_date) next_day,
          lead(basis_change_bps) OVER(ORDER BY effective_date) next_basis_change,
          lead(sofr_change_bps) OVER(ORDER BY effective_date) next_sofr_change
        FROM fund_basis
      )
      SELECT *,
        CASE WHEN date_diff('day',effective_date,next_day) BETWEEN 1 AND 7
          THEN next_basis_change END AS unavailable_next_basis_change,
        CASE WHEN date_diff('day',effective_date,next_day) BETWEEN 1 AND 7
          THEN next_sofr_change END AS unavailable_next_sofr_change
      FROM leaded""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE treasury_daily AS
      WITH current_source AS(
         SELECT f.factor_id,f.observed_date,f.value,f.unit,
           f.ingested_at,f.availability_at,f.record_sha256,
           row_number() OVER(PARTITION BY f.factor_id,f.observed_date
             ORDER BY f.ingested_at DESC,f.record_sha256 DESC,f.run_id DESC) rn
         FROM {P}lab_factor_observations f
         JOIN {P}lab_factor_catalog c USING(factor_id)
         WHERE c.active AND c.license_class NOT LIKE 'restricted%'
           AND f.unit=c.unit AND f.unit='percent'
       ), changes AS (
         SELECT *,
           lag(value) OVER(PARTITION BY factor_id ORDER BY observed_date) last_value,
           lag(observed_date) OVER(PARTITION BY factor_id ORDER BY observed_date) last_day
         FROM current_source WHERE rn=1
       )
       SELECT factor_id,observed_date,value,ingested_at,availability_at,
         record_sha256,
         CASE WHEN date_diff('day',last_day,observed_date) BETWEEN 1 AND 7
           THEN 100.0*(value-last_value) END AS treasury_change_bps
       FROM changes""")
    con.execute("""CREATE OR REPLACE TEMP TABLE matched_factor_funding AS
      SELECT t.factor_id,t.observed_date,t.treasury_change_bps AS y,
        feature.feature_id AS feature_name,
        feature.current_delta AS x,
        feature.future_delta AS future_x,
        date_diff('day',b.previous_day,b.effective_date) AS prior_rate_gap,
        b.bad_claims,
        t.ingested_at AS factor_warehouse_ingested_at,
        b.sofr_received_at,b.effr_received_at
      FROM treasury_daily t JOIN fund_with_future_placebo b
        ON t.observed_date=b.effective_date
      CROSS JOIN LATERAL(VALUES
        ('basis_change_bps',b.basis_change_bps,b.unavailable_next_basis_change),
        ('sofr_change_bps',b.sofr_change_bps,b.unavailable_next_sofr_change)
      ) feature(feature_id,current_delta,future_delta)
      WHERE t.treasury_change_bps IS NOT NULL
        AND feature.current_delta IS NOT NULL
        AND feature.future_delta IS NOT NULL
        AND isfinite(t.treasury_change_bps)
        AND isfinite(feature.current_delta)
        AND isfinite(feature.future_delta)""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE split_factor_funding AS
      WITH indexed AS (
        SELECT *,row_number() OVER(
           PARTITION BY factor_id,feature_name ORDER BY observed_date) ordinal,
         count(*) OVER(PARTITION BY factor_id,feature_name) n
        FROM matched_factor_funding)
      SELECT *,ordinal<=CAST(floor(n*{TRAIN_FRACTION}) AS BIGINT) train
      FROM indexed""")
    con.execute("""CREATE OR REPLACE TEMP TABLE train_funding_fits AS
      SELECT factor_id,feature_name,
         regr_intercept(y,x) AS intercept,
         regr_slope(y,x) AS slope,
         regr_r2(y,x) AS train_r2,
         regr_intercept(y,future_x) AS placebo_intercept,
         regr_slope(y,future_x) AS placebo_slope,
         avg(y) AS train_mean,
         var_samp(y) AS train_variance
      FROM split_factor_funding WHERE train
      GROUP BY 1,2 HAVING var_samp(y)>0 AND var_samp(x)>0
                       AND var_samp(future_x)>0""")
    con.execute("""CREATE OR REPLACE TEMP TABLE funding_oos_scores AS
      SELECT t.factor_id,t.feature_name,count(*) total,
        count(*) FILTER(WHERE t.train) train_n,
        count(*) FILTER(WHERE NOT t.train) test_n,
        count(DISTINCT date_trunc('month',t.observed_date)) months,
        min(t.observed_date) first_date,
        max(t.observed_date) FILTER(WHERE t.train) train_last,
        min(t.observed_date) FILTER(WHERE NOT t.train) test_first,
        max(t.observed_date) last_date,
        f.train_r2,
        1.0-(
          avg(power(t.y-f.intercept-f.slope*t.x,2))
            FILTER(WHERE NOT t.train) /
          nullif(avg(power(t.y-f.train_mean,2))
            FILTER(WHERE NOT t.train),0)) AS holdout_r2,
        1.0-(
          avg(power(t.y-f.placebo_intercept-f.placebo_slope*t.future_x,2))
            FILTER(WHERE NOT t.train) /
          nullif(avg(power(t.y-f.train_mean,2))
            FILTER(WHERE NOT t.train),0)) AS future_placebo_r2,
        f.train_variance,
        avg(power(t.y-f.train_mean,2))
          FILTER(WHERE NOT t.train) AS baseline_test_mse,
        max(t.prior_rate_gap) AS max_rate_gap,
        sum(t.bad_claims) AS invalid_source
      FROM split_factor_funding t JOIN train_funding_fits f
        USING(factor_id,feature_name)
      GROUP BY t.factor_id,t.feature_name,f.train_r2,
        f.intercept,f.slope,f.placebo_intercept,f.placebo_slope,
        f.train_mean,f.train_variance""")

def inspect(con):
    rate_check=con.execute("""SELECT count(*),count(DISTINCT effective_date),
          min(effective_date),max(effective_date),sum(bad_claims)
        FROM fund_basis""").fetchone()
    factor_check=con.execute("""SELECT count(DISTINCT factor_id),
       count(*) FILTER(WHERE record_sha256 IS NULL
         OR length(record_sha256)<>64 OR NOT isfinite(value)
         OR availability_at IS NULL OR ingested_at IS NULL)
       FROM treasury_daily""").fetchone()
    audit=con.execute(f"""SELECT distinct_effective_date_records,
      overlapping_retrieval_days,materially_revised_rate_days,
      CAST(original_release_vintages_approved AS INTEGER)+
      CAST(institutional_funding_shocks_approved AS INTEGER)
      FROM {P}lab_nyfed_rate_source_quality_builds_v1
      ORDER BY built_at DESC LIMIT 1""").fetchone()
    if not audit or not review_source(rate_check,factor_check,audit):
        raise ValueError("NYFed QA prerequisite missing")
    missing=con.execute("""SELECT count(*) FROM (
      SELECT factor_id,feature_name,observed_date,count(*) n
      FROM matched_factor_funding
      GROUP BY 1,2,3 HAVING count(*)>1)""").fetchone()[0]
    if missing:
        raise ValueError("Duplicate factor/date/feature rows are not independent")
    rows=con.execute("""SELECT factor_id,feature_name,total,train_n,test_n,
       months,first_date,train_last,test_first,last_date,train_r2,
       holdout_r2,future_placebo_r2,train_variance,baseline_test_mse,
       max_rate_gap,invalid_source
       FROM funding_oos_scores ORDER BY factor_id,feature_name""").fetchall()
    return rate_check,review_models(rows,rate_check[0]),rows

def tables(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_funding_basis_levels_retro_v1 AS
      SELECT ''::VARCHAR AS build_id, * EXCLUDE(bad_claims),
        FALSE::BOOLEAN AS original_published_at_verified,
        FALSE::BOOLEAN AS licensed_risk_factor_approved
      FROM fund_basis WHERE FALSE""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_funding_treasury_holdout_builds_v1(
      build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      distinct_funding_days BIGINT NOT NULL,
      distinct_factor_families BIGINT NOT NULL,
      exploratory_models BIGINT NOT NULL,
      minimum_paired_days_per_model BIGINT NOT NULL,
      minimum_holdout_days_per_model BIGINT NOT NULL,
      same_day_positive_skill_models BIGINT NOT NULL,
      future_feature_placebo_positive_skill_models BIGINT NOT NULL,
      source_first_published_at_verified BOOLEAN NOT NULL,
      causal_policy_surprise_approved BOOLEAN NOT NULL,
      institutional_security_beta_approved BOOLEAN NOT NULL,
      release_disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_funding_treasury_holdout_models_v1(
      build_id VARCHAR NOT NULL,factor_id VARCHAR NOT NULL,
      feature_name VARCHAR NOT NULL,paired_days BIGINT NOT NULL,
      training_days BIGINT NOT NULL,heldout_days BIGINT NOT NULL,
      distinct_months BIGINT NOT NULL,first_date DATE NOT NULL,
      training_last_date DATE NOT NULL,heldout_first_date DATE NOT NULL,
      last_date DATE NOT NULL,training_r2 DOUBLE NOT NULL,
      same_day_heldout_r2 DOUBLE NOT NULL,
      unavailable_future_feature_placebo_r2 DOUBLE NOT NULL,
      training_treasury_change_variance DOUBLE NOT NULL,
      heldout_mean_baseline_mse DOUBLE NOT NULL,
      maximum_rate_source_day_gap BIGINT NOT NULL,
      invalid_original_source_claims BIGINT NOT NULL,
      source_pit_verified BOOLEAN NOT NULL,
      institutional_risk_beta_approved BOOLEAN NOT NULL)""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40
        or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Require immutable pinned Git commit and internal-only scope")
    import duckdb
    run=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    scriptsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        build(con)
        rate,quality,models=inspect(con)
        tables(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_funding_basis_levels_retro_v1
                SELECT ?::VARCHAR, * EXCLUDE(bad_claims),
                FALSE,FALSE FROM fund_basis""",[run])
            con.execute(f"""INSERT INTO {P}lab_funding_treasury_holdout_builds_v1
                VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,
                'RETROSPECTIVE_FUNDING_RATE_AND_TREASURY_COMOVEMENT_ONLY')""",
                [run,sha,scriptsha,rate[0],FACTOR_COUNT,
                 quality["model_pairs"],quality["min_distinct_dates"],
                 quality["min_holdout"],quality["positive_same_day"],
                 quality["positive_future_placebo"]])
            con.executemany(f"""INSERT INTO {P}lab_funding_treasury_holdout_models_v1
                VALUES ({','.join('?' for _ in range(20))})""",
                [(run,*x,False,False) for x in models])
            con.execute(f"""CREATE OR REPLACE VIEW {P}lab_funding_basis_levels_retro_latest AS
                SELECT * FROM {P}lab_funding_basis_levels_retro_v1
                WHERE build_id=(SELECT build_id FROM
                  {P}lab_funding_treasury_holdout_builds_v1
                  ORDER BY built_at DESC LIMIT 1)""")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD={run} FUNDING_DAYS={rate[0]} TREASURY_FACTORS={FACTOR_COUNT}")
    print(f"MODELS={quality['model_pairs']} MIN_PAIRED_DAYS={quality['min_distinct_dates']} MIN_HOLDOUT={quality['min_holdout']}")
    print(f"POSITIVE_SAME_DAY_HOLDOUT={quality['positive_same_day']} POSITIVE_FUTURE_FEATURE_PLACEBO={quality['positive_future_placebo']}")
    print("PIT_CLOCK=UNVERIFIED POLICY_SURPRISE=NOT_IDENTIFIED SECURITY_BETA_RELEASE=FALSE")

if __name__=="__main__":
    main()
