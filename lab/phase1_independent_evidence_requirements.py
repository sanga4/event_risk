#!/usr/bin/env python3
"""Source-evidence intake worklist for corporate actions, duplicate FX and mappings.

Materialize mandatory exact source evidence requirements and independent dual
review fields; *never* infer real market split/dividend/error from a big return.
This worklist is a REVIEW REQUIREMENT, not evidence of an externally verified
source or self-approval. Snapshot identifiers are stable across builds.
"""
from __future__ import annotations
import hashlib,os
from datetime import datetime,timezone
from pathlib import Path
import duckdb

DB="eventrisk_factor_lab";P=DB+".main."
VERSION="phase1-independent-evidence-review-v1.0.0"
REQUIRED_PRICE=(
 ("original_unadjusted_exchange_close","LICENSABLE_EXCHANGE_OR_VENDOR_SOURCE","original effective trade/date, price, exchange MIC, retrieval and first-source timestamp"),
 ("split_dividend_adjustment_asof","PROVIDER_CORPORATE_ACTION_HISTORY","split/dividend/ex date, issuer permanent ID, as-known-at adjustment factor/revision"),
 ("independent_same_day_corroboration","SEPARATE_INDEPENDENT_MARKET_SOURCE","second independent quote and as-of evidence or justified absent"),
 ("reviewer_and_second_approval","INDEPENDENT_DATA_STEWARD_AND_MODEL_RISK","two attributed decisions with evidence checksums and no automatic waiver")
)
REQUIRED_FX=(
 ("quote_pair_direction","ORIGINAL_FX_MARKET_PROVIDER","base/quote currency units, fixing time and exact initial provider payload"),
 ("original_quote_conflict","INDEPENDENT_RATE_QUOTE_HISTORY","which duplicated rate is historically correct and why, before any overwrite"),
 ("FX_reviewer_signoff","SECOND_INDEPENDENT_REVIEWER","signed reference orientation & revision evidence, vendor license scope")
)
REQUIRED_MAPPING=(
 ("first_available_original_event_source","ORIGINAL_PUBLICATION_RECORD","source event URL, original publication timestamp, content checksum"),
 ("economic_transmission_rationale","ATTRIBUTABLE_ANALYST_SOURCE","specific growth, inflation, cashflow, default, policy or risk appetite path"),
 ("identifiable_factor_response","IDENTIFIED_MACRO_FACTOR_SURPRISE","factor observation first-available clock, sign and alternatives"),
 ("dual_review_and_commercial_rights","INDEPENDENT_REVIEW_AND_RIGHTS","reviewer+second signoff, independent evidence, no hindsight")
)

