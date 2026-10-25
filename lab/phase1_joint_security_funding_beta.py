#!/usr/bin/env python3
"""Joint SPY + Treasury 2Y/10Y + SOFR-EFFR security exposure research.

Retrospective, contemporaneous association only. No provider first-publication
PIT, corporate-action vintage, redistribution license or institutional beta.
Conditioning, HAC errors, training-half sign stability and tail-sensitive
unchanged-date holdouts can REJECT a research fit; none grants approval.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import math
import os

import numpy as np

DB = "eventrisk_factor_lab"
P = DB + ".main."
VERSION = "phase1-joint-security-funding-v1.0.0"
FACTORS = ("DGS2", "DGS10")
N_ASSETS = 48
VARIANTS = ("full_training", "training_tail_exclusion")
MIN_N = 600
MIN_TRAIN = 400
MIN_TEST = 150
TRAIN_SHARE_NUM = 7
TRAIN_SHARE_DEN = 10
MAX_STANDARDIZED_CONDITION = 30.0
STRESS_BASIS_BPS = 10.0
HAC_LAGS = 5
MIN_TRIMMED_TRAIN = 350

def check_source(source, matched):
    """Require explicit research-only raw data and independent date keys."""
    if len(source) != 7 or len(matched) != 5:
        raise ValueError("Input contract drift")
    sec_n, assets, market_n, rates_n, fund_n, bad_source, bad_keys = source
    matched_n, n_assets, distinct_days, matched_bad, matched_dupes = matched
    if (sec_n < 80000 or assets != N_ASSETS or market_n < 600
        or rates_n != 1402 or fund_n < 1500 or bad_source or bad_keys
        or matched_n < 30000 or n_assets != N_ASSETS or distinct_days < MIN_N
        or matched_bad or matched_dupes):
        raise ValueError("Unapproved, incomplete or duplicated input source")
    return True

def model_fit(x_train, y_train, x_test, y_test, x_benchmark_train=None):
    """OLS with centered/scaled training predictors and Bartlett HAC errors.

    Feature order: SPY log-return bp, DGS2 yield bp, DGS10 yield bp,
    SOFR-EFFR funding-basis change bp. No separate hidden model selection.
    """
    x_train = np.asarray(x_train, dtype=float)
    y_train = np.asarray(y_train, dtype=float)
    x_test = np.asarray(x_test, dtype=float)
    y_test = np.asarray(y_test, dtype=float)
    if (x_train.ndim != 2 or x_train.shape[1] != 4
        or x_test.ndim != 2 or x_test.shape[1] != 4
        or len(x_train) != len(y_train) or len(x_test) != len(y_test)
        or len(y_train) < MIN_TRIMMED_TRAIN or len(y_test) < MIN_TEST
        or not all(np.isfinite(a).all() for a in
                   (x_train, y_train, x_test, y_test))):
        raise ValueError("Invalid independent training/holdout shapes or values")
    mean = x_train.mean(axis=0)
    sd = x_train.std(axis=0)
    if np.any(sd < 1e-8):
        raise ValueError("Zero-variance or unidentifiable source factor")
    z = (x_train - mean) / sd
    xt = (x_test - mean) / sd
    design = np.column_stack((np.ones(len(z)), z))
    ztest = np.column_stack((np.ones(len(xt)), xt))
    condition = float(np.linalg.cond(design))
    if not math.isfinite(condition) or condition > MAX_STANDARDIZED_CONDITION:
        raise ValueError("Joint factor multicollinearity: condition threshold")
    coef, _, rank, _ = np.linalg.lstsq(design, y_train, rcond=None)
    if rank != 5:
        raise ValueError("Insufficient joint factor rank")
    error = y_train - design @ coef
    bread = np.linalg.inv(design.T @ design)
    weighted = design * error[:, None]
    meat = weighted.T @ weighted
    for lag in range(1, min(HAC_LAGS, len(y_train)-1) + 1):
        cross = weighted[lag:].T @ weighted[:-lag]
        meat += (1.0 - lag/(HAC_LAGS+1.0)) * (cross + cross.T)
    cov = (len(y_train) / (len(y_train) - 5)) * bread @ meat @ bread
    se = float(np.sqrt(max(0.0, cov[-1, -1])) / sd[-1])
    beta = coef[1:] / sd
    intercept = float(coef[0] - mean @ beta)
    funding_beta = float(beta[-1])
    n = len(y_train)
    # Identical TRAINING rows for joint and control-only comparator;
    # holdout dates and outcomes are identical for both.
    base_train = design[:, :-1]
    base_test = ztest[:, :-1]
    base_coef, _, base_rank, _ = np.linalg.lstsq(base_train, y_train, rcond=None)
    if base_rank != 4:
        raise ValueError("Unidentified market+Treasury comparator")
    mse_base = float(np.mean((y_test - base_test @ base_coef)**2))
    mse_joint = float(np.mean((y_test - ztest @ coef)**2))
    if mse_base <= 0:
        raise ValueError("Degenerate held-out benchmark")
    skill = 1.0 - mse_joint/mse_base

    # Training-half sign stability never uses untouched holdout dates.
    half = n//2
    half_slopes = []
    for xx, yy in ((x_train[:half], y_train[:half]),
                   (x_train[half:], y_train[half:])):
        hm = xx.mean(axis=0)
        hs = xx.std(axis=0)
        if np.any(hs < 1e-8):
            half_slopes.append(float("nan"))
            continue
        hz = np.column_stack((np.ones(len(xx)), (xx-hm)/hs))
        hc, _, hrank, _ = np.linalg.lstsq(hz, yy, rcond=None)
        half_slopes.append(float(hc[-1]/hs[-1]) if hrank == 5 else float("nan"))
    stable = bool(all(math.isfinite(t) for t in half_slopes)
                  and np.sign(half_slopes[0]) == np.sign(half_slopes[1])
                  and np.sign(half_slopes[0]) == np.sign(funding_beta)
                  and abs(funding_beta) > 0)
    ci_low, ci_high = funding_beta - 1.96*se, funding_beta + 1.96*se
    separated = bool(ci_low > 0 or ci_high < 0)
    research_status = (
        "RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL" if
        skill > 0 and stable and separated else
        "REJECT_NEGATIVE_HOLDOUT_SKILL" if skill <= 0 else
        "REJECT_TRAINING_HALVES_SIGN_UNSTABLE" if not stable else
        "REJECT_HAC_INTERVAL_INCLUDES_ZERO")
    values = [condition, intercept, *beta.tolist(), se, ci_low, ci_high,
              half_slopes[0], half_slopes[1], mse_base, mse_joint, skill]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Nonfinite joint factor beta or uncertainty")
    return dict(condition=condition, intercept=intercept,
                market_beta=float(beta[0]), dgs2_beta=float(beta[1]),
                dgs10_beta=float(beta[2]), funding_beta=funding_beta,
                funding_hac_se=se, ci_low=float(ci_low), ci_high=float(ci_high),
                first_half_beta=float(half_slopes[0]),
                second_half_beta=float(half_slopes[1]),
                sign_stable=stable, baseline_mse=mse_base,
                joint_mse=mse_joint, incremental_skill=skill,
                research_status=research_status)

def compute_all(rows):
    """Prespecified two variants per ticker; no holdout-tuning or winner picking."""
    from collections import defaultdict
    grouped = defaultdict(list)
    seen = set()
    for record in rows:
        if len(record) != 9:
            raise ValueError("Changed factor-date record shape")
        ticker, day, y, market, d2, d10, funding, flagged, invalid = record
        if (not ticker or ticker=="SPY" or (ticker, day) in seen
            or invalid or flagged not in (True, False, 0, 1)
            or not all(math.isfinite(float(v)) for v in
                       (y, market, d2, d10, funding))):
            raise ValueError("Duplicate key, invalid response or false PIT claim")
        seen.add((ticker, day))
        grouped[ticker].append(record)
    if len(grouped) != N_ASSETS:
        raise ValueError("Unexpected security universe")
    result = []
    for ticker in sorted(grouped):
        sample = sorted(grouped[ticker], key=lambda r: r[1])
        n = len(sample)
        train = (n * TRAIN_SHARE_NUM)//TRAIN_SHARE_DEN
        if n < MIN_N or train < MIN_TRAIN or n-train < MIN_TEST:
            raise ValueError("Insufficient unique aligned dates")
        dates = [r[1] for r in sample]
        if len({(d.year,d.month) for d in dates}) < 18:
            raise ValueError("Insufficient history months")
        x = np.array([[float(v) for v in r[3:7]] for r in sample])
        y = np.array([float(r[2]) for r in sample])
        excluded = np.array([bool(r[7]) or abs(float(r[6])) >= STRESS_BASIS_BPS
                              for r in sample],dtype=bool)
        for variant in VARIANTS:
            mask = np.ones(train, dtype=bool) if variant=="full_training" else ~excluded[:train]
            if mask.sum()<MIN_TRIMMED_TRAIN:
                raise ValueError("Training tail exclusions made sample insufficient")
            fit = model_fit(x[:train][mask], y[:train][mask],
                            x[train:], y[train:])
            result.append(dict(ticker=ticker, variant=variant,
                n=n, n_train=train, n_fit=int(mask.sum()), n_holdout=n-train,
                first=dates[0], train_last=dates[train-1],
                holdout_first=dates[train], last=dates[-1],
                excluded_train=int(train-mask.sum()),
                flagged_holdout=int(sum(bool(r[7]) for r in sample[train:])),
                **fit))
    if len(result)!=N_ASSETS*len(VARIANTS):
        raise ValueError("Research model coverage changed")
    return result

def sql_inputs(con):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE joint_asset_input AS
      WITH treasury AS (
         SELECT observed_date,
           max(shock_bps) FILTER(WHERE factor_id='DGS2') AS d2,
           max(shock_bps) FILTER(WHERE factor_id='DGS10') AS d10,
           count(*) AS n_factors,
           count(*) FILTER(WHERE published_vintage_independently_verified
             OR data_use_class<>'retrospective_research_only'
             OR length(source_record_sha256)<>64 OR NOT isfinite(shock_bps)
             OR source_availability_at IS NULL OR source_ingested_at IS NULL) AS bad
         FROM {P}lab_rate_shocks_retro_v1
         WHERE factor_id IN ('DGS2','DGS10')
         GROUP BY observed_date
       )
       SELECT r.ticker,r.observed_date,r.return_bps y,m.return_bps market,
         t.d2,t.d10,f.basis_change_bps funding,
         r.large_absolute_log_return flagged,
         CAST(r.source_availability_pit_verified OR r.corporate_action_vintage_verified
           OR r.data_use_class<>'retrospective_research_only'
           OR r.source<>'yahoo' OR r.currency<>'USD'
           OR m.source_availability_pit_verified OR m.corporate_action_vintage_verified
           OR m.data_use_class<>'retrospective_research_only'
           OR f.original_published_at_verified OR f.licensed_risk_factor_approved
           OR length(f.sofr_sha)<>64 OR length(f.effr_sha)<>64
           OR t.n_factors<>2 OR t.bad>0 AS BIGINT) invalid
       FROM {P}lab_security_returns_retro_v1 r
       JOIN {P}lab_security_returns_retro_v1 m
         ON r.observed_date=m.observed_date AND m.ticker='SPY'
       JOIN treasury t ON r.observed_date=t.observed_date
       JOIN {P}lab_funding_basis_levels_retro_latest f
         ON r.observed_date=f.effective_date
       WHERE r.ticker<>'SPY' AND t.n_factors=2 AND
         f.basis_change_bps IS NOT NULL
         AND isfinite(r.return_bps) AND isfinite(m.return_bps)
         AND isfinite(t.d2) AND isfinite(t.d10)
         AND isfinite(f.basis_change_bps)""")
    sec=con.execute(f"""SELECT count(*),
       count(DISTINCT ticker) FILTER(WHERE ticker<>'SPY'),
       count(*) FILTER(WHERE ticker='SPY'),
       count(*) FILTER(WHERE source_availability_pit_verified
          OR corporate_action_vintage_verified OR currency<>'USD'
          OR source<>'yahoo' OR data_use_class<>'retrospective_research_only'),
       (SELECT count(*) FROM(SELECT ticker,observed_date,count(*) n
          FROM {P}lab_security_returns_retro_v1 GROUP BY 1,2 HAVING n>1))
       FROM {P}lab_security_returns_retro_v1""").fetchone()
    rate=con.execute(f"""SELECT count(*),count(*) FILTER(WHERE
       published_vintage_independently_verified OR
       data_use_class<>'retrospective_research_only'
       OR length(source_record_sha256)<>64)
       FROM {P}lab_rate_shocks_retro_v1 WHERE factor_id IN ('DGS2','DGS10')""").fetchone()
    fund=con.execute(f"""SELECT count(*),count(*) FILTER(WHERE
      original_published_at_verified OR licensed_risk_factor_approved)
      FROM {P}lab_funding_basis_levels_retro_latest""").fetchone()
    match=con.execute("""SELECT count(*),count(DISTINCT ticker),
       count(DISTINCT observed_date),
       count(*) FILTER(WHERE invalid<>0),
       (SELECT count(*) FROM (SELECT ticker,observed_date,count(*) n
          FROM joint_asset_input GROUP BY 1,2 HAVING n>1))
       FROM joint_asset_input""").fetchone()
    check_source((*sec[:3],rate[0],fund[0],
                  sec[3]+rate[1]+fund[1],sec[4]),match)
    data=con.execute("""SELECT ticker,observed_date,y,market,d2,d10,
      funding,flagged,invalid FROM joint_asset_input
      ORDER BY ticker,observed_date""").fetchall()
    return data

