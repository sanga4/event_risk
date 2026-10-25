#!/usr/bin/env python3
"""Independent, SELECT-only acceptance for a materialized 48-asset funding-loss build.

Recomputes *per-day* squared losses, parent per-model MSE, exact 48×2 shared
date coverage and both prespecified common-date bootstrap summaries. A passing
report proves internal retrospective warehouse calculation integrity ONLY:
no original publisher PIT, issuer adjustments, rights or beta signoff.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import duckdb
import numpy as np

import phase1_shared_date_holdout_bootstrap as bootstrap

DB = "eventrisk_factor_lab"
P = DB + ".main."
SHA = re.compile(r"^[0-9a-f]{40}$")
MSE_TOL = dict(rel_tol=1e-8, abs_tol=1e-7)
RESULT_TOL = dict(rel_tol=1e-9, abs_tol=1e-8)
STATE = "RESEARCH_LOSS_SOURCE_REPLAY_VERIFIED_NOT_INSTITUTIONAL"
DISPOSITION = "RETROSPECTIVE_PAIRED_PREDICTION_LOSSES_NO_PIT_OR_LICENSE_RELEASE"
VARIANTS = frozenset(("full_training", "training_tail_exclusion"))


def approx(actual, expected, metric, tolerance=RESULT_TOL):
    if (type(actual) not in (int, float)
        or type(expected) not in (int, float)
        or not math.isfinite(actual) or not math.isfinite(expected)
        or not math.isclose(actual, expected, **tolerance)):
        raise ValueError("Persisted loss/boot model metric drift: " + metric)


def verify(manifest, parent, original, losses, summaries, expected_commit,
           producer_sha):
    """Pure, fail-closed manifest and independently replayed bootstrap checks.

    manifest columns: build, git, script sha, parent build, total cells,
    variants, securities, common dates, four source/release booleans, status.
    parent: parent build id, source code hash, source data hash, 4 approval sum.
    original: ticker,variant,heldout_dates,training cutoff,heldout first/last,
    original control MSE, original joint MSE, approval sum.
    losses: source-build, parent-build, ticker,variant,day,cutoff,actual,
    baseline prediction,joint prediction,baseline MSE loss,joint MSE loss,
    4 approval flags as a sum.
    summaries: build,parent,variant,date count,pass count,max_t,mean,lower,
    upper,2 approval flags sum.
    """
    if not SHA.fullmatch(expected_commit):
        raise ValueError("Requires exact pinned checked-out Git commit")
    if len(manifest) != 13:
        raise ValueError("Missing complete daily-loss build manifest")
    (build,sha,digest,parent_id,cells,variant_count,asset_count,days,
     pit,actions,rights,approved,status) = manifest
    if (not build or sha != expected_commit or digest != producer_sha or
        variant_count != 2 or asset_count != 48 or days < 150
        or cells != 48*2*days or
        any(x is not False for x in (pit,actions,rights,approved))
        or status != DISPOSITION):
        raise ValueError("Incorrect producer identity, source scope, or release state")
    if (len(parent)!=4 or parent[0]!=parent_id or
        not re.fullmatch(r"[0-9a-f]{64}",parent[1] or "") or
        not re.fullmatch(r"[0-9a-f]{64}",parent[2] or "") or parent[3] != 0):
        raise ValueError("Original 48-security parent source build unverified")
    if len(original)!=96 or len(losses)!=cells or len(summaries)!=2:
        raise ValueError("Missing parent, daily security loss, or bootstrap rows")
    original_map = {}
    for row in original:
        (ticker,variant,n,cutoff,first,last,bm,jm,release) = row
        key=(ticker,variant)
        if (key in original_map or variant not in VARIANTS or release != 0
            or n != days or not cutoff < first <= last):
            raise ValueError("Duplicated, divergent or approved parent security model")
        original_map[key]=row
    tickers = sorted({key[0] for key in original_map})
    if (len(tickers)!=48 or any({key[1] for key in original_map
                               if key[0]==t} != VARIANTS for t in tickers)
        or any(t == "SPY" for t in tickers)):
        raise ValueError("Wrong 48×2 parent risk-asset hypothesis family")
    lookup={}
    accum=defaultdict(lambda: [0.0,0.0,0])
    calendar=defaultdict(set)
    for r in losses:
        (source,parent_build,ticker,variant,day,cutoff,actual,pred_b,pred_j,
         loss_b,loss_j,flag_sum)=r
        key=(ticker,variant)
        idkey=(ticker,variant,day)
        if (source!=build or parent_build!=parent_id or
            key not in original_map or idkey in lookup or flag_sum != 0
            or not isinstance(day,date) or type(day) is not date):
            raise ValueError("Duplicate/unbacked or falsely released daily loss source")
        _,_,_,parent_cutoff,first,last,_,_,_ = original_map[key]
        if not (cutoff == parent_cutoff and first <= day <= last and cutoff < day):
            raise ValueError("Changed training cutoff or dated heldout observation")
        for value in (actual,pred_b,pred_j,loss_b,loss_j):
            if type(value) not in (float,int) or not math.isfinite(value):
                raise ValueError("Invalid prediction or nonfinite daily loss")
        if loss_b < 0 or loss_j < 0:
            raise ValueError("Negative squared forecast loss")
        approx(loss_b,(actual-pred_b)**2,"baseline original daily prediction",MSE_TOL)
        approx(loss_j,(actual-pred_j)**2,"joint original daily prediction",MSE_TOL)
        lookup[idkey]=r
        accum[key][0]+=loss_b
        accum[key][1]+=loss_j
        accum[key][2]+=1
        calendar[variant].add(day)
    for key,original_row in original_map.items():
        _,_,n,_,_,_,bm,jm,_=original_row
        total_b,total_j,count=accum[key]
        if count!=n:
            raise ValueError("Missing or duplicated parent-model heldout dates")
        approx(total_b/count,bm,"parent baseline MSE",MSE_TOL)
        approx(total_j/count,jm,"parent four-factor MSE",MSE_TOL)

    matched={}
    for variant in sorted(VARIANTS):
        date_list=sorted(calendar[variant])
        if len(date_list)!=days:
            raise ValueError("Insufficient or inconsistent common asset-date history")
        expected_dates=set(date_list)
        if any({d for t,v,d in lookup if (t,v)==(ticker,variant)}
               != expected_dates for ticker in tickers):
            raise ValueError("One or more securities use different holdout dates")
        cutoffs={original_map[ticker,variant][3] for ticker in tickers}
        if len(cutoffs)!=1:
            raise ValueError("Securities have inconsistent training cutoffs")
        arr_b=np.array([[lookup[t,variant,d][9] for t in tickers]
                        for d in date_list],dtype=float)
        arr_j=np.array([[lookup[t,variant,d][10] for t in tickers]
                        for d in date_list],dtype=float)
        matched[variant]=bootstrap.assess(
            tickers,date_list,next(iter(cutoffs)),arr_b,arr_j)

    seen_variants=set()
    for row in summaries:
        (source,parent_build,variant,n,passing,tcrit,average,lower,upper,flag_sum)=row
        if (source!=build or parent_build!=parent_id or
            variant not in VARIANTS or variant in seen_variants or n!=days or
            flag_sum!=0):
            raise ValueError("Source attribution or bootstrap disposition invalid")
        seen_variants.add(variant)
        result=matched[variant]
        if passing != result["research_cells_with_simultaneous_lower_bound_above_zero"]:
            raise ValueError("Stored 48-family simultaneous pass count inconsistent")
        for label,got,wanted in (
            ("max_t",tcrit,result["simultaneous_max_t_critical"]),
            ("aggregate_loss",average,result["cross_security_mean_loss_improvement"]),
            ("bootstrap_lower",lower,result["cross_security_mean_block_bootstrap_ci95"][0]),
            ("bootstrap_upper",upper,result["cross_security_mean_block_bootstrap_ci95"][1]),
        ):
            approx(got,wanted,label)
    if seen_variants!=VARIANTS:
        raise ValueError("Incomplete original paired bootstrap variants")

    return {
        "status":STATE,"build_id":build,"parent_model_build":parent_id,
        "git_source_sha":sha,"source_script_sha256":producer_sha,
        "source_model_sha256":parent[1],"original_parent_rows_sha256":parent[2],
        "daily_security_variant_observations":cells,
        "security_assets":48,"variants":2,"common_holdout_dates":days,
        "shared_date_bootstrap_result":{
            v: {"simultaneous_research_screen_pass":
                    matched[v]["research_cells_with_simultaneous_lower_bound_above_zero"],
                "aggregate_loss_improvement_ci":
                    matched[v]["cross_security_mean_block_bootstrap_ci95"]}
            for v in sorted(VARIANTS)},
        "original_publisher_pit_verified":False,
        "original_issuer_adjustment_pit_verified":False,
        "legal_data_rights_approved":False,
        "institutional_beta_released":False,
    }


def inspect(con,expected_commit,producer_sha,prefix=P):
    manifest=con.execute(f"""
        SELECT build_id,git_sha,script_sha256,parent_model_build,
          daily_loss_cells,variants,securities,shared_holdout_dates,
          source_original_pit_verified,issuer_action_vintages_verified,
          redistribution_rights_approved,institutional_beta_release,
          release_status
        FROM {prefix}lab_joint_funding_daily_loss_builds_v1
        ORDER BY built_at DESC,build_id DESC LIMIT 1
    """).fetchone()
    if manifest is None:
        raise ValueError("No original daily loss research materialization exists")
    parent=con.execute(f"""
        SELECT build_id,source_code_sha256,source_rows_sha256,
          CAST(issuer_pit_verified AS INTEGER)+
          CAST(adjusted_prices_independently_verified AS INTEGER)+
          CAST(vendor_rights_cleared AS INTEGER)+
          CAST(institutional_beta_release AS INTEGER)
        FROM {prefix}lab_joint_security_funding_builds_v1
        WHERE build_id=?
    """,[manifest[3]]).fetchone()
    original=con.execute(f"""
        SELECT ticker,variant,heldout_dates,train_last_day,
          heldout_first_day,last_day,
          market_and_treasury_heldout_mse,
          joint_market_treasury_funding_heldout_mse,
          CAST(issuer_pit_verified AS INTEGER)+
          CAST(vendor_adjustments_and_rights_approved AS INTEGER)+
          CAST(institutional_beta_released AS INTEGER)
        FROM {prefix}lab_joint_security_funding_models_v1
        WHERE build_id=? ORDER BY ticker,variant
    """,[manifest[3]]).fetchall()
    losses=con.execute(f"""
        SELECT build_id,parent_model_build,ticker,model_variant,
          heldout_date,train_last_date,actual_security_return_bps,
          baseline_control_pred_return_bps,joint_funding_pred_return_bps,
          baseline_squared_error_bps2,joint_squared_error_bps2,
          CAST(original_issuer_prices_asof_verified AS INTEGER)+
          CAST(original_factor_publication_asof_verified AS INTEGER)+
          CAST(licensed_risk_use_approved AS INTEGER)+
          CAST(institutional_beta_released AS INTEGER)
        FROM {prefix}lab_joint_funding_daily_paired_losses_v1
        WHERE build_id=? ORDER BY model_variant,ticker,heldout_date
    """,[manifest[0]]).fetchall()
    summaries=con.execute(f"""
        SELECT build_id,parent_model_build,variant,shared_holdout_days,
          simultaneous_48family_pass,simultaneous_max_t,
          aggregate_mean_loss_improvement,aggregate_block_ci95_lower,
          aggregate_block_ci95_upper,
          CAST(source_original_pit_verified AS INTEGER)+
          CAST(institutional_beta_released AS INTEGER)
        FROM {prefix}lab_joint_funding_shared_date_builds_v1
        WHERE build_id=? ORDER BY variant
    """,[manifest[0]]).fetchall()
    return verify(manifest,parent,original,losses,summaries,
                  expected_commit,producer_sha)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-commit",required=True)
    args=parser.parse_args()
    producer=Path(__file__).with_name("phase1_joint_daily_paired_loss_research.py")
    codehash=hashlib.sha256(producer.read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        report=inspect(con,args.source_commit,codehash)
    print(json.dumps(report,sort_keys=True,indent=2))
    print("RESEARCH_ONLY=TRUE INSTITUTIONAL_BETA_RELEASE=FALSE")


if __name__=="__main__":
    sys.exit(main())
