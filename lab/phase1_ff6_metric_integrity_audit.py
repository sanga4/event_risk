#!/usr/bin/env python3
"""Independent reconciliation of descriptive FF6 rolling-beta warehouse metrics.

Does NOT refit or overwrite vendor securities or claim original first-known-at
factor data. Reconstructs saved six-beta vector drifts and same holdout RMSE
comparisons from persisted outputs. Quantitative integrity != model approval.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import math
import os
from pathlib import Path

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-ff6-independent-metric-audit-v1.0.0"
FACTORS=("FF_US_MKT_RF","FF_US_SMB","FF_US_HML","FF_US_RMW","FF_US_CMA","FF_US_MOM")
TRAIN=378
TEST=63
BETA_THRESHOLD=.5
RELATIVE_SSE_THRESHOLD=1.25
TOL=1e-7


def evaluate(windows,coefficients):
    """Fail closed on nonmatching windows/factors or miscomputed model flags.

    Window rows: ticker,window_number,train_start,train_end,test_start,test_end,
    n_train,n_test,train_condition,holdout_r2,holdout_rmse,baseline_rmse,
    flagged_count,recorded_drift,recorded_drift_flag,recorded_bad_fit_flag,
    source_pit,issuer_actions,licensed_risk.
    Coefficient rows: ticker,window_number,factor_id,beta,hac5_se,pit,risk.
    """
    factors={}
    for ticker,ordinal,factor,beta,se,pit,risk in coefficients:
        key=(ticker,ordinal)
        if factor not in FACTORS or (key,factor) in factors:
            raise ValueError("Unexpected or duplicate factor coefficient")
        if pit or risk:
            raise ValueError("FF6 coefficient incorrectly authorized for risk")
        if beta is None or se is None or not math.isfinite(beta) or not math.isfinite(se) or se<=0:
            raise ValueError("Nonfinite/invalid beta coefficient or HAC uncertainty")
        factors[(key,factor)]=(float(beta),float(se))
    byticker=defaultdict(list)
    seen=set()
    for row in windows:
        if len(row)!=19:
            raise ValueError("Unexpected beta window source schema")
        (ticker,ordinal,trstart,trend,teststart,testend,ntr,ntst,condition,
         r2,rmse,benchmark,flagged,drift,drift_review,bad_fit_review,
         pit,issuer,rights)=row
        key=(ticker,ordinal)
        if key in seen:
            raise ValueError("Duplicate rolling window")
        seen.add(key)
        if not (trstart<trend<teststart<=testend and ntr==TRAIN and ntst==TEST):
            raise ValueError("Rolling window contains future train date or wrong size")
        if pit or issuer or rights:
            raise ValueError("Source was not independently verified for risk use")
        if (condition is None or not math.isfinite(condition) or condition>1000 or condition<=0
            or rmse is None or not math.isfinite(rmse) or rmse<0
            or benchmark is None or not math.isfinite(benchmark) or benchmark<=0
            or r2 is None or not math.isfinite(r2) or flagged is None or flagged<0
            or flagged>TRAIN+TEST):
            raise ValueError("Invalid rolling window diagnostics")
        measured_r2=1-(rmse/benchmark)**2
        if abs(measured_r2-r2)>TOL:
            raise ValueError("Stored holdout SSE/R2 identity mismatch")
        expected_bad=((rmse/benchmark)**2)>RELATIVE_SSE_THRESHOLD
        if bool(bad_fit_review)!=expected_bad:
            raise ValueError("Stored poor-holdout review flag mismatch")
        beta=[]
        for factor in FACTORS:
            val=factors.get((key,factor))
            if val is None:
                raise ValueError("Incomplete six-factor coefficient vector")
            beta.append(val[0])
        byticker[ticker].append((ordinal,trstart,trend,teststart,testend,
                                 beta,drift,bool(drift_review),bool(bad_fit_review),
                                 int(flagged)))
    if len(factors)!=len(windows)*len(FACTORS):
        raise ValueError("Orphan or duplicate source beta coefficient")
    if len(byticker)<40 or len(windows)<200:
        raise ValueError("Incomplete security beta universe")
    summaries=[]
    for ticker,records in sorted(byticker.items()):
        records.sort(key=lambda z:z[0])
        previous=None
        previous_end=None
        shifts=[]
        for ordinal,trstart,trend,teststart,testend,beta,drift,review,bad,flagged in records:
            if previous_end is not None and testend<=previous_end:
                raise ValueError("Nonchronological rolling heldout windows")
            measured=(None if previous is None else
                      math.sqrt(sum((a-b)**2 for a,b in zip(beta,previous)))/
                      max(math.sqrt(sum(x*x for x in previous)),.25))
            if measured is None:
                if drift is not None or review:
                    raise ValueError("First eligible window cannot have adjacent beta drift")
            else:
                if drift is None or not math.isfinite(drift) or abs(drift-measured)>TOL:
                    raise ValueError("Saved adjacent six-beta shift mismatch")
                if review != (measured>BETA_THRESHOLD):
                    raise ValueError("Beta-shift review threshold mismatch")
                shifts.append(measured)
            previous=beta
            previous_end=testend
        summaries.append((
            ticker,len(records),sum(r[7] for r in records),
            sum(r[8] for r in records),sum(r[9]>0 for r in records),
            max(shifts) if shifts else 0.0,
            bool(any(r[7] or r[8] or r[9]>0 for r in records))
        ))
    return summaries


def load(con):
    source=con.execute(f"""SELECT build_id,security_count,model_windows,coefficients,
       adjacent_beta_shift_review_windows,poor_holdout_fit_review_windows,
       windows_with_flagged_price_days,source_pit_certified_models,
       institutional_release_approved
       FROM {P}lab_ff6_rolling_beta_builds_v1
       ORDER BY built_at DESC LIMIT 1""").fetchone()
    if not source or source[7] or source[8]:
        raise RuntimeError("Rolling FF6 source audit missing or incorrectly approved")
    windows=con.execute(f"""SELECT ticker,window_number,train_start,train_end,test_start,test_end,
       n_train,n_test,train_condition,holdout_r2_vs_market_only,
       holdout_rmse_bps,market_baseline_holdout_rmse_bps,
       sample_flagged_large_security_returns,adjacent_factor_beta_l2_change,
       adjacent_beta_change_requires_review,poor_holdout_relative_error_requires_review,
       original_source_publication_pit_verified,security_original_corporate_actions_verified,
       licensed_beta_for_portfolio_risk
       FROM {P}lab_ff6_rolling_beta_windows_v1
       WHERE build_id=? ORDER BY ticker,window_number""",[source[0]]).fetchall()
    coeff=con.execute(f"""SELECT ticker,window_number,factor_id,
       coef_simple_return_bp_per_factor_bp,hac5_se,
       original_source_pit_verified,authorized_for_risk_model
       FROM {P}lab_ff6_rolling_beta_coefficients_v1
       WHERE build_id=? ORDER BY ticker,window_number,factor_id""",[source[0]]).fetchall()
    if (len(windows)!=source[2] or len(coeff)!=source[3] or
        len(coeff)!=len(windows)*len(FACTORS)):
        raise RuntimeError("Source FF6 build counts do not reconcile")
    return source,windows,coeff


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_ff6_metric_integrity_builds_v1(
      build_id VARCHAR NOT NULL,source_build_id VARCHAR NOT NULL,
      source_git_sha VARCHAR NOT NULL,script_sha256 VARCHAR NOT NULL,
      built_at TIMESTAMPTZ NOT NULL,security_count INTEGER NOT NULL,
      valid_windows INTEGER NOT NULL,verified_coefficients INTEGER NOT NULL,
      recomputed_drift_review_windows INTEGER NOT NULL,
      recomputed_poor_holdout_review_windows INTEGER NOT NULL,
      windows_with_flagged_security_returns INTEGER NOT NULL,
      independent_original_source_pit_approved BOOLEAN NOT NULL,
      institutional_beta_model_released BOOLEAN NOT NULL,
      status VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_ff6_metric_integrity_subjects_v1(
      build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,
      audited_windows INTEGER NOT NULL,drift_review_windows INTEGER NOT NULL,
      poor_holdout_windows INTEGER NOT NULL,flagged_price_windows INTEGER NOT NULL,
      largest_adjacent_six_factor_beta_shift DOUBLE NOT NULL,
      independent_model_review_required BOOLEAN NOT NULL,
      original_corporate_actions_verified BOOLEAN NOT NULL,
      approved_for_institutional_beta BOOLEAN NOT NULL)""")


