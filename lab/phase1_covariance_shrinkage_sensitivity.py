#!/usr/bin/env python3
"""Predeclared covariance shrinkage stress sweep over recorded 7×7 research matrices.

Does not tune an approved production model or simulate portfolio P&L.
One historical training/holdout matrix already computed, not PIT licensed.
Covariance is dimensionless AFTER training-only standardization across
Treasury yield shocks, ECB informational quote/EUR changes, French portfolio
simple returns. Gaussian covariance-only pseudo-log score uses a test
sample covariance; lower is relatively better on this same retrospective
heldout period, not investable predictive accuracy. Compare fixed values,
do not silently pick the hindsight winner.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib,math,os
import duckdb,numpy as np

P="eventrisk_factor_lab.main."
VERSION="phase1-cross-asset-shrink-sensitivity-v1.0.0"
FRACTIONS=(0.0,0.10,0.25,0.50,0.75,1.0)
FACTORS=("CURVE_LEVEL_BPS","CURVE_SLOPE_BPS","CURVE_CURVATURE_BPS",
 "ECB_EUR_USD_QUOTE_BPS","ECB_EUR_JPY_QUOTE_BPS",
 "FF_US_MKT_RF_RETURN_BPS","FF_US_MOM_RETURN_BPS")

def diagnostic(train,holdout,shrink):
    tr=np.asarray(train,dtype=float);ho=np.asarray(holdout,dtype=float)
    if tr.shape!=(7,7) or ho.shape!=(7,7):
        raise ValueError("Requires complete 7×7 train and holdout covariance")
    if not np.isfinite(tr).all() or not np.isfinite(ho).all():
        raise ValueError("Nonfinite sample covariance")
    if not np.allclose(tr,tr.T,atol=1e-6) or not np.allclose(ho,ho.T,atol=1e-6):
        raise ValueError("Covariance must be symmetric")
    if not 0<=shrink<=1:raise ValueError("Invalid shrink")
    est=(1-shrink)*tr+shrink*np.diag(np.diag(tr))
    vals=np.linalg.eigvalsh(est)
    if min(vals)<=1e-8:raise ValueError("Nonpositive estimated covariance")
    sign,logdet=np.linalg.slogdet(est)
    if sign<=0:raise ValueError("Nonpositive covariance determinant")
    score=float(logdet+np.trace(np.linalg.solve(est,ho)))
    error=float(np.linalg.norm(est-ho,ord='fro')/
                np.linalg.norm(est,ord='fro'))
    variance=np.diag(ho)/np.diag(est)
    largest_ratio=float(np.max(np.maximum(variance,1/variance)))
    return {"gaussian_covariance_score":score,"relative_covariance_error":error,
            "condition":float(max(vals)/min(vals)),
            "min_eigenvalue":float(min(vals)),
            "largest_variance_ratio":largest_ratio}

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("Internal-only immutable Git SHA required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_factor_covariance_shrinkage_tests_v1(
         build_id VARCHAR NOT NULL,source_covariance_build_id VARCHAR NOT NULL,
         fixed_training_shrinkage_fraction DOUBLE NOT NULL,
         gaussian_holdout_covariance_pseudologscore DOUBLE NOT NULL,
         relative_holdout_covariance_distance DOUBLE NOT NULL,
         training_covariance_condition DOUBLE NOT NULL,
         min_training_covariance_eigenvalue DOUBLE NOT NULL,
         largest_holdout_variance_ratio DOUBLE NOT NULL,
         hindsight_selection_prohibited BOOLEAN NOT NULL,
         source_pit_certified BOOLEAN NOT NULL,
         original_provider_data_rights_approved BOOLEAN NOT NULL,
         portfolio_risk_model_approved BOOLEAN NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_factor_covariance_shrinkage_builds_v1(
         build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
         code_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
         source_covariance_build_id VARCHAR NOT NULL,
         prespecified_candidate_models BIGINT NOT NULL,
         source_factor_dimensions BIGINT NOT NULL,
         source_joint_observations BIGINT NOT NULL,
         training_observations BIGINT NOT NULL,
         holdout_observations BIGINT NOT NULL,
         candidates_with_covariance_distance_over_50pct BIGINT NOT NULL,
         worst_relative_holdout_distance DOUBLE NOT NULL,
         lowest_heldout_pseudoscore_fraction_exploratory DOUBLE NOT NULL,
         retrospectively_selected_for_production BOOLEAN NOT NULL,
         institutional_factor_risk_released BOOLEAN NOT NULL,
         status VARCHAR NOT NULL
        )""")
        builds=con.execute(f"""
        SELECT build_id,n_factors,n_joint_observations,n_train,n_holdout
        FROM {P}lab_cross_asset_risk_diagnostics_v1
        ORDER BY built_at DESC LIMIT 1
        """).fetchone()
        if builds is None:raise RuntimeError("Missing source cross asset covariance")
        source_id,nf,nall,ntrain,ntest=builds
        cells=con.execute(f"""
         SELECT factor_a,factor_b,standardized_train_sample_covariance,
                holdout_standardized_sample_covariance
         FROM {P}lab_cross_asset_factor_covariance_v1
         WHERE build_id=?
        """,[source_id]).fetchall()
        names={v:i for i,v in enumerate(FACTORS)}
        tr=np.zeros((7,7));ho=np.zeros((7,7));present=set()
        for a,b,t,h in cells:
            if a not in names or b not in names:raise ValueError("Unknown covariance factor")
            i,j=names[a],names[b]
            if (i,j) in present:raise ValueError("Duplicate covariance cell")
            present.add((i,j));tr[i,j]=float(t);ho[i,j]=float(h)
        if len(present)!=49 or nf!=7 or nall<500 or ntrain<350 or ntest<120:
            raise RuntimeError("Incomplete native covariance research source")
        vals=[diagnostic(tr,ho,x) for x in FRACTIONS]
        scores=np.asarray([v["gaussian_covariance_score"] for v in vals])
        best=FRACTIONS[int(np.argmin(scores))]
        rows=[(
            build,source_id,x,d["gaussian_covariance_score"],
            d["relative_covariance_error"],d["condition"],d["min_eigenvalue"],
            d["largest_variance_ratio"],True,False,False,False
            ) for x,d in zip(FRACTIONS,vals)]
        flagged=sum(r[4]>.5 for r in rows)
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(f"INSERT INTO {P}lab_factor_covariance_shrinkage_tests_v1 VALUES ({','.join(['?']*12)})",rows)
            con.execute(f"""
             INSERT INTO {P}lab_factor_covariance_shrinkage_builds_v1
             VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,FALSE,FALSE,
                     'RESEARCH_SENSITIVITY_NO_HOLDOUT_MODEL_SELECTION_OR_PORTFOLIO_RELEASE')
            """,[build,sha,digest,source_id,len(rows),nf,nall,ntrain,ntest,
                  flagged,max(r[4] for r in rows),best])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build} SOURCE_COVARIANCE_BUILD={source_id}")
        for x,d in zip(FRACTIONS,vals):
            print(f"SHRINK={x:.2f} HOLDOUT_PSEUDOLOGSCORE={d['gaussian_covariance_score']:.5f} HOLDOUT_DRIFT={d['relative_covariance_error']:.5f} TRAIN_CONDITION={d['condition']:.3f}")
        print(f"HINDSIGHT_MINIMUM_SCORE_SHRINKAGE_NOT_ELIGIBLE_FOR_PRODUCTION={best:.2f}")
        print("INDEPENDENT_RISK_VALIDATION=FALSE LICENSED_PORTFOLIO_COVARIANCE=FALSE")
    finally:
        con.close()

if __name__=="__main__":
    main()
