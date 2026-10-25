#!/usr/bin/env python3
"""Familywise multiplicity and cross-variant sensitivity of joint funding betas.

A second-stage, append-only REJECTION audit. The original 96 retrospective
security beta fits are not re-estimated or self-approved. Holm correction
covers ALL 96 predeclared model cells, not only nominally significant results.
HAC normal tail probabilities remain descriptive; not economically causal PIT.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import math
import os

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-joint-funding-familywise-v1.0.0"
VARIANTS=frozenset(("full_training","training_tail_exclusion"))
ASSETS=48
FAMILY=96
ALPHA=0.05
RELATIVE_SHIFT_THRESHOLD=0.25

def score(rows):
    """Validate parent-model keys/provenance and apply global Holm correction.

    Columns: ticker, variant, matched_dates, training_dates, heldout_dates,
    fit_training_dates, first, train_last, holdout_first, last, beta, HAC_SE,
    heldout_incremental_skill, training_half_sign_stable, prior_state,
    upstream_approval_count.
    """
    if len(rows)!=FAMILY:
        raise ValueError("Missing original 96 independent model cells")
    parsed={}
    for r in rows:
        if len(r)!=16:
            raise ValueError("Changed independent source model schema")
        (ticker,variant,n,train,test,fit_n,first,train_last,test_first,last,
         beta,se,skill,stable,prior,approved)=r
        key=(ticker,variant)
        if (not ticker or ticker=="SPY" or variant not in VARIANTS
            or key in parsed or approved or
            n<600 or train<400 or test<150 or fit_n<350 or fit_n>train
            or train+test!=n or not first<=train_last<test_first<=last
            or not isinstance(stable,bool) or
            not isinstance(prior,str) or not (prior.startswith("REJECT_")
            or prior=="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL")
            or not all(isinstance(x,(int,float)) and math.isfinite(x)
                       for x in (beta,se,skill)) or se<=0):
            raise ValueError("Invalid key, chronology, standard error or source approval")
        p=math.erfc(abs(beta/se)/math.sqrt(2.0))
        if not 0<=p<=1:
            raise ValueError("Invalid nominal two-sided Gaussian/HAC tail probability")
        parsed[key]={"row":r,"p":p}
    tickers={x[0] for x in parsed}
    if len(tickers)!=ASSETS or any({v for t,v in parsed if t==ticker}!=VARIANTS
                                  for ticker in tickers):
        raise ValueError("Incomplete paired 48-asset factor universe")
    variation={}
    for ticker in tickers:
        full=parsed[ticker,"full_training"]["row"]
        trim=parsed[ticker,"training_tail_exclusion"]["row"]
        if (full[2:5]!=trim[2:5] or full[6:10]!=trim[6:10]
            or full[5]!=full[3] or trim[5]>full[5]):
            raise ValueError("Tail sensitivity changed original holdout or chronology")
        sign_flip=full[10]*trim[10]<0
        relative_shift=abs(full[10]-trim[10])/max(abs(full[10]),1e-6)
        variation[ticker]=(sign_flip,relative_shift,trim[3]-trim[5])
    ordered=sorted(parsed, key=lambda k:(parsed[k]["p"],k))
    cum=0.0
    for i,key in enumerate(ordered):
        cum=max(cum,min(1.0,(FAMILY-i)*parsed[key]["p"]))
        parsed[key]["holm_p"]=cum
        parsed[key]["rank"]=i+1
    output=[]
    for ticker,variant in sorted(parsed):
        r=parsed[ticker,variant]["row"]
        s=parsed[ticker,variant]
        sign_flip,shift,excluded=variation[ticker]
        nominal=s["p"]<=ALPHA
        adjusted=s["holm_p"]<=ALPHA
        # Never elevate a failed base model or missing source rights.
        status=("REJECT_EXISTING_HOLDOUT_OR_STABILITY_SCREEN"
                if r[14]!="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL" else
                "REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING"
                if not adjusted else
                "RESEARCH_MULTIPLICITY_SCREEN_PASS_NOT_INSTITUTIONAL")
        output.append((ticker,variant,s["rank"],r[10],r[11],s["p"],s["holm_p"],
                       nominal,adjusted,r[12],r[13],r[14],sign_flip,shift,
                       excluded,status))
    return {"models":FAMILY,"assets":ASSETS,
            "nominal_hac_p_below_05":sum(x[7] for x in output),
            "holm_p_below_05":sum(x[8] for x in output),
            "original_research_screen_pass":sum(x[11]=="RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL" for x in output),
            "joint_screen_pass":sum(x[-1]=="RESEARCH_MULTIPLICITY_SCREEN_PASS_NOT_INSTITUTIONAL" for x in output),
            "sign_flip_assets":sum(variation[t][0] for t in tickers),
            "relative_shift_gt25_assets":sum(variation[t][1]>RELATIVE_SHIFT_THRESHOLD for t in tickers),
            "positive_oos_both_variants":sum(parsed[t,"full_training"]["row"][12]>0 and parsed[t,"training_tail_exclusion"]["row"][12]>0 for t in tickers),
            "min_nominal_p":min(x[5] for x in output),
            "min_holm_adjusted_p":min(x[6] for x in output),
            "rows":output}

def read_parent(con):
    parent=con.execute(f"""SELECT build_id,source_git_sha,
       fitted_research_models,securities,
       CAST(issuer_pit_verified AS INTEGER)+
       CAST(adjusted_prices_independently_verified AS INTEGER)+
       CAST(vendor_rights_cleared AS INTEGER)+
       CAST(institutional_beta_release AS INTEGER)
       FROM {P}lab_joint_security_funding_builds_v1
       ORDER BY built_at DESC LIMIT 1""").fetchone()
    if (parent is None or len(parent[1])!=40 or parent[2]!=FAMILY
        or parent[3]!=ASSETS or parent[4]!=0):
        raise ValueError("Latest source joint model build is unverified or incomplete")
    rows=con.execute(f"""SELECT ticker,variant,matched_dates,training_dates,
       heldout_dates,fit_training_dates,first_day,train_last_day,
       heldout_first_day,last_day,funding_basis_beta,funding_hac_nw5_se,
       incremental_heldout_skill,training_halves_sign_stable,
       research_screen_status,
       CAST(issuer_pit_verified AS INTEGER)+
       CAST(vendor_adjustments_and_rights_approved AS INTEGER)+
       CAST(institutional_beta_released AS INTEGER)
       FROM {P}lab_joint_security_funding_models_v1
       WHERE build_id=? ORDER BY ticker,variant""",[parent[0]]).fetchall()
    return parent,rows

def tables(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_funding_familywise_builds_v1(
      build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,source_models_sha256 VARCHAR NOT NULL,
      parent_model_build_id VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      model_cells BIGINT NOT NULL,security_assets BIGINT NOT NULL,
      nominal_hac_p_below_05 BIGINT NOT NULL,
      holm_p_below_05 BIGINT NOT NULL,
      original_research_screen_pass BIGINT NOT NULL,
      jointly_research_screen_pass BIGINT NOT NULL,
      sign_flip_securities BIGINT NOT NULL,
      coefficient_shift_gt25pct_securities BIGINT NOT NULL,
      positive_skill_both_variants_securities BIGINT NOT NULL,
      minimum_nominal_p DOUBLE NOT NULL,
      minimum_holm_adjusted_p DOUBLE NOT NULL,
      issuer_first_published_at_verified BOOLEAN NOT NULL,
      corporate_action_price_vintage_verified BOOLEAN NOT NULL,
      redistribution_rights_verified BOOLEAN NOT NULL,
      institutional_risk_beta_released BOOLEAN NOT NULL,
      disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_joint_funding_familywise_models_v1(
      build_id VARCHAR NOT NULL,ticker VARCHAR NOT NULL,variant VARCHAR NOT NULL,
      familywise_rank BIGINT NOT NULL,funding_beta DOUBLE NOT NULL,
      funding_hac_se DOUBLE NOT NULL,nominal_hac_p DOUBLE NOT NULL,
      holm_familywise_p DOUBLE NOT NULL,nominal_p_below_05 BOOLEAN NOT NULL,
      holm_p_below_05 BOOLEAN NOT NULL,heldout_incremental_skill DOUBLE NOT NULL,
      training_half_sign_stable BOOLEAN NOT NULL,
      prior_original_research_state VARCHAR NOT NULL,
      full_to_trim_funding_sign_flip BOOLEAN NOT NULL,
      relative_full_to_trim_beta_shift DOUBLE NOT NULL,
      trimmed_training_days_excluded BIGINT NOT NULL,
      familywise_research_state VARCHAR NOT NULL,
      institutional_beta_released BOOLEAN NOT NULL)""")

