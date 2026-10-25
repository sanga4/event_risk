#!/usr/bin/env python3
"""Seven-factor held-out covariance tail audit; NO portfolio VaR approval.

The source is an already computed, retrospective, four-method walk-forward
Gaussian covariance study. A Mahalanobis quadratic is compared to predeclared
chi-square(7) reference quantiles. Estimation, revisions, non-Gaussian tails
and dependence invalidate treating the nominal quantile as a proven VaR.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import random

DB = "eventrisk_factor_lab"
P = DB + ".main."
VERSION = "phase1-covariance-tail-audit-v1.0.0"
MODELS = ("eq252_shrink10", "eq252_shrink50", "ewma094_shrink10", "ewma097_shrink10")
FACTORS = 7
TRAIN = 252
HOLDOUT = 164
Q95 = 14.067140449340169  # chi-square 7 degrees of freedom, fixed before evaluation
Q99 = 18.475306906582357
N_RESAMPLES = 1000
BLOCK = 10
SEED = 20261025


def iid_binomial_upper_tail(n, hits, p):
    """Exact Pr{Binomial(n,p) >= hits}; iid approximation ONLY."""
    if n < 1 or not 0 <= hits <= n or not 0 < p < 1:
        raise ValueError("Invalid tail probability inputs")
    return math.fsum(math.comb(n, k) * p**k * (1 - p)**(n-k)
                     for k in range(hits, n+1))


def circular_block_interval(bits, seed=SEED, block=BLOCK, resamples=N_RESAMPLES):
    """Deterministic descriptive resampling of observed clustered hits."""
    n = len(bits)
    if n < 125 or block < 1 or block > n or resamples < 100:
        raise ValueError("Insufficient block-bootstrap history")
    if any(v not in (0, 1) for v in bits):
        raise ValueError("Exceedance series must be binary")
    rng = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        indices = []
        for _ in range(math.ceil(n/block)):
            k = rng.randrange(n)
            indices.extend((k+j) % n for j in range(block))
        estimates.append(sum(bits[k] for k in indices[:n]) / n)
    estimates.sort()
    return estimates[int((resamples-1)*.025)], estimates[int((resamples-1)*.975)]


def longest_run(bits):
    current = longest = 0
    for hit in bits:
        current = current + 1 if hit else 0
        longest = max(longest, current)
    return longest


def evaluate(rows):
    """Validate strict paired chronology and calculate prespecified diagnostics.

    Row fields: observed_date, model_id, train_start, train_end, n_train,
    Mahalanobis quadratic, largest train-standardized absolute shock,
    train-only scaling, original PIT approved, source rights approved,
    institutional model approved.
    """
    per_model = defaultdict(list)
    observed = set()
    for row in rows:
        if len(row) != 11:
            raise ValueError("Unexpected source score schema")
        day, model, tr0, tr1, ntrain, q, maxz, train_only, pit, rights, approved = row
        if model not in MODELS:
            raise ValueError("Unexpected covariance model")
        if not (tr0 < tr1 < day) or ntrain != TRAIN or train_only is not True:
            raise ValueError("Future-data train overlap or scaling violation")
        if pit or rights or approved:
            raise ValueError("Unverified model cannot be treated as approved")
        if q is None or maxz is None or not math.isfinite(q) or not math.isfinite(maxz):
            raise ValueError("Missing or nonfinite covariance score")
        if q < 0 or maxz < 0:
            raise ValueError("Invalid negative risk diagnostic")
        if (model, day) in observed:
            raise ValueError("Duplicate factor-date model score")
        observed.add((model, day))
        per_model[model].append((day, float(q), float(maxz)))
    if set(per_model) != set(MODELS) or len(rows) != len(MODELS)*HOLDOUT:
        raise ValueError("Expected full four-method paired holdout")
    results = []
    daily = []
    reference_dates = None
    for index, model in enumerate(MODELS):
        data = sorted(per_model[model])
        dates = tuple(r[0] for r in data)
        if len(data) != HOLDOUT or len(set(dates)) != HOLDOUT:
            raise ValueError("Insufficient unique evaluation dates")
        if reference_dates is None:
            reference_dates = dates
        elif dates != reference_dates:
            raise ValueError("Nonidentical holdout dates across methods")
        exceed99 = [int(q > Q99) for _, q, _ in data]
        exceed95 = [int(q > Q95) for _, q, _ in data]
        highz = [int(z > 4.0) for _, _, z in data]
        lo, hi = circular_block_interval(exceed99, seed=SEED + index)
        hits99 = sum(exceed99)
        results.append(dict(
            model_id=model, days=HOLDOUT, hits95=sum(exceed95),
            hits99=hits99, observed99=hits99/HOLDOUT,
            expected99=HOLDOUT*.01, iid_p=iid_binomial_upper_tail(HOLDOUT,hits99,.01),
            block_lo=lo, block_hi=hi, longest_run=longest_run(exceed99),
        ))
        results[-1]["large_shocks"] = sum(highz)
        results[-1]["large_shock_hits99"] = sum(a*b for a,b in zip(highz,exceed99))
        daily.extend((date,model,q,z,bool(x95),bool(x99))
                     for (date,q,z),x95,x99 in zip(data,exceed95,exceed99))
    return results,daily


def read_source(con):
    build = con.execute(f"""SELECT build_id,strict_source_joint_dates,holdout_days,
      factor_count,prespecified_model_count,daily_model_scores,portfolio_risk_model_released
      FROM {P}lab_regime_cov_research_builds_v1
      ORDER BY created_at DESC LIMIT 1""").fetchone()
    if (build is None or build[1] < 600 or build[2] != HOLDOUT or
        build[3] != FACTORS or build[4] != len(MODELS) or
        build[5] != HOLDOUT*len(MODELS) or build[6]):
        raise RuntimeError("Covariance source build missing or not research-only")
    rows = con.execute(f"""SELECT factor_observed_date,model_id,training_start,training_end,
       historical_train_observations,quadratic_mahalanobis_score,
       largest_train_scaled_factor_move,training_only_factor_standardization,
       original_historic_source_pit_verified,licensed_for_portfolio_risk,
       approved_institutional_risk_model
       FROM {P}lab_regime_cov_daily_scores_v1
       WHERE build_id=? ORDER BY factor_observed_date,model_id""",[build[0]]).fetchall()
    return build[0], rows


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_cov_tail_calibration_builds_v1(
       build_id VARCHAR NOT NULL, source_build_id VARCHAR NOT NULL,
       source_git_sha VARCHAR NOT NULL, code_sha256 VARCHAR NOT NULL,
       built_at TIMESTAMPTZ NOT NULL, model_count INTEGER NOT NULL,
       paired_holdout_dates INTEGER NOT NULL, daily_scores INTEGER NOT NULL,
       total_99pct_exceedances INTEGER NOT NULL,
       original_publication_pit_verified BOOLEAN NOT NULL,
       licensed_portfolio_risk_approved BOOLEAN NOT NULL,
       institutional_model_release BOOLEAN NOT NULL, release_state VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_cov_tail_calibration_summary_v1(
       build_id VARCHAR NOT NULL,source_build_id VARCHAR NOT NULL,
       model_id VARCHAR NOT NULL, holdout_days INTEGER NOT NULL,
       nominal_95pct_hits INTEGER NOT NULL,nominal_99pct_hits INTEGER NOT NULL,
       observed_99pct_exceedance_rate DOUBLE NOT NULL,
       nominal_99pct_expected_hits DOUBLE NOT NULL,
       iid_binomial_upper_tail_p_diagnostic DOUBLE NOT NULL,
       circular_10day_block_lower95 DOUBLE NOT NULL,
       circular_10day_block_upper95 DOUBLE NOT NULL,
       longest_run_99pct_hits INTEGER NOT NULL,
       observed_days_with_absolute_train_scaled_move_gt4 INTEGER NOT NULL,
       those_days_also_exceeding_99pct INTEGER NOT NULL,
       model_risk_independently_approved BOOLEAN NOT NULL,
       original_source_pit_certified BOOLEAN NOT NULL,
       approved_portfolio_var_backtest BOOLEAN NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_cov_tail_calibration_daily_v1(
       build_id VARCHAR NOT NULL, source_build_id VARCHAR NOT NULL,
       factor_observed_date DATE NOT NULL,model_id VARCHAR NOT NULL,
       quadratic_mahalanobis_score DOUBLE NOT NULL,
       largest_train_scaled_factor_move DOUBLE NOT NULL,
       exceeds_nominal_chi7_95 BOOLEAN NOT NULL,
       exceeds_nominal_chi7_99 BOOLEAN NOT NULL,
       approved_portfolio_var_backtest BOOLEAN NOT NULL)""")


