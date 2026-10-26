#!/usr/bin/env python3
"""Independent SELECT-only audit of 96-cell original-source funding Holm results.

Recalculate every original HAC-normal tail p, full 96-Holm step-down rank,
cross-variant beta robustness reject code, and manifest source SHA from original
parent rows. Never call the producer's score() and never grant source PIT/rights.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

import duckdb

DB="eventrisk_factor_lab"
P=DB+".main."
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA64=re.compile(r"^[0-9a-f]{64}$")
VARIANTS=frozenset(("full_training","training_tail_exclusion"))
DISPOSITION="HAC_MULTIPLE_TESTING_AND_VARIANT_DRIFT_RESEARCH_ONLY"
PASS="RESEARCH_MULTIPLICITY_SCREEN_PASS_NOT_INSTITUTIONAL"
ALPHA=0.05
MAX_BETA_SHIFT=.25

def check_number(actual,expected,label):
    if (type(actual) not in (int,float) or not math.isfinite(actual)
        or not math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-12)):
        raise ValueError("Independent Holm metric/rank drift: "+label)

def verify(manifest,parent,original,persisted,expected_sha,producer_digest):
    """Reconstruct from immutable 16-field parent model rows, NOT producer output.

    manifest: 22 versioned build fields (source identity, count and approvals)
    parent: 7 original build attributes incl source/model SHA and approval sum
    original: 96 16-field model rows (see original 96-factor producer read_parent)
    persisted: 96 18-field source/pvalue/rank/status rows
    """
    if not SHA40.fullmatch(expected_sha) or not SHA64.fullmatch(producer_digest):
        raise ValueError("Expected exact Git/source identity")
    if manifest is None or len(manifest)!=22 or parent is None or len(parent)!=7:
        raise ValueError("Incomplete original source or audit manifest")
    (build,sha,script_digest,source_models_sha,parent_build,built_at,
     models,assets,nominal_count,holm_count,base_screen,joint_screen,
     sign_flip_count,shift_count,both_skill,min_nom,min_adjusted,
     issuer_pit,action_pit,rights,release,disposition)=manifest
    if (not build or sha!=expected_sha or script_digest!=producer_digest
        or not SHA64.fullmatch(source_models_sha)
        or not isinstance(built_at,datetime) or built_at.tzinfo is None
        or models!=96 or assets!=48 or
        any(x is not False for x in (issuer_pit,action_pit,rights,release))
        or disposition!=DISPOSITION or
        parent[0]!=parent_build or not SHA40.fullmatch(parent[1])
        or not SHA64.fullmatch(parent[2]) or not SHA64.fullmatch(parent[3])
        or parent[4:6]!=(96,48) or parent[6]!=0):
        raise ValueError("Incorrect source model version, schema, PIT or rights release")
    if len(original)!=96 or len(persisted)!=96:
        raise ValueError("Missing original 96-model family or stored audit cell")
    if hashlib.sha256(repr(original).encode()).hexdigest()!=source_models_sha:
        raise ValueError("Original 96-model source sequence hash does not match stored build")
    base={}
    for row in original:
        if len(row)!=16:
            raise ValueError("Original parent model column contract drift")
        (ticker,variant,n,n_train,n_test,n_fit,first,last_train,first_test,last,
         beta,se,skill,stable,prior,approved)=row
        key=(ticker,variant)
        if (not isinstance(ticker,str) or not ticker or ticker=="SPY"
            or variant not in VARIANTS or key in base or approved!=0
            or n<600 or n_train<400 or n_test<150 or n_fit<350
            or n_fit>n_train or n_train+n_test!=n
            or not first<=last_train<first_test<=last
            or type(stable) is not bool or
            type(prior) is not str or
            not (prior.startswith("REJECT_")
                 or prior=="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL")
            or any(type(z) not in (int,float) or not math.isfinite(z)
                   for z in (beta,se,skill)) or se<=0):
            raise ValueError("Original model source key/coefficient/PIT invalid")
        if (prior=="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL" and
            (skill<=0 or not stable or abs(beta/se)<=1.96)):
            raise ValueError("Original claimed pass unsupported by source diagnostics")
        base[key]=row
    tickers={k[0] for k in base}
    if len(tickers)!=48 or any(
            {(t,v) for v in VARIANTS}.issubset(base) is False for t in tickers):
        raise ValueError("Invalid complete original 48x2 security universe")
    for ticker in tickers:
        f=base[ticker,"full_training"]
        t=base[ticker,"training_tail_exclusion"]
        if (f[2:5]!=t[2:5] or f[6:10]!=t[6:10]
            or f[5]!=f[3] or t[5]>f[5]):
            raise ValueError("Changed original identical holdout/variant dates")
    p={key:math.erfc(abs(row[10]/row[11])/math.sqrt(2))
       for key,row in base.items()}
    ordered=sorted(base,key=lambda key:(p[key],key))
    ranks={}
    adjusted={}
    cumulative=0.
    for j,key in enumerate(ordered):
        cumulative=max(cumulative,min(1.,(96-j)*p[key]))
        ranks[key]=j+1
        adjusted[key]=cumulative
    found=set()
    eligible={}
    sign_assets=set()
    shift_assets=set()
    positive_both=set()
    rejected=Counter()
    for ticker in tickers:
        full=base[ticker,"full_training"]
        trim=base[ticker,"training_tail_exclusion"]
        if full[10]*trim[10]<0:
            sign_assets.add(ticker)
        if abs(full[10]-trim[10])/max(abs(full[10]),1e-6)>MAX_BETA_SHIFT:
            shift_assets.add(ticker)
        if full[12]>0 and trim[12]>0:
            positive_both.add(ticker)
    for row in persisted:
        if len(row)!=18:
            raise ValueError("Persisted 96-model original audit column contract changed")
        (run,ticker,variant,rank,beta,se,pv,holm_p,p_nom,p_holm,
         skill,stable,prior,flip,shift,excluded,state,released)=row
        key=(ticker,variant)
        if (run!=build or key not in base or key in found or
            type(released) is not bool or released):
            raise ValueError("Missing, duplicate, unapproved model audit identity")
        found.add(key)
        orig=base[key]
        other=base[ticker,("training_tail_exclusion" if variant=="full_training"
                         else "full_training")]
        expected_flip=orig[10]*other[10]<0
        expected_shift=abs(base[ticker,"full_training"][10]-
                           base[ticker,"training_tail_exclusion"][10])/max(
                           abs(base[ticker,"full_training"][10]),1e-6)
        trim=base[ticker,"training_tail_exclusion"]
        expected_excluded=trim[3]-trim[5]
        expected_status=("REJECT_CROSS_VARIANT_FUNDING_BETA_SIGN_REVERSAL"
            if expected_flip else
            "REJECT_CROSS_VARIANT_FUNDING_BETA_SHIFT_GT25PCT"
            if expected_shift>MAX_BETA_SHIFT else
            "REJECT_CROSS_VARIANT_HOLDOUT_SKILL"
            if orig[12]<=0 or other[12]<=0 else
            "REJECT_EXISTING_HOLDOUT_OR_STABILITY_SCREEN"
            if orig[14]!="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL" else
            "REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING"
            if adjusted[key]>ALPHA else PASS)
        if (type(rank) is not int or rank!=ranks[key] or
            any(type(v) is not bool for v in (p_nom,p_holm,stable,flip))
            or p_nom!=(p[key]<=ALPHA) or p_holm!=(adjusted[key]<=ALPHA)
            or stable is not orig[13] or prior!=orig[14] or
            flip!=expected_flip or excluded!=expected_excluded
            or state!=expected_status):
            raise ValueError("Independent familywise rank/variant reject state drift")
        for name,value,expected in (
            ("funding_beta",beta,orig[10]),("HAC_se",se,orig[11]),
            ("nominal_p",pv,p[key]),("holm_p",holm_p,adjusted[key]),
            ("heldout_skill",skill,orig[12]),
            ("variant_relative_shift",shift,expected_shift)):
            check_number(value,expected,name)
        rejected[state]+=1
        eligible[key]=state==PASS
    if found!=set(base):
        raise ValueError("Stored source Holm family missing parent key")
    summary={
        "nominal_hac_p_below_05":sum(v<=ALPHA for v in p.values()),
        "holm_p_below_05":sum(v<=ALPHA for v in adjusted.values()),
        "original_research_screen_pass":sum(
            r[14]=="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL"
            for r in base.values()),
        "jointly_research_screen_pass":sum(eligible.values()),
        "sign_flip_securities":len(sign_assets),
        "coefficient_shift_gt25pct_securities":len(shift_assets),
        "positive_skill_both_variants_securities":len(positive_both),
        "minimum_nominal_p":min(p.values()),
        "minimum_holm_adjusted_p":min(adjusted.values()),
    }
    for name,actual in (("nominal_hac_p_below_05",nominal_count),
                        ("holm_p_below_05",holm_count),
                        ("original_research_screen_pass",base_screen),
                        ("jointly_research_screen_pass",joint_screen),
                        ("sign_flip_securities",sign_flip_count),
                        ("coefficient_shift_gt25pct_securities",shift_count),
                        ("positive_skill_both_variants_securities",both_skill)):
        if type(actual) is not int or actual!=summary[name]:
            raise ValueError("Original model multiplicity manifest counter drift: "+name)
    check_number(min_nom,summary["minimum_nominal_p"],"minimum_nominal_p")
    check_number(min_adjusted,summary["minimum_holm_adjusted_p"],
                 "minimum_holm_adjusted_p")
    return {
        "status":"INDEPENDENT_HOLM_96_SOURCE_REPLAY_ACCEPTED_RESEARCH_ONLY",
        "audit_build_id":build,"source_git_sha":sha,
        "source_script_sha256":script_digest,
        "parent_original_model_build":parent_build,
        "original_model_rows_sha256":source_models_sha,
        "models":96,"assets":48,
        **summary,
        "cross_training_pair_joint_survivors":sorted(
            t for t in tickers if eligible[t,"full_training"] and
            eligible[t,"training_tail_exclusion"]),
        "reason_counts":dict(sorted(rejected.items())),
        "original_publisher_first_known_pit_certified":False,
        "issuer_adjustment_vintage_certified":False,
        "licensed_downstream_risk_use":False,
        "institutional_beta_release":False,
    }

def inspect(con,expected_sha,producer_digest,prefix=P):
    manifest=con.execute(f"""SELECT build_id,source_git_sha,script_sha256,
       source_models_sha256,parent_model_build_id,built_at,
       model_cells,security_assets,nominal_hac_p_below_05,
       holm_p_below_05,original_research_screen_pass,
       jointly_research_screen_pass,sign_flip_securities,
       coefficient_shift_gt25pct_securities,
       positive_skill_both_variants_securities,minimum_nominal_p,
       minimum_holm_adjusted_p,issuer_first_published_at_verified,
       corporate_action_price_vintage_verified,redistribution_rights_verified,
       institutional_risk_beta_released,disposition
       FROM {prefix}lab_joint_funding_familywise_builds_v1
       ORDER BY built_at DESC LIMIT 1""").fetchone()
    if not manifest:
        raise ValueError("No original 96 Holm-model audit was materialized")
    parent=con.execute(f"""SELECT build_id,source_git_sha,source_code_sha256,
       source_rows_sha256,fitted_research_models,securities,
       CAST(issuer_pit_verified AS INTEGER)+
       CAST(adjusted_prices_independently_verified AS INTEGER)+
       CAST(vendor_rights_cleared AS INTEGER)+
       CAST(institutional_beta_release AS INTEGER)
       FROM {prefix}lab_joint_security_funding_builds_v1
       WHERE build_id=?""",[manifest[4]]).fetchone()
    original=con.execute(f"""SELECT ticker,variant,matched_dates,training_dates,
       heldout_dates,fit_training_dates,first_day,train_last_day,
       heldout_first_day,last_day,funding_basis_beta,funding_hac_nw5_se,
       incremental_heldout_skill,training_halves_sign_stable,
       research_screen_status,
       CAST(issuer_pit_verified AS INTEGER)+
       CAST(vendor_adjustments_and_rights_approved AS INTEGER)+
       CAST(institutional_beta_released AS INTEGER)
       FROM {prefix}lab_joint_security_funding_models_v1
       WHERE build_id=? ORDER BY ticker,variant""",[manifest[4]]).fetchall()
    persisted=con.execute(f"""SELECT build_id,ticker,variant,familywise_rank,
       funding_beta,funding_hac_se,nominal_hac_p,holm_familywise_p,
       nominal_p_below_05,holm_p_below_05,heldout_incremental_skill,
       training_half_sign_stable,prior_original_research_state,
       full_to_trim_funding_sign_flip,relative_full_to_trim_beta_shift,
       trimmed_training_days_excluded,familywise_research_state,
       institutional_beta_released
       FROM {prefix}lab_joint_funding_familywise_models_v1
       WHERE build_id=? ORDER BY ticker,variant""",[manifest[0]]).fetchall()
    return verify(manifest,parent,original,persisted,expected_sha,producer_digest)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-commit",required=True)
    args=parser.parse_args()
    original_method=Path(__file__).with_name(
        "phase1_joint_funding_familywise_audit.py")
    digest=hashlib.sha256(original_method.read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        report=inspect(con,args.source_commit,digest)
    print(json.dumps(report,sort_keys=True,default=str,indent=2))
    print("INDEPENDENT_RESEARCH_HOLM_REPLAY=PASS; PROVIDER_PIT=FALSE; "
          "DATA_RIGHTS=UNVERIFIED; INSTITUTIONAL_BETA=FALSE")

if __name__=="__main__":
    main()