def append_validated_audit(con,run,sha,digest,original_hash,parent,report):
    """Append only after independent source check; rollback all writes on error."""
    if report["models"]!=FAMILY or report["assets"]!=ASSETS or len(report["rows"])!=FAMILY:
        raise ValueError("Incomplete source models cannot persist")
    tables(con)
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"""INSERT INTO {P}lab_joint_funding_familywise_builds_v1
           VALUES (?,?,?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,FALSE,
             'HAC_MULTIPLE_TESTING_AND_VARIANT_DRIFT_RESEARCH_ONLY')""",
          [run,sha,digest,original_hash,parent[0],report["models"],
           report["assets"],report["nominal_hac_p_below_05"],
           report["holm_p_below_05"],report["original_research_screen_pass"],
           report["joint_screen_pass"],report["sign_flip_assets"],
           report["relative_shift_gt25_assets"],
           report["positive_oos_both_variants"],
           report["min_nominal_p"],report["min_holm_adjusted_p"]])
        con.executemany(f"""INSERT INTO {P}lab_joint_funding_familywise_models_v1
          VALUES ({','.join('?' for _ in range(18))})""",
          [(run,*entry,False) for entry in report["rows"]])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40
        or any(ch not in "0123456789abcdef" for ch in sha)):
        raise RuntimeError("Only pinned Git source and internal research scope allowed")
    import duckdb
    run=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        parent,original=read_parent(con)
        report=score(original)
        original_hash=hashlib.sha256(repr(original).encode()).hexdigest()
        append_validated_audit(con,run,sha,digest,original_hash,parent,report)
    print(f"BUILD={run} PARENT={parent[0]} MODELS={report['models']}")
    print(f"NOMINAL_HAC_P_LT_05={report['nominal_hac_p_below_05']} HOLM_P_LT_05={report['holm_p_below_05']}")
    print(f"BASE_SCREEN_PASS={report['original_research_screen_pass']} JOINT_SCREEN_PASS={report['joint_screen_pass']}")
    print(f"SECURITY_SIGN_FLIPS={report['sign_flip_assets']} SECURITY_BETA_SHIFTS_GT25PCT={report['relative_shift_gt25_assets']}")
    print("ASYMPTOTIC_PVALUES_ONLY=TRUE CROSS_SECTION_DEPENDENCE_UNRESOLVED=TRUE")
    print("PUBLICATION_PIT=FALSE LICENSE_RIGHTS=FALSE INSTITUTIONAL_BETA_RELEASE=FALSE")

if __name__=="__main__":
    main()