def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Pinned Git SHA and internal research-only scope required")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        source,windows,coeff=load(con)
        summary=evaluate(windows,coeff)
        drifts=sum(z[2] for z in summary)
        bad=sum(z[3] for z in summary)
        exposed=sum(z[4] for z in summary)
        if (len(summary)!=source[1] or drifts!=source[4]
                or bad!=source[5] or exposed!=source[6]):
            raise RuntimeError("Independent recomputation disagrees with source manifest")
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_ff6_metric_integrity_builds_v1
                 VALUES(?,?,?,?,current_timestamp,?,?,?,?,?,?,FALSE,FALSE,
                 'INTEGRITY_RECONCILED_NOT_PIT_OR_INSTITUTIONAL_BETA_APPROVED')""",
                 [build,source[0],commit,digest,len(summary),len(windows),len(coeff),
                  drifts,bad,exposed])
            con.executemany(f"""INSERT INTO {P}lab_ff6_metric_integrity_subjects_v1
                VALUES ({','.join('?' for _ in range(10))})""",[
                (build,*s,False,False) for s in summary])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} SOURCE_BUILD={source[0]} VERIFIED_WINDOWS={len(windows)}")
    print(f"SECURITIES={len(summary)} VERIFIED_SIX_FACTOR_COEFFICIENTS={len(coeff)}")
    print(f"ADJACENT_DRIFT_REVIEW={drifts} POOR_HOLDOUT_REVIEW={bad} FLAGGED_SOURCE_PRICE_WINDOWS={exposed}")
    print("SOURCE_CORPORATE_ACTION_PIT=FALSE INSTITUTIONAL_RISK_BETA_APPROVAL=FALSE")


if __name__=="__main__":
    main()
