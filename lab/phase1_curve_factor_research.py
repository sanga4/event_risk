#!/usr/bin/env python3
"""Research-only USD security exposures to interpretable Treasury curve shocks.

Three factors from DGS2/DGS5/DGS10 daily yield changes (basis points):
  LEVEL = (DGS2 + DGS5 + DGS10) / 3
  SLOPE = DGS10 - DGS2
  CURVATURE = 2*DGS5 - DGS2 - DGS10
with contemporaneous SPY adjusted-price log-return as control.

OLS with full multivariate Newey-West/Bartlett HAC(5) covariance, rank /
training-only standardised condition checks, chronological 70/30 test,
SPY-only holdout comparator and BH adjustment of all researched curve slopes.
THIS IS RETROSPECTIVE DATA WITH UNCERTIFIED ADJUSTMENTS, RIGHTS AND VINTAGES.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path

import duckdb
import numpy as np

P = "eventrisk_factor_lab.main."
VERSION = "phase1-curve-factor-betas-v1.0.0"
COMPONENTS = ("LEVEL", "SLOPE", "CURVATURE")
LAGS = 5
MIN_N = 300
MAX_STANDARDIZED_CONDITION = 1000.0


def bh_adjust(p_values):
    """Benjamini-Hochberg across the entire pre-specified model family."""
    result = [None] * len(p_values)
    eligible = sorted(
        (float(p), i) for i, p in enumerate(p_values)
        if p is not None and math.isfinite(p) and 0 <= p <= 1
    )
    prev = 1.0
    for rank in range(len(eligible) - 1, -1, -1):
        p, i = eligible[rank]
        prev = min(prev, p * len(eligible) / (rank + 1))
        result[i] = prev
    return result


def fit_curve(rows):
    """rows (day, asset_return_bps, spy_return_bps, L_bps, S_bps, C_bps, outlier).

    Ex-post contemporaneous explanatory exposures, NEVER a tradable forecast.
    """
    n = len(rows)
    split = int(n * 0.7)
    if n < MIN_N or split < 210 or n - split < 80:
        return None
    arr = np.asarray([r[1:6] for r in rows], dtype=float)
    if not np.isfinite(arr).all():
        return None
    y = arr[:, 0]
    x = np.column_stack((np.ones(n), arr[:, 1:]))  # intercept/SPY/L/S/C
    tr_x, te_x = x[:split], x[split:]
    tr_y, te_y = y[:split], y[split:]
    p = tr_x.shape[1]
    scaling = np.std(tr_x[:, 1:], axis=0, ddof=1)
    if (not np.isfinite(scaling).all()) or np.any(scaling < 1e-8):
        return None
    z = tr_x.copy()
    z[:, 1:] = (tr_x[:, 1:] - np.mean(tr_x[:, 1:], axis=0)) / scaling
    cond = float(np.linalg.cond(z))
    if not np.isfinite(cond) or cond > MAX_STANDARDIZED_CONDITION:
        return None
    b, _, rank, _ = np.linalg.lstsq(tr_x, tr_y, rcond=None)
    if rank != p:
        return None
    residual = tr_y - tr_x @ b
    # Time-ordered score outer products: Newey-West HAC with finite-sample
    # multiplier. We do not assume residual independence across trading days.
    score = tr_x * residual[:, None]
    meat = score.T @ score
    for h in range(1, min(LAGS, split - 1) + 1):
        cross = score[h:].T @ score[:-h]
        meat += (1 - h / (LAGS + 1)) * (cross + cross.T)
    xx_inv = np.linalg.inv(tr_x.T @ tr_x)
    cov = xx_inv @ meat @ xx_inv * split / (split - p)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    if not np.isfinite(se).all() or np.any(se[2:] < 1e-12):
        return None
    z_rates = [float(b[j] / se[j]) for j in (2, 3, 4)]
    p_rates = [math.erfc(abs(zv) / math.sqrt(2)) for zv in z_rates]
    base = tr_x[:, :2]
    market_b, _, r_market, _ = np.linalg.lstsq(base, tr_y, rcond=None)
    if r_market != 2:
        return None
    predictions = te_x @ b
    baseline = te_x[:, :2] @ market_b
    test_sse = float(np.sum((te_y - predictions)**2))
    base_sse = float(np.sum((te_y - baseline)**2))
    test_rmse = math.sqrt(test_sse / (n - split))
    baseline_rmse = math.sqrt(base_sse / (n - split))
    train_sst = float(np.sum((tr_y - np.mean(tr_y))**2))
    train_r2 = 1 - float(np.sum(residual**2)) / train_sst if train_sst > 1e-9 else None
    test_r2 = 1 - test_sse / base_sse if base_sse > 1e-9 else None
    return dict(
        n=n, train=split, test=n - split,
        train_through=rows[split - 1][0], test_from=rows[split][0],
        first=rows[0][0], last=rows[-1][0],
        beta=[float(v) for v in b],
        se=[float(v) for v in se],
        z=z_rates, p=p_rates,
        train_condition=cond,
        train_r2=train_r2, test_r2_vs_spy=test_r2,
        test_rmse=test_rmse, baseline_rmse=baseline_rmse,
        flagged=sum(bool(r[6]) for r in rows),
    )


def setup(con):
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_curve_factor_retro_v1(
        build_id VARCHAR NOT NULL, observed_date DATE NOT NULL,
        dgs2_shock_bps DOUBLE NOT NULL, dgs5_shock_bps DOUBLE NOT NULL,
        dgs10_shock_bps DOUBLE NOT NULL,
        level_shock_bps DOUBLE NOT NULL, slope_shock_bps DOUBLE NOT NULL,
        curvature_shock_bps DOUBLE NOT NULL,
        independent_source_publication_time_verified BOOLEAN NOT NULL,
        data_rights_verified BOOLEAN NOT NULL,
        research_only BOOLEAN NOT NULL)
    """)
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_security_curve_model_retro_v1(
        build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
        benchmark VARCHAR NOT NULL,first_date DATE NOT NULL,
        last_date DATE NOT NULL,train_through DATE NOT NULL,
        test_from DATE NOT NULL,n_observations BIGINT NOT NULL,
        n_train BIGINT NOT NULL,n_test BIGINT NOT NULL,
        standardized_train_condition DOUBLE NOT NULL,
        beta_spy DOUBLE NOT NULL,intercept_bps DOUBLE NOT NULL,
        train_r_squared DOUBLE,test_r2_vs_spy_only DOUBLE,
        test_rmse_bps DOUBLE NOT NULL,spy_baseline_rmse_bps DOUBLE NOT NULL,
        flagged_large_return_days BIGINT NOT NULL,
        hag_lags INTEGER NOT NULL,source_security_adjustments_pit_verified BOOLEAN NOT NULL,
        source_factors_pit_verified BOOLEAN NOT NULL,source_rights_verified BOOLEAN NOT NULL,
        authorized_institutional_release BOOLEAN NOT NULL,model_status VARCHAR NOT NULL)
    """)
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_security_curve_coefficients_retro_v1(
        build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
        curve_component VARCHAR NOT NULL,coefficient_bps_per_bp DOUBLE NOT NULL,
        hac_se DOUBLE NOT NULL,normal_approx_z DOUBLE NOT NULL,
        p_normal DOUBLE NOT NULL,bh_family_q DOUBLE,
        ci95_lower DOUBLE NOT NULL,ci95_upper DOUBLE NOT NULL,
        response_unit VARCHAR NOT NULL,predictor_unit VARCHAR NOT NULL,
        independently_validated BOOLEAN NOT NULL,
        released_as_institutional_beta BOOLEAN NOT NULL)
    """)
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_security_curve_builds_retro_v1(
        build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
        script_sha256 VARCHAR NOT NULL,created_at TIMESTAMPTZ NOT NULL,
        curve_factor_days BIGINT NOT NULL,security_models BIGINT NOT NULL,
        model_coefficients BIGINT NOT NULL,
        q_below_05 BIGINT NOT NULL,
        holdout_improved_vs_spy BIGINT NOT NULL,
        flagged_outlier_exposed_models BIGINT NOT NULL,
        max_standardized_condition DOUBLE,
        independently_verified_models BIGINT NOT NULL,
        release_state VARCHAR NOT NULL)
    """)


def stage(con):
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_curve_shocks AS
    WITH rates AS (
      SELECT observed_date,
        max(shock_bps) FILTER (WHERE factor_id='DGS2') AS y2,
        max(shock_bps) FILTER (WHERE factor_id='DGS5') AS y5,
        max(shock_bps) FILTER (WHERE factor_id='DGS10') AS y10,
        COUNT(DISTINCT factor_id) AS n_factor_ids
      FROM {P}lab_rate_shocks_retro_v1
      WHERE factor_id IN ('DGS2','DGS5','DGS10')
      GROUP BY 1
    )
    SELECT observed_date, y2,y5,y10,
      (y2+y5+y10)/3.0 AS curve_level_bps,
      (y10-y2) AS curve_slope_bps,
      (2*y5-y2-y10) AS curve_curvature_bps
    FROM rates WHERE n_factor_ids=3
      AND isfinite(y2) AND isfinite(y5) AND isfinite(y10)
    """)
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE tmp_curve_market AS
    SELECT a.ticker,a.observed_date,a.return_bps AS asset_return,
      spy.return_bps AS spy_return,
      c.curve_level_bps,c.curve_slope_bps,c.curve_curvature_bps,
      a.large_absolute_log_return
    FROM {P}lab_security_returns_retro_v1 AS a
    JOIN {P}lab_security_returns_retro_v1 AS spy
      ON spy.ticker='SPY' AND spy.observed_date=a.observed_date
    JOIN tmp_curve_shocks c ON c.observed_date=a.observed_date
    WHERE a.ticker<>'SPY' AND a.currency='USD'
    ORDER BY a.ticker,a.observed_date
    """)


def main():
    commit = os.getenv("LAB_PIPELINE_COMMIT", "")
    if (os.getenv("LAB_RESEARCH_SCOPE") != "internal-only"
        or len(commit) != 40 or any(x not in "0123456789abcdef" for x in commit)):
        raise RuntimeError("Internal-only scope and immutable Git SHA required")
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build = VERSION + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con = duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        setup(con)
        stage(con)
        days = con.execute("SELECT COUNT(*) FROM tmp_curve_shocks").fetchone()[0]
        by_ticker = defaultdict(list)
        cur = con.execute("SELECT * FROM tmp_curve_market")
        while batch := cur.fetchmany(10000):
            for ticker, day, y, spy, l, s, c, flag in batch:
                if all(math.isfinite(float(v)) for v in (y, spy, l, s, c)):
                    by_ticker[ticker].append(
                        (day, float(y), float(spy), float(l), float(s), float(c), bool(flag))
                    )
        model_rows, coefficient_rows = [], []
        for ticker, values in sorted(by_ticker.items()):
            values.sort(key=lambda r:r[0])
            if len({(r[0].year,r[0].month) for r in values}) < 18:
                continue
            result = fit_curve(values)
            if result is None:
                continue
            model_rows.append((
                build,ticker,"SPY",result["first"],result["last"],
                result["train_through"],result["test_from"],
                result["n"],result["train"],result["test"],
                result["train_condition"],result["beta"][1],
                result["beta"][0],result["train_r2"],
                result["test_r2_vs_spy"],result["test_rmse"],result["baseline_rmse"],
                result["flagged"],LAGS,False,False,False,False,
                "EX_POST_MULTIFACTOR_CURVE_RESEARCH_NOT_PIT"
            ))
            for idx,name in enumerate(COMPONENTS):
                j=idx+2
                b=result["beta"][j]
                se=result["se"][j]
                coefficient_rows.append((
                    build,ticker,name,b,se,result["z"][idx],result["p"][idx],
                    None,b-1.96*se,b+1.96*se,
                    "security_log_return_basis_points","curve_shock_basis_points",
                    False,False
                ))
        qs=bh_adjust([r[6] for r in coefficient_rows])
        coefficient_rows=[
            (*row[:7], q, *row[8:]) for row,q in zip(coefficient_rows,qs)
        ]
        q_pass=sum(q is not None and q < .05 for q in qs)
        holdout=sum(row[14] is not None and row[14] > 0 for row in model_rows)
        flagged=sum(row[17]>0 for row in model_rows)
        condition=max((row[10] for row in model_rows),default=None)
        if len(model_rows)<30 or days<600:
            raise RuntimeError("Insufficient historical rate or equity series")
        con.execute("BEGIN TRANSACTION")
        try:
            # Append-only versioned builds; original market prices/rates
            # and 864 single-factor research regressions never overwritten.
            con.execute(f"""
            INSERT INTO {P}lab_curve_factor_retro_v1
            SELECT ?,observed_date,y2,y5,y10,curve_level_bps,
              curve_slope_bps,curve_curvature_bps,FALSE,FALSE,TRUE
            FROM tmp_curve_shocks
            """,[build])
            con.executemany(
                f"INSERT INTO {P}lab_security_curve_model_retro_v1 "
                f"VALUES ({','.join(['?']*24)})",model_rows
            )
            con.executemany(
                f"INSERT INTO {P}lab_security_curve_coefficients_retro_v1 "
                f"VALUES ({','.join(['?']*14)})",coefficient_rows
            )
            con.execute(f"""
            INSERT INTO {P}lab_security_curve_builds_retro_v1
            VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,0,
                    'RESEARCH_ONLY_NO_SOURCE_PIT_OR_INSTITUTIONAL_BETA_APPROVAL')
            """,[build,commit,digest,days,len(model_rows),len(coefficient_rows),
                  q_pass,holdout,flagged,condition])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build)
        print(f"CURVE_FACTOR_DAYS={days}")
        print(f"USD_SECURITY_CURVE_MODELS={len(model_rows)}")
        print(f"RATE_CURVE_COMPONENT_COEFFICIENTS={len(coefficient_rows)}")
        print(f"Q_BELOW_0_05={q_pass} OOS_IMPROVED_VS_SPY={holdout}")
        print(f"MODELS_CONTAINING_FLAGGED_PRICE_DAY={flagged}")
        print(f"MAX_TRAIN_CONDITION={condition}")
        print("INDEPENDENT_SOURCE_PIT_VERIFIED=FALSE")
        print("INSTITUTIONAL_BETA_RELEASED=FALSE")
    finally:
        con.close()


if __name__ == "__main__":
    main()