def main():
    commit = os.environ.get("LAB_PIPELINE_COMMIT", "")
    if (os.getenv("LAB_RESEARCH_SCOPE") != "internal-only" or len(commit) != 40 or
        any(c not in "0123456789abcdef" for c in commit)):
        raise RuntimeError("Pinned source commit and research-only scope required")
    import duckdb
    build = VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        source_build, rows = read_source(con)
        summary,daily = evaluate(rows)
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_cov_tail_calibration_builds_v1 VALUES
               (?,?,?,?,current_timestamp,?,?,?,?,FALSE,FALSE,FALSE,
               'RETROSPECTIVE_TAIL_CALIBRATION_ONLY_NOT_APPROVED_VAR')""",
               [build,source_build,commit,code_sha,len(summary),HOLDOUT,len(daily),
                sum(m["hits99"] for m in summary)])
            con.executemany(f"""INSERT INTO {P}lab_cov_tail_calibration_summary_v1
               VALUES ({','.join('?' for _ in range(17))})""",[
               (build,source_build,m["model_id"],m["days"],m["hits95"],m["hits99"],
                m["observed99"],m["expected99"],m["iid_p"],
                m["block_lo"],m["block_hi"],m["longest_run"],
                m["large_shocks"],m["large_shock_hits99"],False,False,False)
               for m in summary])
            # Vectorized persistence of the input-derived day scores.
            con.execute(f"""INSERT INTO {P}lab_cov_tail_calibration_daily_v1
               SELECT ?,?,factor_observed_date,model_id,
                 quadratic_mahalanobis_score,largest_train_scaled_factor_move,
                 quadratic_mahalanobis_score>?,quadratic_mahalanobis_score>?,FALSE
               FROM {P}lab_regime_cov_daily_scores_v1 WHERE build_id=?""",
               [build,source_build,Q95,Q99,source_build])
            n=con.execute(f"""SELECT COUNT(*) FROM {P}lab_cov_tail_calibration_daily_v1
               WHERE build_id=?""",[build]).fetchone()[0]
            if n!=len(daily):
                raise RuntimeError("Daily audit row count mismatch")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} SOURCE_BUILD={source_build} MODELS={len(summary)} SCORES={len(daily)}")
    for m in summary:
        print(f"MODEL={m['model_id']} NOMINAL99_HITS={m['hits99']}/{m['days']} "
              f"RATE={m['observed99']:.4f} IID_DIAGNOSTIC_P={m['iid_p']:.6g} "
              f"BLOCK_BOOTSTRAP95=[{m['block_lo']:.4f},{m['block_hi']:.4f}] "
              f"MAX_CONSECUTIVE={m['longest_run']}")
    print("ORIGINAL_SOURCE_PIT=FALSE LICENSED_VAR=FALSE INSTITUTIONAL_MODEL_APPROVED=FALSE")


if __name__ == "__main__":
    main()