def key(kind,ref,requirement):
    return hashlib.sha256(f"{kind}|{ref}|{requirement}".encode()).hexdigest()[:32]

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise RuntimeError("Pinned source SHA and internal-only evidence triage required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_independent_evidence_requirements_v1(
          build_id VARCHAR NOT NULL,requirement_id VARCHAR NOT NULL,
          subject_class VARCHAR NOT NULL,subject_key VARCHAR NOT NULL,
          ticker_or_venue VARCHAR,original_observed_date DATE,
          required_evidence_type VARCHAR NOT NULL,
          acceptable_original_source_class VARCHAR NOT NULL,
          evidence_description VARCHAR NOT NULL,
          original_source_uri VARCHAR,source_archived_sha256 VARCHAR,
          source_original_published_at TIMESTAMPTZ,
          original_provider_revision_at TIMESTAMPTZ,
          permitted_use_license_evidence VARCHAR,
          reviewer_id VARCHAR,reviewed_at TIMESTAMPTZ,
          independent_second_reviewer_id VARCHAR,
          second_approved_at TIMESTAMPTZ,
          factual_evidence_verified BOOLEAN NOT NULL,
          independent_review_complete BOOLEAN NOT NULL,
          institutional_risk_use_approved BOOLEAN NOT NULL,
          requirement_state VARCHAR NOT NULL)
        """)
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_independent_evidence_builds_v1(
          build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
          source_code_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
          abnormal_security_price_cases BIGINT NOT NULL,
          duplicate_fx_quote_groups BIGINT NOT NULL,
          mapping_hypotheses_pending_review BIGINT NOT NULL,
          evidence_requirements BIGINT NOT NULL,
          original_source_records_verified BIGINT NOT NULL,
          independently_approved_decisions BIGINT NOT NULL,
          institutionally_approved_risk_links BIGINT NOT NULL,
          release_state VARCHAR NOT NULL)
        """)
        # Stable review subjects on the latest native source QA build only.
        abnormal=con.execute(f"""
          SELECT ticker,observed_date
          FROM {P}lab_security_price_exception_cases_v1
          WHERE build_id=(SELECT build_id FROM {P}lab_security_price_exception_builds_v1
             ORDER BY built_at DESC LIMIT 1)
          ORDER BY ticker,observed_date
        """).fetchall()
        duplicate=con.execute(f"""
          SELECT ticker,observed_date
          FROM {P}lab_security_duplicate_quote_cases_v1
          WHERE build_id=(SELECT build_id FROM {P}lab_security_price_exception_builds_v1
             ORDER BY built_at DESC LIMIT 1)
          ORDER BY ticker,observed_date
        """).fetchall()
        maps=con.execute(f"""
          SELECT review_id,venue,first_eligible_capture_at,review_state,reviewer,reviewed_at
          FROM {P}lab_forward_mapping_review_queue_v1
          WHERE review_state NOT IN ('APPROVED','REJECTED')
          ORDER BY review_id
        """).fetchall()
        if len(abnormal)!=12 or len(duplicate)!=4 or len(maps)<50:
            raise RuntimeError("Unexpected source or mapping review universe; do not write partial worklist")
        rows=[]
        def include(subject,ref,label,day,requirements):
            for code,source_class,note in requirements:
                rows.append((
                    build,key(subject,ref,code),subject,ref,label,day,
                    code,source_class,note,None,None,None,None,None,
                    None,None,None,None,False,False,False,
                    "MISSING_ORIGINAL_SOURCE_AND_SIGNED_REVIEW"
                ))
        for ticker,day in abnormal:
            include("ADJUSTED_PRICE_EXCURSION",f"{ticker}:{day}",ticker,day,REQUIRED_PRICE)
        for ticker,day in duplicate:
            include("DUPLICATE_FX_SOURCE_QUOTE",f"{ticker}:{day}",ticker,day,REQUIRED_FX)
        for rid,venue,first_capture,status,reviewer,reviewed in maps:
            include("EVENT_ECONOMIC_CHANNEL_MAPPING",rid,venue,
                    first_capture.date() if first_capture else None,REQUIRED_MAPPING)
        if len({z[1] for z in rows})!=len(rows):
            raise RuntimeError("Evidence requirement hash collision or duplicate")
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(f"INSERT INTO {P}lab_independent_evidence_requirements_v1 "
                          f"VALUES ({','.join(['?']*22)})",rows)
            con.execute(f"""
              INSERT INTO {P}lab_independent_evidence_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,0,0,0,
                'INDEPENDENT_ORIGINAL_SOURCE_EVIDENCE_NOT_PRESENT')
            """,[build,sha,digest,len(abnormal),len(duplicate),len(maps),len(rows)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build}")
        print(f"SECURITY_PRICE_CASES={len(abnormal)} FX_DUPLICATE_CASES={len(duplicate)}")
        print(f"EVENT_MAPPING_REVIEW_CASES={len(maps)}")
        print(f"REQUIREMENTS_NEED_REAL_EVIDENCE={len(rows)}")
        print("VERIFIED_ORIGINAL_SOURCE_ITEMS=0 SECOND_SIGNOFFS=0 MODEL_RELEASE=FALSE")

if __name__=="__main__":
    main()
