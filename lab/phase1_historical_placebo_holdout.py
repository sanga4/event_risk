#!/usr/bin/env python3
"""Held-out negative-control study of backfilled market and Treasury factor changes.

This is NOT a point-in-time, causal, production, forecast or tradable model.
The "future" market feature is a deliberately unavailable-at-date placebo
and must never become an operational signal or fitted live feature.
"""
from __future__ import annotations
import hashlib
import math
import os
from datetime import datetime,timezone
from pathlib import Path

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-retro-placebo-holdout-v1.0.0"
EXPECTED_FACTORS=18
EXPECTED_VENUES=("kalshi","polymarket")
MIN_HISTORY=450
MIN_MONTHS=18
TRAIN_SHARE=.70
MIN_TRAIN=300
MIN_TEST=120


def assess(source_manifest,models):
    """Reject invalid chronology, upstream claims and spurious release states.

    Model tuple: venue,factor_id,source_n,train_n,test_n,months,
    first_day,train_last,test_first,last_day,train_r2,
    model_holdout_r2,placebo_holdout_r2,
    train_y_variance,baseline_holdout_mse,unknown_source_claims.
    """
    if len(source_manifest)!=5:
        raise ValueError("Unexpected historic source manifest")
    source_id,venue_rows,model_rows,pit_rows,release_state=source_manifest
    if (not source_id or venue_rows<2900 or model_rows!=EXPECTED_FACTORS*2
        or pit_rows!=0 or release_state!="RETROSPECTIVE_RESEARCH_NOT_RELEASED"):
        raise ValueError("Missing or falsely certified historical source build")
    if len(models)!=EXPECTED_FACTORS*len(EXPECTED_VENUES):
        raise ValueError("Missing factor/venue models")
    seen=set()
    summary=[]
    for r in models:
        if len(r)!=16:
            raise ValueError("Unexpected out-of-time model schema")
        (venue,factor,n,ntrain,ntest,months,first,last_train,first_test,last,
         train_r2,model_r2,placebo_r2,train_y_var,baseline_mse,invalid)=r
        if venue not in EXPECTED_VENUES or not factor or (venue,factor) in seen:
            raise ValueError("Duplicate or unsupported factor/venue research cell")
        seen.add((venue,factor))
        if (n<MIN_HISTORY or months<MIN_MONTHS
            or ntrain+ntest!=n
            or ntrain!=math.floor(TRAIN_SHARE*n)
            or ntrain<MIN_TRAIN or ntest<MIN_TEST
            or not(first<=last_train<first_test<=last)):
            raise ValueError("Leaky or insufficient chronological training/holdout sample")
        if (invalid!=0 or train_y_var is None or train_y_var<=0
            or baseline_mse is None or baseline_mse<=0
            or any(x is None or not math.isfinite(x) for x in
                   (train_r2,model_r2,placebo_r2,train_y_var,baseline_mse))
            or not -1e-10<=train_r2<=1.0000000001):
            raise ValueError("Nonfinite metrics or unverified source/time contract")
        summary.append(tuple(r[:-1])+
                       (model_r2>0,placebo_r2>0,
                        "RETROSPECTIVE_HOLDOUT_ONLY_FUTURE_X_IS_UNAVAILABLE_PLACEBO"))
    if {x[0] for x in summary}!=set(EXPECTED_VENUES):
        raise ValueError("Venue coverage mismatch")
    if len({x[1] for x in summary})!=EXPECTED_FACTORS:
        raise ValueError("Factor family coverage mismatch")
    return summary