def schema(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_security_funding_builds_v1(
       build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
       source_code_sha256 VARCHAR NOT NULL,source_rows_sha256 VARCHAR NOT NULL,
       built_at TIMESTAMPTZ NOT NULL,securities BIGINT NOT NULL,
       fitted_research_models BIGINT NOT NULL,
       minimum_joined_dates BIGINT NOT NULL,minimum_holdout_dates BIGINT NOT NULL,
       positive_incremental_holdout_models BIGINT NOT NULL,
       research_screen_pass_models BIGINT NOT NULL,
       issuer_pit_verified BOOLEAN NOT NULL,
       adjusted_prices_independently_verified BOOLEAN NOT NULL,
       vendor_rights_cleared BOOLEAN NOT NULL,
       institutional_beta_release BOOLEAN NOT NULL,
       disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_security_funding_models_v1(
       build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
       variant VARCHAR NOT NULL,matched_dates BIGINT NOT NULL,
       training_dates BIGINT NOT NULL,fit_training_dates BIGINT NOT NULL,
       heldout_dates BIGINT NOT NULL,first_day DATE NOT NULL,
       train_last_day DATE NOT NULL,heldout_first_day DATE NOT NULL,
       last_day DATE NOT NULL,excluded_training_days BIGINT NOT NULL,
       flagged_heldout_price_days BIGINT NOT NULL,
       standardized_design_condition DOUBLE NOT NULL,
       market_spy_beta DOUBLE NOT NULL,dgs2_yield_change_beta DOUBLE NOT NULL,
       dgs10_yield_change_beta DOUBLE NOT NULL,
       funding_basis_beta DOUBLE NOT NULL,
       funding_hac_nw5_se DOUBLE NOT NULL,
       funding_ci95_low DOUBLE NOT NULL,funding_ci95_high DOUBLE NOT NULL,
       training_first_half_funding_beta DOUBLE NOT NULL,
       training_second_half_funding_beta DOUBLE NOT NULL,
       training_halves_sign_stable BOOLEAN NOT NULL,
       market_and_treasury_heldout_mse DOUBLE NOT NULL,
       joint_market_treasury_funding_heldout_mse DOUBLE NOT NULL,
       incremental_heldout_skill DOUBLE NOT NULL,
       research_screen_status VARCHAR NOT NULL,
       issuer_pit_verified BOOLEAN NOT NULL,
       vendor_adjustments_and_rights_approved BOOLEAN NOT NULL,
       institutional_beta_released BOOLEAN NOT NULL)""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40
        or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Require pinned SHA and internal-only research scope")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        rows=sql_inputs(con)
        fitted=compute_all(rows)  # strict fail-closed before any persistent mutation
        source_hash=hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()
        schema(con)
        colnames=("ticker","variant","n","n_train","n_fit","n_holdout",
                  "first","train_last","holdout_first","last","excluded_train",
                  "flagged_holdout","condition","market_beta","dgs2_beta",
                  "dgs10_beta","funding_beta","funding_hac_se","ci_low",
                  "ci_high","first_half_beta","second_half_beta","sign_stable",
                  "baseline_mse","joint_mse","incremental_skill","research_status")
        payload=[(build,*[x[k] for k in colnames],False,False,False) for x in fitted]
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_joint_security_funding_builds_v1
               VALUES(?,?,?,?,current_timestamp,?,?,?,?,?,?,FALSE,FALSE,FALSE,FALSE,
               'RETROSPECTIVE_MULTI_FACTOR_RESEARCH_ONLY')""",
               [build,sha,digest,source_hash,N_ASSETS,len(fitted),
                min(x["n"] for x in fitted),min(x["n_holdout"] for x in fitted),
                sum(x["incremental_skill"]>0 for x in fitted),
                sum(x["research_status"]=="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL"
                    for x in fitted)])
            con.executemany(f"""INSERT INTO {P}lab_joint_security_funding_models_v1
               VALUES({','.join('?' for _ in range(31))})""",payload)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD={build} ASSETS={N_ASSETS} MODELS={len(fitted)} SOURCE_ROWS={len(rows)}")
    print(f"MIN_DATES={min(x['n'] for x in fitted)} MIN_TEST={min(x['n_holdout'] for x in fitted)}")
    print(f"POSITIVE_OOS={sum(x['incremental_skill']>0 for x in fitted)} RESEARCH_SCREEN_PASS={sum(x['research_status']=='RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL' for x in fitted)}")
    print("SOURCE_PIT=FALSE VENDOR_RIGHTS=FALSE CORPORATE_ACTION_APPROVAL=FALSE INSTITUTIONAL_BETA=FALSE")

if __name__=="__main__":
    main()
