#!/usr/bin/env python3
"""Reconstruct *retrospective* daily paired held-out losses for 48 funding betas.

Source-locked: replay the EXACT date-aligned market/Treasury/funding parent
features and both predeclared training variants; compare source row SHA256 and
all parent model statistics to the existing versioned parent build before any
persistent mutation. Only an explicit manual research-append opt-in writes.

These are NOT first-published source vintages, executable source prices,
independent macro shocks, or institutionally authorized risk estimates.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

import duckdb
import numpy as np

import phase1_joint_security_funding_beta as parent_method
import phase1_shared_date_holdout_bootstrap as shared_date

DB = "eventrisk_factor_lab"
P = DB + ".main."
VERSION = "phase1-joint-daily-loss-v1.0.0"
PARENT_METRICS = (
    "ticker","variant","n","n_train","n_fit","n_holdout","first",
    "train_last","holdout_first","last","funding_beta","funding_hac_se",
    "baseline_mse","joint_mse","incremental_skill",
)

def check_parent_record(source, row):
    """Fail closed on altered or falsely approved parent model coefficients."""
    if len(source) != 16:
        raise ValueError("Changed parent model evidence contract")
    (*values, approved) = source
    if approved != 0:
        raise ValueError("Parent model release or data-rights claim unsupported")
    for j, key in enumerate(PARENT_METRICS):
        expected = row[key]
        actual = values[j]
        if isinstance(expected, float):
            if not (isinstance(actual, (float,int)) and
                    math.isfinite(float(actual)) and
                    math.isclose(float(actual), expected, rel_tol=1e-8, abs_tol=1e-7)):
                raise ValueError(f"Parent replay coefficient/heldout drift: {key}")
        elif actual != expected:
            raise ValueError(f"Parent replay source chronology/identity drift: {key}")


def reconstruct_one(records, fit):
    """Training-only normalized nested joint/baseline fit; same dates/outcomes.

    The parent model is independently reproduced; no future holdout y is ever
    accessed while fitting. Only heldout truth is used when measuring loss.
    """
    sample = sorted(records, key=lambda r:r[1])
    if len(sample) != fit["n"] or len({r[1] for r in sample}) != len(sample):
        raise ValueError("Duplicated, missing or changed source security days")
    cut = fit["n_train"]
    if not (sample[cut-1][1] == fit["train_last"]
            and sample[cut][1] == fit["holdout_first"]):
        raise ValueError("Training/heldout boundary changed from parent")
    x = np.array([[float(t) for t in r[3:7]] for r in sample])
    y = np.array([float(r[2]) for r in sample])
    excluded=np.array([bool(r[7]) or abs(float(r[6])) >=
        parent_method.STRESS_BASIS_BPS for r in sample],dtype=bool)
    mask=(np.ones(cut,dtype=bool) if fit["variant"]=="full_training"
          else ~excluded[:cut])
    if int(mask.sum()) != fit["n_fit"]:
        raise ValueError("Parent training-exclusion population changed")
    xm=x[:cut][mask]
    ym=y[:cut][mask]
    mu=xm.mean(axis=0)
    sd=xm.std(axis=0)
    if np.any(sd<1e-8):
        raise ValueError("Reconstruction unidentifiable under parent training")
    z=(xm-mu)/sd
    zhold=(x[cut:]-mu)/sd
    control=np.column_stack((np.ones(len(ym)),z[:,:3]))
    control_coeff,*_=np.linalg.lstsq(control,ym,rcond=None)
    control_hold=np.column_stack((np.ones(len(zhold)),zhold[:,:3]))
    base_pred=control_hold@control_coeff
    joint_pred=fit["intercept"]+x[cut:]@np.array([
        fit["market_beta"],fit["dgs2_beta"],fit["dgs10_beta"],
        fit["funding_beta"]])
    true=y[cut:]
    base_loss=np.square(true-base_pred)
    joint_loss=np.square(true-joint_pred)
    for name,actual,expected in (("baseline_mse",float(base_loss.mean()),
                                  fit["baseline_mse"]),
                                 ("joint_mse",float(joint_loss.mean()),
                                  fit["joint_mse"])):
        if not math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-7):
            raise ValueError(f"Reconstructed paired daily {name} differs from parent")
    if not (np.isfinite(base_pred).all() and np.isfinite(joint_pred).all() and
            np.isfinite(base_loss).all() and np.isfinite(joint_loss).all()):
        raise ValueError("Nonfinite heldout source replay")
    return [
        (fit["ticker"],fit["variant"],sample[cut+j][1],fit["train_last"],
         float(true[j]),float(base_pred[j]),float(joint_pred[j]),
         float(base_loss[j]),float(joint_loss[j]))
        for j in range(len(true))
    ]


def reconstruct(rows, parent_model_rows):
    """Reconcile 96 exact parent models, then return daily rows and two audits."""
    from itertools import groupby
    fits=parent_method.compute_all(rows)
    if len(fits)!=96 or len(parent_model_rows)!=96:
        raise ValueError("Incomplete parent 48×2 research model evidence")
    mapped={}
    for rec in parent_model_rows:
        key=(rec[0],rec[1])
        if key in mapped:
            raise ValueError("Duplicate parent model identity")
        mapped[key]=rec
    if len(mapped)!=96:
        raise ValueError("Incomplete or duplicated parent model records")
    for fit in fits:
        if (fit["ticker"],fit["variant"]) not in mapped:
            raise ValueError("Missing original parent model")
        check_parent_record(mapped[fit["ticker"],fit["variant"]],fit)
    groups={}
    for ticker,items in groupby(rows,lambda r:r[0]):
        groups[ticker]=list(items)
    daily=[]
    for fit in fits:
        daily.extend(reconstruct_one(groups[fit["ticker"]],fit))
    if len(daily)<96*shared_date.MIN_HOLDOUT_DATES:
        raise ValueError("Daily paired forecast-loss population incomplete")
    byvariant={}
    tickers=sorted(groups)
    for variant in parent_method.VARIANTS:
        subset=[r for r in daily if r[1]==variant]
        calendar=sorted({r[2] for r in subset})
        if len(subset)!=len(calendar)*48:
            raise ValueError("Incomplete common heldout security-day panel")
        lookup={(r[0],r[2]):r for r in subset}
        if len(lookup)!=len(subset):
            raise ValueError("Duplicate shared date × asset loss source")
        if {r[3] for r in subset}!={r[3] for r in subset if r[0]==tickers[0]}:
            raise ValueError("Different parent training cutoffs across securities")
        cutoff=min(r[3] for r in subset)
        base=np.array([[lookup[t,d][7] for t in tickers] for d in calendar])
        joint=np.array([[lookup[t,d][8] for t in tickers] for d in calendar])
        byvariant[variant]=shared_date.assess(tickers,calendar,cutoff,base,joint)
    return daily,byvariant


def read_parent(con):
    record=con.execute(f"""
      SELECT build_id,source_git_sha,source_rows_sha256,
             fitted_research_models,securities,
             CAST(issuer_pit_verified AS INTEGER)+
             CAST(adjusted_prices_independently_verified AS INTEGER)+
             CAST(vendor_rights_cleared AS INTEGER)+
             CAST(institutional_beta_release AS INTEGER)
      FROM {P}lab_joint_security_funding_builds_v1
      ORDER BY built_at DESC LIMIT 1
    """).fetchone()
    if (not record or len(record[1])!=40 or record[3:5]!=(96,48)
        or record[5]!=0):
        raise ValueError("Parent joint funding source/approval state invalid")
    model_rows=con.execute(f"""
      SELECT ticker,variant,matched_dates,training_dates,fit_training_dates,
        heldout_dates,first_day,train_last_day,heldout_first_day,last_day,
        funding_basis_beta,funding_hac_nw5_se,
        market_and_treasury_heldout_mse,
        joint_market_treasury_funding_heldout_mse,
        incremental_heldout_skill,
        CAST(issuer_pit_verified AS INTEGER)+
        CAST(vendor_adjustments_and_rights_approved AS INTEGER)+
        CAST(institutional_beta_released AS INTEGER)
      FROM {P}lab_joint_security_funding_models_v1
      WHERE build_id=? ORDER BY ticker,variant
    """,[record[0]]).fetchall()
    return record,model_rows


def append_research(con,build,sha,script_sha,parent_build,daily,variant_reports):
    """Append atomic research metadata only; no source tables or approvals changed."""
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_funding_daily_loss_builds_v1(
      build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,parent_model_build VARCHAR NOT NULL,
      built_at TIMESTAMPTZ NOT NULL,
      daily_loss_cells BIGINT NOT NULL,variants BIGINT NOT NULL,
      securities BIGINT NOT NULL,shared_holdout_dates BIGINT NOT NULL,
      source_original_pit_verified BOOLEAN NOT NULL,
      issuer_action_vintages_verified BOOLEAN NOT NULL,
      redistribution_rights_approved BOOLEAN NOT NULL,
      institutional_beta_release BOOLEAN NOT NULL,
      release_status VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_funding_daily_paired_losses_v1(
      build_id VARCHAR NOT NULL,parent_model_build VARCHAR NOT NULL,
      ticker VARCHAR NOT NULL,model_variant VARCHAR NOT NULL,
      heldout_date DATE NOT NULL,train_last_date DATE NOT NULL,
      actual_security_return_bps DOUBLE NOT NULL,
      baseline_control_pred_return_bps DOUBLE NOT NULL,
      joint_funding_pred_return_bps DOUBLE NOT NULL,
      baseline_squared_error_bps2 DOUBLE NOT NULL,
      joint_squared_error_bps2 DOUBLE NOT NULL,
      original_issuer_prices_asof_verified BOOLEAN NOT NULL,
      original_factor_publication_asof_verified BOOLEAN NOT NULL,
      licensed_risk_use_approved BOOLEAN NOT NULL,
      institutional_beta_released BOOLEAN NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_funding_shared_date_builds_v1(
      build_id VARCHAR NOT NULL,parent_model_build VARCHAR NOT NULL,
      variant VARCHAR NOT NULL,shared_holdout_days BIGINT NOT NULL,
      simultaneous_48family_pass BIGINT NOT NULL,
      simultaneous_max_t DOUBLE NOT NULL,
      aggregate_mean_loss_improvement DOUBLE NOT NULL,
      aggregate_block_ci95_lower DOUBLE NOT NULL,
      aggregate_block_ci95_upper DOUBLE NOT NULL,
      source_original_pit_verified BOOLEAN NOT NULL,
      institutional_beta_released BOOLEAN NOT NULL)""")
    records=[(build,parent_build,*r,False,False,False,False) for r in daily]
    summaries=[(build,parent_build,variant,r["independent_date_count"],
        r["research_cells_with_simultaneous_lower_bound_above_zero"],
        r["simultaneous_max_t_critical"],
        r["cross_security_mean_loss_improvement"],
        *r["cross_security_mean_block_bootstrap_ci95"],False,False)
        for variant,r in sorted(variant_reports.items())]
    if len(daily)!=len(variant_reports)*48*next(iter(
            variant_reports.values()))["independent_date_count"]:
        raise ValueError("Incomplete research daily paired-loss materialization")
    con.execute("BEGIN TRANSACTION")
    try:
        con.executemany(f"""INSERT INTO {P}lab_joint_funding_daily_paired_losses_v1
          VALUES ({','.join(['?']*15)})""",records)
        con.executemany(f"""INSERT INTO {P}lab_joint_funding_shared_date_builds_v1
          VALUES ({','.join(['?']*11)})""",summaries)
        con.execute(f"""INSERT INTO {P}lab_joint_funding_daily_loss_builds_v1
          VALUES (?,?,?,?,current_timestamp,?,?,?,?,FALSE,FALSE,FALSE,FALSE,
          'RETROSPECTIVE_PAIRED_PREDICTION_LOSSES_NO_PIT_OR_LICENSE_RELEASE')
          """,[build,sha,script_sha,parent_build,len(records),len(summaries),48,
               next(iter(variant_reports.values()))["independent_date_count"]])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--append-research",action="store_true")
    args=parser.parse_args()
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40
        or any(x not in "0123456789abcdef" for x in commit)):
        raise ValueError("Pinned Git source and research scope required")
    if args.append_research and os.getenv("LAB_RESEARCH_WRITE_ACK")!="confirmed":
        raise ValueError("Explicit named research-only append confirmation required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        parent_build,models=read_parent(con)
        rows=parent_method.sql_inputs(con)
        source_sha=hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()
        if source_sha!=parent_build[2]:
            raise ValueError("Original source 48-security × macro date history changed")
        daily,audits=reconstruct(rows,models)
        if args.append_research:
            append_research(con,build,commit,script_sha,parent_build[0],
                            daily,audits)
    print(json.dumps({
        "build_id":build if args.append_research else None,
        "parent_source_build":parent_build[0],
        "pair_loss_observations":len(daily),
        "mode":"APPEND_ONLY_RESEARCH_MATERIALIZATION" if args.append_research
               else "SOURCE_PINNED_READ_ONLY_REPLAY_NO_DATABASE_WRITES",
        "variant_shared_date_bootstrap_summary":{
            k:{"heldout_dates":v["independent_date_count"],
               "statistical_research_screen_only_count":
                   v["research_cells_with_simultaneous_lower_bound_above_zero"],
               "common_date_block_ci95":
                   v["cross_security_mean_block_bootstrap_ci95"]}
            for k,v in audits.items()},
        "original_source_pit":False,
        "legal_redistribution_approval":False,
        "institutional_beta_release":False,
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
