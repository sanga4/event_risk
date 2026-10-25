#!/usr/bin/env python3
"""Market-controlled USD security exposure to SOFR-EFFR daily funding basis.

Retrospective diagnostic, NOT a tradable forecast, causal event impact,
independently point-in-time-validated security beta, or licensed production feed.
Two fits per security: all training days vs training excluding large funding
basis shifts and vendor price outliers; both evaluated on the SAME heldout dates.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib,math,os

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-security-funding-basis-v1.0.0"
EXPECTED_ASSETS=48
VARIANTS=frozenset(("all_training_days","trimmed_training_stress_and_price"))
MIN_MATCHED_DAYS=600
MIN_TRAIN=400
MIN_TEST=150
MIN_MONTHS=18
TRAIN_NUM=7
TRAIN_DEN=10
STRESS_ABS_BPS=10.0
MIN_RESIDUAL_FACTOR_VARIANCE=1e-6

def check_sources(sec,source_funding):
    """Validate no security-price/vendor or funding vintage source release claims."""
    if len(sec)!=6 or len(source_funding)!=5:
        raise ValueError("Changed security/funding source contract")
    n,assets,bench,invalid,duplicates,flagged=sec
    funding_days,funding_builds,first_clock,source_unapproved,funding_pit=source_funding
    if (n<30000 or assets!=EXPECTED_ASSETS or bench<600
        or invalid!=0 or duplicates!=0 or flagged<0 or flagged>n
        or funding_days<1500 or funding_builds!=1
        or first_clock is None or source_unapproved!=0 or funding_pit!=0):
        raise ValueError("Source prices, chronology, license or funding provenance invalid")
    return True

def assess(rows):
    if len(rows)!=EXPECTED_ASSETS*len(VARIANTS):
        raise ValueError("Missing or duplicated fitted security/funding research models")
    unique=set()
    for r in rows:
        # ticker,variant,n,train,test,months,first,train_last,test_first,last,
        # training_fit_count,excluded_training,market_slope,funding_slope,
        # train_basis_residual_var,market_oos_mse,augmented_oos_mse,
        # delta_oos_skill,holdout_flagged_rows,large_basis_training,
        # invalid_source_claims
        if len(r)!=21:
            raise ValueError("Funding exposure model schema changed")
        (ticker,variant,n,train,test,months,first,train_last,test_first,last,
         fit_count,trimmed,market_beta,fund_beta,resid_var,market_mse,
         augmented_mse,skill,holdout_bad,stress_train,invalid)=r
        if (not ticker or ticker=="SPY" or variant not in VARIANTS
            or (ticker,variant) in unique):
            raise ValueError("Unsupported or duplicated security/funding model")
        unique.add((ticker,variant))
        if (n<MIN_MATCHED_DAYS or train!=n*TRAIN_NUM//TRAIN_DEN
            or train<MIN_TRAIN or test<MIN_TEST or train+test!=n
            or months<MIN_MONTHS or not(first<=train_last<test_first<=last)
            or fit_count<MIN_TRAIN-40 or fit_count>train
            or trimmed!=train-fit_count or trimmed<0
            or holdout_bad<0 or holdout_bad>test
            or stress_train<0 or stress_train>train):
            raise ValueError("Insufficient or leaky chronological asset history")
        if (variant=="all_training_days" and trimmed!=0) or (
            variant=="trimmed_training_stress_and_price"
            and stress_train>0 and trimmed<stress_train):
            raise ValueError("Tail/price-exception sensitivity not faithfully implemented")
        numeric=(market_beta,fund_beta,resid_var,market_mse,
                 augmented_mse,skill)
        if (invalid!=0 or any(x is None or not isinstance(x,(int,float))
            or not math.isfinite(x) for x in numeric)
            or resid_var<=MIN_RESIDUAL_FACTOR_VARIANCE
            or market_mse<=0 or augmented_mse<0
            or abs(skill-(1.0-augmented_mse/market_mse))>1e-7):
            raise ValueError("Invalid OOS funding coefficient or release constraint")
    if len({r[0] for r in rows})!=EXPECTED_ASSETS:
        raise ValueError("Unexpected asset universe or absent funding estimates")
    return {"models":len(rows),"assets":EXPECTED_ASSETS,
            "positive_all":sum(r[17]>0 for r in rows if r[1]=="all_training_days"),
            "positive_trimmed":sum(r[17]>0 for r in rows if r[1]!="all_training_days"),
            "trimmed_changed":sum(r[11]>0 for r in rows if r[1]!="all_training_days"),
            "min_dates":min(r[2] for r in rows),"min_holdout":min(r[4] for r in rows)}

def build(con):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE fund_input AS
      SELECT effective_date,basis_change_bps,sofr_sha,effr_sha,
        sofr_received_at,effr_received_at
      FROM {P}lab_funding_basis_levels_retro_latest
      WHERE basis_change_bps IS NOT NULL AND isfinite(basis_change_bps)""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE security_matched AS
       SELECT r.ticker,r.observed_date,
        r.return_bps AS security_return_bps,
        m.return_bps AS market_return_bps,
        f.basis_change_bps AS funding_basis_delta_bps,
        abs(f.basis_change_bps)>={STRESS_ABS_BPS} AS funding_stress_day,
        r.large_absolute_log_return AS price_outlier_day,
        r.source AS security_source,r.source_run_id,
        r.fetched_at AS security_retrieved_at,
        f.sofr_sha,f.effr_sha,f.sofr_received_at,f.effr_received_at,
        r.source_availability_pit_verified,
        r.corporate_action_vintage_verified,
        r.data_use_class
      FROM {P}lab_security_returns_retro_v1 r
      JOIN {P}lab_security_returns_retro_v1 m
        ON r.observed_date=m.observed_date AND m.ticker='SPY'
      JOIN fund_input f ON r.observed_date=f.effective_date
      WHERE r.ticker<>'SPY'
        AND r.currency='USD' AND m.currency='USD'
        AND isfinite(r.return_bps) AND isfinite(m.return_bps)
      """)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE dated_sample AS
       SELECT *,row_number() OVER(PARTITION BY ticker
         ORDER BY observed_date) AS sample_ordinal,
         count(*) OVER(PARTITION BY ticker) AS matched_count
       FROM security_matched""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE split_sample AS
       SELECT *,
        sample_ordinal<=CAST(floor(matched_count*{TRAIN_NUM}.0/{TRAIN_DEN}) AS BIGINT)
          AS is_train
       FROM dated_sample""")
    con.execute("""CREATE OR REPLACE TEMP TABLE variant_train AS
       SELECT s.*,
         CASE WHEN choice.variant='all_training_days' THEN
           'all_training_days' ELSE 'trimmed_training_stress_and_price'
         END AS fit_variant
       FROM split_sample s
       CROSS JOIN (VALUES ('all_training_days'),
             ('trimmed_training_stress_and_price')) choice(variant)
       WHERE is_train
         AND (choice.variant='all_training_days'
             OR (NOT funding_stress_day AND NOT price_outlier_day))""")
    con.execute("""CREATE OR REPLACE TEMP TABLE coeff_inputs AS
       SELECT ticker,fit_variant,count(*) fit_n,
         avg(security_return_bps) avg_y,
         avg(market_return_bps) avg_m,
         avg(funding_basis_delta_bps) avg_x,
         var_pop(market_return_bps) var_m,
         var_pop(funding_basis_delta_bps) var_x,
         covar_pop(security_return_bps,market_return_bps) cov_ym,
         covar_pop(security_return_bps,funding_basis_delta_bps) cov_yx,
         covar_pop(market_return_bps,funding_basis_delta_bps) cov_mx
       FROM variant_train GROUP BY 1,2""")
    con.execute("""CREATE OR REPLACE TEMP TABLE coeffs AS
       WITH residual AS (
         SELECT *,
         (var_x-power(cov_mx,2)/nullif(var_m,0)) AS residual_x_var
         FROM coeff_inputs
       ), fit AS (
         SELECT *, (cov_yx-cov_ym*cov_mx/nullif(var_m,0))
           /nullif(residual_x_var,0) AS funding_slope
         FROM residual
       )
       SELECT *, (cov_ym-funding_slope*cov_mx)
         /nullif(var_m,0) AS market_slope,
         avg_y-(cov_ym-funding_slope*cov_mx)
           /nullif(var_m,0)*avg_m-funding_slope*avg_x AS model_intercept
       FROM fit""")
    # Market-only benchmark trained on identical FULL training date sample
    # for both variants; only the incremental basis fit is tail sensitive.
    con.execute("""CREATE OR REPLACE TEMP TABLE benchmark_fit AS
       SELECT ticker,
         regr_slope(security_return_bps,market_return_bps) AS market_beta,
         regr_intercept(security_return_bps,market_return_bps) AS intercept
       FROM split_sample WHERE is_train GROUP BY ticker""")
    con.execute("""CREATE OR REPLACE TEMP TABLE oos_metrics AS
       WITH scores AS (
         SELECT s.*,c.fit_variant,c.fit_n,c.market_slope,c.funding_slope,
          c.residual_x_var,
          power(s.security_return_bps-b.intercept
            -b.market_beta*s.market_return_bps,2) benchmark_error2,
          power(s.security_return_bps-c.model_intercept
            -c.market_slope*s.market_return_bps
            -c.funding_slope*s.funding_basis_delta_bps,2) enhanced_error2
         FROM split_sample s JOIN coeffs c USING(ticker)
         JOIN benchmark_fit b USING(ticker)
       )
       SELECT ticker,fit_variant,
         count(*) AS total,
         count(*) FILTER(WHERE is_train) AS train_n,
         count(*) FILTER(WHERE NOT is_train) AS test_n,
         count(DISTINCT date_trunc('month',observed_date)) AS n_months,
         min(observed_date) AS first_date,
         max(observed_date) FILTER(WHERE is_train) AS last_train,
         min(observed_date) FILTER(WHERE NOT is_train) AS first_test,
         max(observed_date) AS last_date,
         max(fit_n) AS effective_fit_count,
         count(*) FILTER(WHERE is_train)-max(fit_n) AS excluded_train,
         max(market_slope) AS market_slope,
         max(funding_slope) AS funding_slope,
         max(residual_x_var) AS residual_var,
         avg(benchmark_error2) FILTER(WHERE NOT is_train) AS benchmark_oos_mse,
         avg(enhanced_error2) FILTER(WHERE NOT is_train) AS enhanced_oos_mse,
         1.0-(avg(enhanced_error2) FILTER(WHERE NOT is_train))
               /nullif(avg(benchmark_error2) FILTER(WHERE NOT is_train),0)
             AS incremental_oos_skill,
         count(*) FILTER(WHERE NOT is_train AND price_outlier_day) AS heldout_flagged,
         count(*) FILTER(WHERE is_train AND funding_stress_day) AS training_stress_days,
         count(*) FILTER(WHERE source_availability_pit_verified OR
           corporate_action_vintage_verified OR
           data_use_class<>'retrospective_research_only'
           OR security_source<>'yahoo'
           OR length(sofr_sha)<>64 OR length(effr_sha)<>64) AS invalid_source
       FROM scores GROUP BY ticker,fit_variant""")

def inspect(con):
    sec=con.execute(f"""SELECT count(*),count(DISTINCT ticker) FILTER(WHERE ticker<>'SPY'),
      count(*) FILTER(WHERE ticker='SPY'),
      count(*) FILTER(WHERE currency<>'USD'
        OR source_availability_pit_verified
        OR corporate_action_vintage_verified
        OR data_use_class<>'retrospective_research_only'
        OR source<>'yahoo'
        OR NOT isfinite(return_bps)),
      (SELECT count(*) FROM(
        SELECT ticker,observed_date,count(*) n
        FROM {P}lab_security_returns_retro_v1 GROUP BY 1,2
        HAVING count(*)>1)),
      count(*) FILTER(WHERE large_absolute_log_return)
      FROM {P}lab_security_returns_retro_v1""").fetchone()
    fund=con.execute(f"""SELECT count(*),count(DISTINCT build_id),
       min(sofr_received_at),
       count(*) FILTER(WHERE original_published_at_verified
         OR licensed_risk_factor_approved
         OR length(sofr_sha)<>64 OR length(effr_sha)<>64),
       (SELECT count(*) FROM {P}lab_funding_treasury_holdout_builds_v1
          WHERE source_first_published_at_verified OR
          causal_policy_surprise_approved OR institutional_security_beta_approved)
       FROM {P}lab_funding_basis_levels_retro_latest""").fetchone()
    check_sources(sec,fund)
    duplicated=con.execute("""SELECT count(*) FROM
      (SELECT ticker,observed_date,count(*) n FROM security_matched
       GROUP BY ticker,observed_date HAVING count(*)>1)""").fetchone()[0]
    if duplicated: raise ValueError("Duplicate matched security dates")
    out=con.execute("""SELECT ticker,fit_variant,total,train_n,test_n,n_months,
       first_date,last_train,first_test,last_date,effective_fit_count,
       excluded_train,market_slope,funding_slope,residual_var,
       benchmark_oos_mse,enhanced_oos_mse,incremental_oos_skill,
       heldout_flagged,training_stress_days,invalid_source
       FROM oos_metrics ORDER BY ticker,fit_variant""").fetchall()
    return check_sources(sec,fund),assess(out),out

def schema(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_security_funding_exposure_builds_v1(
      build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
      code_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      securities BIGINT NOT NULL,research_model_variants BIGINT NOT NULL,
      minimum_matched_calendar_days BIGINT NOT NULL,
      minimum_heldout_calendar_days BIGINT NOT NULL,
      positive_incremental_oos_models_full BIGINT NOT NULL,
      positive_incremental_oos_models_tail_trimmed BIGINT NOT NULL,
      models_with_tail_or_price_training_removed BIGINT NOT NULL,
      issuer_first_publication_verified BOOLEAN NOT NULL,
      adjusted_price_corporate_actions_verified BOOLEAN NOT NULL,
      commercial_reuse_rights_cleared BOOLEAN NOT NULL,
      institutional_security_betas_released BOOLEAN NOT NULL,
      model_disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_security_funding_exposure_models_v1(
      build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
      fit_variant VARCHAR NOT NULL,matched_calendar_days BIGINT NOT NULL,
      train_calendar_days BIGINT NOT NULL,heldout_calendar_days BIGINT NOT NULL,
      distinct_months BIGINT NOT NULL,first_date DATE NOT NULL,
      train_through DATE NOT NULL,heldout_from DATE NOT NULL,
      last_date DATE NOT NULL,actual_fitted_train_days BIGINT NOT NULL,
      excluded_training_days BIGINT NOT NULL,
      spy_log_return_exposure DOUBLE NOT NULL,
      funding_basis_exposure_security_log_return_bps_per_funding_bp DOUBLE NOT NULL,
      train_funding_residual_variance DOUBLE NOT NULL,
      market_only_heldout_mse DOUBLE NOT NULL,
      market_plus_funding_heldout_mse DOUBLE NOT NULL,
      incremental_heldout_skill DOUBLE NOT NULL,
      heldout_large_adjusted_price_moves BIGINT NOT NULL,
      original_training_large_funding_moves BIGINT NOT NULL,
      invalid_source_claims BIGINT NOT NULL,
      original_source_pit_verified BOOLEAN NOT NULL,
      vendor_rights_and_adjustments_approved BOOLEAN NOT NULL,
      institutional_security_beta_approved BOOLEAN NOT NULL)""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or
        len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Pinned Git source commit and internal-only scope required")
    import duckdb
    run=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        build(con)
        _,summary,rows=inspect(con)
        schema(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_security_funding_exposure_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,FALSE,
                'RETROSPECTIVE_SPY_CONTROLLED_COMOVEMENT_NOT_RELEASED')""",
              [run,sha,digest,summary["assets"],summary["models"],
               summary["min_dates"],summary["min_holdout"],
               summary["positive_all"],summary["positive_trimmed"],
               summary["trimmed_changed"]])
            con.executemany(f"""INSERT INTO {P}lab_security_funding_exposure_models_v1
              VALUES ({','.join('?' for _ in range(25))})""",
              [(run,*row,False,False,False) for row in rows])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD={run} SECURITIES={summary['assets']} RESEARCH_VARIANTS={summary['models']}")
    print(f"PAIRED_DATE_MIN={summary['min_dates']} HOLDOUT_MIN={summary['min_holdout']}")
    print(f"POSITIVE_INCREMENTAL_SKILL_ALL={summary['positive_all']} TAIL_TRIMMED={summary['positive_trimmed']} TRIMMED_CHANGED={summary['trimmed_changed']}")
    print("PIT=FALSE LICENSES=FALSE CORPORATE_ACTION_VINTAGES=FALSE SECURITY_BETA_RELEASE=FALSE")

if __name__=="__main__":
    main()
