#!/usr/bin/env python3
"""Exploratory factor/venue diagnostics with HAC errors and chronological holdout.

Research-only. Historical market quotes are mostly backfills and reported
factor histories lack historical vintage provenance. Nothing is PIT/causal.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from math import erfc, floor, isfinite, sqrt
import hashlib
import os

import duckdb

DB = "eventrisk_factor_lab"
P = DB + ".main."
VERSION = "phase1-diagnostics-v2.0.0"


def ols_hac_train(pairs, lag=5):
    """Two-coefficient OLS plus Bartlett-kernel Newey-West covariance."""
    n = len(pairs)
    if n < 40:
        return None
    xs = [float(p[0]) for p in pairs]
    ys = [float(p[1]) for p in pairs]
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    centered = [x - xbar for x in xs]
    xx = sum(z*z for z in centered)
    if xx < 1e-12:
        return None
    beta = sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys)) / xx
    alpha = ybar - beta*xbar
    resid = [y-alpha-beta*x for x,y in zip(xs,ys)]
    sse = sum(r*r for r in resid)
    yy = sum((y-ybar)**2 for y in ys)
    r2 = 1 - sse/yy if yy > 1e-12 else None
    # The slope influence score is (x - mean_x)*residual / Sxx.
    scores = [x*r for x,r in zip(centered,resid)]
    long_var = sum(s*s for s in scores)
    for h in range(1, min(lag, n-1)+1):
        weight = 1 - h/(lag+1)
        long_var += 2 * weight * sum(scores[t]*scores[t-h] for t in range(h,n))
    long_var = max(0.0, long_var)
    se = sqrt(n/(n-2) * long_var)/xx
    z = beta/se if se > 1e-14 else None
    p = erfc(abs(z)/sqrt(2)) if z is not None else None
    return {"slope":beta,"intercept":alpha,"r2":r2,"hac_se":se,"z":z,"p":p,
            "train_y_mean":ybar}


def fit(rows, lag):
    n = len(rows)
    ntrain = floor(0.70 * n)
    if ntrain < 80 or n-ntrain < 25:
        return None
    train = rows[:ntrain]
    test = rows[ntrain:]
    model = ols_hac_train([(x,y) for _,x,y in train],lag)
    if model is None:
        return None
    baseline_mean = model["train_y_mean"]
    actual = [y for _,x,y in test]
    fitted = [model["intercept"] + model["slope"]*x for _,x,y in test]
    base_error = sum((y-baseline_mean)**2 for y in actual)
    fit_error = sum((y-pred)**2 for y,pred in zip(actual,fitted))
    model["oos_r2_vs_train_mean"] = (
        1 - fit_error/base_error if base_error > 1e-12 else None
    )
    model["oos_rmse"] = sqrt(fit_error/len(test))
    model["baseline_rmse"] = sqrt(base_error/len(test))
    model["train_n"] = ntrain
    model["test_n"] = len(test)
    return model


def bh_adjust(pvalues):
    """Benjamini-Hochberg multiplicity-adjusted q values for all tested models."""
    valid = sorted((min(1.,max(0.,float(p))),i) for i,p in enumerate(pvalues)
                   if p is not None and isfinite(p))
    out = [None]*len(pvalues)
    m = len(valid)
    q_min = 1.0
    for rank in range(m-1, -1, -1):
        p, i = valid[rank]
        q_min = min(q_min, p*m/(rank+1))
        out[i] = q_min
    return out


def main():
    if os.environ.get("LAB_RESEARCH_SCOPE") != "internal-only":
        raise RuntimeError("This builder requires LAB_RESEARCH_SCOPE=internal-only")
    commit = os.environ.get("LAB_PIPELINE_COMMIT", "")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("An immutable 40-digit source Git SHA is mandatory")
    sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_id = VERSION + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con = duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone = 'UTC'")
    try:
        # Aggregate only from established research inputs; restricted factors
        # and invalid venue samples are excluded. Lagged predictor is PREVIOUS
        # OBSERVED venue day, not an event known-before publication guarantee.
        query = f"""
        WITH factor_vintages AS (
          SELECT f.factor_id, f.observed_date, f.value, f.unit,
            row_number() OVER (
              PARTITION BY f.factor_id,f.observed_date
              ORDER BY f.ingested_at DESC,f.record_sha256 DESC
            ) AS rank_vintage
          FROM {P}lab_factor_observations f
          JOIN {P}lab_factor_catalog c USING (factor_id)
          WHERE c.active=TRUE AND c.license_class NOT LIKE 'restricted%'
            AND f.unit=c.unit AND isfinite(f.value)
        ),
        factor_changes AS (
          SELECT factor_id, unit,observed_date, value,
            lag(value) OVER (PARTITION BY factor_id ORDER BY observed_date) AS prev_value,
            lag(observed_date) OVER (PARTITION BY factor_id ORDER BY observed_date) AS prev_date
          FROM factor_vintages WHERE rank_vintage=1
        ),
        factor_final AS (
          SELECT factor_id,unit,observed_date,
            CASE WHEN date_diff('day',prev_date,observed_date) BETWEEN 1 AND 7
              THEN CASE WHEN unit='percent' THEN 100*(value-prev_value)
                        ELSE value-prev_value END
              ELSE NULL END AS factor_delta
          FROM factor_changes
        ),
        venue_history AS (
          SELECT venue, observed_date,mean_absolute_delta_pp,
            lag(mean_absolute_delta_pp) OVER (
              PARTITION BY venue ORDER BY observed_date
            ) AS prev_abs_move,
            lag(observed_date) OVER (
              PARTITION BY venue ORDER BY observed_date
            ) AS prev_venue_day
          FROM {P}lab_venue_daily_features_v1
          WHERE n_comparable_markets >= 10 AND point_in_time_verified=FALSE
        )
        SELECT f.factor_id,f.unit,v.venue,f.observed_date,
          v.mean_absolute_delta_pp AS x_same_day,
          CASE WHEN date_diff('day',v.prev_venue_day,v.observed_date) BETWEEN 1 AND 4
               THEN v.prev_abs_move ELSE NULL END AS x_previous_venue_day,
          f.factor_delta AS response
        FROM factor_final f JOIN venue_history v USING(observed_date)
        WHERE f.factor_delta IS NOT NULL AND isfinite(f.factor_delta)
        ORDER BY f.factor_id,v.venue,f.observed_date
        """
        dataset = con.execute(query).fetchall()
        groups = defaultdict(list)
        for fid, unit, venue, day, same, prev, y in dataset:
            if y is None or not isfinite(y):
                continue
            for spec, x in (("contemporaneous",same), ("previous_venue_day",prev)):
                if x is not None and isfinite(x):
                    groups[(fid,unit,venue,spec)].append((day,float(x),float(y)))
        output=[]
        for (fid, unit, venue, spec), rows in sorted(groups.items()):
            if len(rows)<120 or len({(d.year,d.month) for d,_,_ in rows})<12:
                continue
            rows.sort(key=lambda x:x[0])
            result = fit(rows,5)
            if result is None:
                continue
            output.append((fid,unit,venue,spec,len(rows),rows[0][0],rows[-1][0],result))
        qvalues = bh_adjust([row[-1]["p"] for row in output])
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_robust_regressions_v2 (
          factor_id VARCHAR NOT NULL,
          factor_unit VARCHAR NOT NULL,
          venue VARCHAR NOT NULL,
          predictor_timing VARCHAR NOT NULL,
          n_total BIGINT NOT NULL,
          n_train BIGINT NOT NULL,
          n_test BIGINT NOT NULL,
          start_date DATE NOT NULL,
          end_date DATE NOT NULL,
          slope DOUBLE,
          intercept DOUBLE,
          in_sample_r2 DOUBLE,
          newey_west_lags INTEGER NOT NULL,
          hac_slope_se DOUBLE,
          z_approx DOUBLE,
          two_sided_normal_p DOUBLE,
          benjamini_hochberg_q DOUBLE,
          oos_r2_vs_train_mean DOUBLE,
          oos_rmse DOUBLE,
          baseline_rmse DOUBLE,
          research_label VARCHAR NOT NULL,
          point_in_time_verified BOOLEAN NOT NULL,
          approved_for_decision_use BOOLEAN NOT NULL,
          build_id VARCHAR NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_robust_regression_builds_v2 (
          build_id VARCHAR NOT NULL,
          pipeline_version VARCHAR NOT NULL,
          source_commit VARCHAR NOT NULL,
          source_script_sha256 VARCHAR NOT NULL,
          built_at TIMESTAMPTZ NOT NULL,
          compared_hypotheses BIGINT NOT NULL,
          significant_at_fdr_5pct BIGINT NOT NULL,
          positive_out_of_sample_r2 BIGINT NOT NULL,
          point_in_time_eligible BIGINT NOT NULL,
          release_state VARCHAR NOT NULL
        )""")
        # Each model uses chronological 70/30 holdout. Robust SE is a
        # 5-lag Bartlett HAC normal approximation; not a causal significance test.
        packed=[]
        for (fid, unit,venue,spec,n,first,last,r),q in zip(output,qvalues):
            packed.append((fid,unit,venue,spec,n,r["train_n"],r["test_n"],
                           first,last,r["slope"],r["intercept"],r["r2"],5,
                           r["hac_se"],r["z"],r["p"],q,
                           r["oos_r2_vs_train_mean"],r["oos_rmse"],r["baseline_rmse"],
                           "EXPLORATORY_HISTORICAL_ASSOCIATION_NO_PIT",
                           False,False,build_id))
        passing_fdr = sum(q is not None and q<0.05 for q in qvalues)
        positive_oos = sum(x[-1]["oos_r2_vs_train_mean"] is not None and x[-1]["oos_r2_vs_train_mean"]>0 for x in output)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"DELETE FROM {P}lab_robust_regressions_v2")
            if packed:
                placeholders = ",".join(["?"]*24)
                con.executemany(f"INSERT INTO {P}lab_robust_regressions_v2 VALUES ({placeholders})",packed)
            con.execute(f"""
              INSERT INTO {P}lab_robust_regression_builds_v2 VALUES (
                ?,?,?,?,current_timestamp,?,?,?,0,'RESEARCH_UNRELEASED_NOT_POINT_IN_TIME'
              )""",[build_id,VERSION,commit,sha256,len(output),passing_fdr,positive_oos])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build_id)
        print("MODELS="+str(len(output)))
        print("FDR_Q_BELOW_0_05="+str(passing_fdr))
        print("OOS_R2_POSITIVE="+str(positive_oos))
        print("POINT_IN_TIME_ELIGIBLE=0; RELEASE=BLOCKED")
    finally:
        con.close()


if __name__ == "__main__":
    main()