def construct(con):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE p1_factor_latest AS
      WITH candidates AS (
        SELECT f.factor_id,f.observed_date,f.value,f.unit,
          row_number() OVER(
            PARTITION BY f.factor_id,f.observed_date
            ORDER BY f.ingested_at DESC,f.record_sha256 DESC,f.run_id DESC
          ) rk
        FROM {P}lab_factor_observations f
        JOIN {P}lab_factor_catalog c USING(factor_id)
        WHERE c.active=TRUE AND c.license_class NOT LIKE 'restricted%'
          AND f.unit=c.unit AND isfinite(f.value)
      ), shifts AS (
        SELECT factor_id,observed_date,unit,value,
          lag(value) OVER(PARTITION BY factor_id ORDER BY observed_date) prev_value,
          lag(observed_date) OVER(PARTITION BY factor_id ORDER BY observed_date) prev_day
        FROM candidates WHERE rk=1
      )
      SELECT factor_id,observed_date,unit,
        CASE WHEN date_diff('day',prev_day,observed_date) BETWEEN 1 AND 7
          THEN CASE WHEN unit='percent' THEN 100.0*(value-prev_value)
                    ELSE value-prev_value END ELSE NULL END y
      FROM shifts""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE p1_venue_leads AS
      SELECT venue,observed_date,mean_absolute_delta_pp AS x,
        n_comparable_markets,
        lead(mean_absolute_delta_pp) OVER(PARTITION BY venue ORDER BY observed_date) AS next_x,
        lead(observed_date) OVER(PARTITION BY venue ORDER BY observed_date) AS next_day
      FROM {P}lab_venue_daily_features_v1""")
    con.execute("""CREATE OR REPLACE TEMP TABLE p1_matched_placebo AS
      SELECT v.venue,f.factor_id,f.unit,v.observed_date,
        v.x,v.next_x,f.y,
        row_number() OVER(PARTITION BY v.venue,f.factor_id
          ORDER BY v.observed_date) AS session_rank,
        count(*) OVER(PARTITION BY v.venue,f.factor_id) AS total_sessions
      FROM p1_factor_latest f JOIN p1_venue_leads v USING(observed_date)
      WHERE v.n_comparable_markets>=10
        AND v.x IS NOT NULL AND v.next_x IS NOT NULL
        AND date_diff('day',v.observed_date,v.next_day) BETWEEN 1 AND 7
        AND f.y IS NOT NULL AND isfinite(f.y)
        AND isfinite(v.x) AND isfinite(v.next_x)""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE p1_chronological AS
      SELECT *,session_rank<=CAST(floor(total_sessions*{TRAIN_SHARE}) AS BIGINT)
        AS is_train
      FROM p1_matched_placebo""")
    con.execute("""CREATE OR REPLACE TEMP TABLE p1_train_fits AS
      SELECT venue,factor_id,
         regr_slope(y,x) AS ordinary_slope,
         regr_intercept(y,x) AS ordinary_intercept,
         regr_r2(y,x) AS ordinary_train_r2,
         regr_slope(y,next_x) AS future_x_placebo_slope,
         regr_intercept(y,next_x) AS future_x_placebo_intercept,
         var_samp(y) AS train_y_variance,
         avg(y) AS train_y_mean
      FROM p1_chronological
      WHERE is_train
      GROUP BY 1,2
      HAVING var_samp(x)>0 AND var_samp(y)>0 AND var_samp(next_x)>0""")
    con.execute("""CREATE OR REPLACE TEMP TABLE p1_test_results AS
      SELECT t.venue,t.factor_id,count(*) AS source_n,
        count(*) FILTER(WHERE t.is_train) AS train_n,
        count(*) FILTER(WHERE NOT t.is_train) AS test_n,
        count(DISTINCT date_trunc('month',t.observed_date)) AS months,
        min(t.observed_date) AS first_day,
        max(t.observed_date) FILTER(WHERE t.is_train) AS train_last,
        min(t.observed_date) FILTER(WHERE NOT t.is_train) AS test_first,
        max(t.observed_date) AS last_day,
        f.ordinary_train_r2 AS train_r2,
        1.0-(
          avg(power(t.y-f.ordinary_intercept-f.ordinary_slope*t.x,2))
            FILTER(WHERE NOT t.is_train)
          /nullif(avg(power(t.y-f.train_y_mean,2))
            FILTER(WHERE NOT t.is_train),0)) AS model_holdout_r2,
        1.0-(
          avg(power(t.y-f.future_x_placebo_intercept
              -f.future_x_placebo_slope*t.next_x,2))
            FILTER(WHERE NOT t.is_train)
          /nullif(avg(power(t.y-f.train_y_mean,2))
            FILTER(WHERE NOT t.is_train),0)) AS future_x_placebo_holdout_r2,
        f.train_y_variance,
        avg(power(t.y-f.train_y_mean,2))
            FILTER(WHERE NOT t.is_train) AS baseline_holdout_mse,
        0::BIGINT AS invalid_source_claims
      FROM p1_chronological t JOIN p1_train_fits f USING(venue,factor_id)
      GROUP BY t.venue,t.factor_id,f.ordinary_train_r2,
        f.ordinary_intercept,f.ordinary_slope,
        f.future_x_placebo_intercept,f.future_x_placebo_slope,
        f.train_y_variance,f.train_y_mean""")
    # Preserve one distinct session/date per factor/venue; never count
    # market-proposition duplicates as independent factor returns.


def sources(con):
    source=con.execute(f"""SELECT build_id,venue_daily_rows,
        exploratory_regression_rows,point_in_time_eligible_rows,release_state
      FROM {P}lab_history_build_runs_v1 ORDER BY built_at DESC LIMIT 1""").fetchone()
    if not source:
        raise ValueError("Missing baseline historical input manifest")
    corrupt=con.execute(f"""SELECT
      (SELECT count(*) FROM {P}lab_venue_daily_features_v1
         WHERE point_in_time_verified OR
               snapshot_provenance<>'historical_event_time_not_availability_time'),
      (SELECT count(*) FROM {P}lab_exploratory_regressions_v1
         WHERE point_in_time_verified OR approved_for_decision_use)
    """).fetchone()
    if any(corrupt):
        raise ValueError("Historically backfilled input has false PIT approval")
    return source


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_historical_placebo_holdout_builds_v1(
      build_id VARCHAR NOT NULL,source_build VARCHAR NOT NULL,
      source_git_sha VARCHAR NOT NULL,source_script_sha256 VARCHAR NOT NULL,
      built_at TIMESTAMPTZ NOT NULL,model_pairs BIGINT NOT NULL,
      models_positive_same_day_test_r2 BIGINT NOT NULL,
      models_positive_future_feature_placebo_test_r2 BIGINT NOT NULL,
      original_source_pit_certified BOOLEAN NOT NULL,
      institutional_causal_mapping_approved BOOLEAN NOT NULL,
      release_status VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_historical_placebo_holdout_models_v1(
      build_id VARCHAR NOT NULL,venue VARCHAR NOT NULL,factor_id VARCHAR NOT NULL,
      paired_sessions BIGINT NOT NULL,training_sessions BIGINT NOT NULL,
      heldout_sessions BIGINT NOT NULL,distinct_months BIGINT NOT NULL,
      first_date DATE NOT NULL,training_last_date DATE NOT NULL,
      heldout_first_date DATE NOT NULL,last_date DATE NOT NULL,
      training_r2 DOUBLE NOT NULL,
      heldout_r2_against_training_mean DOUBLE NOT NULL,
      future_feature_placebo_holdout_r2 DOUBLE NOT NULL,
      training_factor_variance DOUBLE NOT NULL,
      heldout_baseline_mse DOUBLE NOT NULL,
      positive_heldout_signal BOOLEAN NOT NULL,
      positive_future_feature_placebo BOOLEAN NOT NULL,
      methodology_class VARCHAR NOT NULL,
      original_source_pit_certified BOOLEAN NOT NULL,
      approved_for_institutional_risk BOOLEAN NOT NULL)""")


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(k not in "0123456789abcdef" for k in sha):
        raise RuntimeError("Pinned code and internal research-only scope required")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        source=sources(con)
        construct(con)
        model_rows=con.execute("""SELECT venue,factor_id,source_n,train_n,test_n,
          months,first_day,train_last,test_first,last_day,train_r2,
          model_holdout_r2,future_x_placebo_holdout_r2,
          train_y_variance,baseline_holdout_mse,invalid_source_claims
          FROM p1_test_results ORDER BY venue,factor_id""").fetchall()
        models=assess(source,model_rows)
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_historical_placebo_holdout_builds_v1
               VALUES (?,?,?,?,current_timestamp,?,?,?,FALSE,FALSE,
               'BACKFILLED_OBSERVATIONS_EX_POST_NO_EVENT_CAUSAL_RELEASE')""",
                [build,source[0],sha,digest,len(models),
                 sum(r[15] for r in models),sum(r[16] for r in models)])
            con.executemany(f"""INSERT INTO {P}lab_historical_placebo_holdout_models_v1
               VALUES ({','.join('?' for _ in range(21))})""",
               [(build,*r,False,False) for r in models])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} PAIRS={len(models)} SOURCE_HISTORY={source[0]}")
    print(f"OUT_OF_TIME_POSITIVE_MODEL_R2={sum(r[15] for r in models)} FUTURE_MARKET_FEATURE_PLACEBO_POSITIVE_R2={sum(r[16] for r in models)}")
    print(f"HELDOUT_DATE_FIRST={min(r[8] for r in models)} LAST={max(r[9] for r in models)}")
    print("PROVIDER_AS_KNOWN=FALSE NEGATIVE_CONTROL_NOT_TRADEABLE=TRUE EVENT_CAUSAL_APPROVAL=FALSE")


if __name__=="__main__":
    main()
