#!/usr/bin/env python3
"""Audit every institutional field contract and populate a durable gap ledger.

This is a read-only audit against existing source data. The only writes are
new versioned metadata tables owned by the Factor Lab. There are deliberately
NO automatic fixes, inferred source publication timestamps or approval flags.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from institutional_data_contracts import CONTRACTS, validate_contracts

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-field-contracts-v1.0.0"


def expected_type_class(field):
    """Target class; not a claim the source actually has this type."""
    f=field.lower()
    if f in {
        "evidence_approved","historical_point_in_time_released",
        "provider_quote_freshness_verified","capture_time_verified",
        "source_availability_pit_verified","corporate_action_vintage_verified",
        "published_vintage_independently_verified","point_in_time_verified",
        "independent_data_rights_verified","released_for_risk_use",
        "event_to_factor_mapping_approved","redistribution_allowed",
        "total_return_verified","publication_time_independently_verified",
        "innovation_method_approved","asof_tradable_at_verified",
        "released_for_signal_use","approved_for_use","independently_verified_asof",
        "license_use_approved","independent_replay_verified",
        "historically_backtest_released","historical_mapping_lookahead",
        "active","large_absolute_log_return"
    } or f.endswith(("_verified","_released","_allowed")):
        return "BOOLEAN"
    if f in {"date","observed_date","factor_observed_date","vintage_date","asof_date",
             "observation_date","previous_observed_date","symbol_history_valid_from",
             "symbol_history_valid_to","source_realtime_start","source_realtime_end",
             "mapping_valid_from","mapping_valid_to"}:
        return "DATE_OR_TIMESTAMP"
    if f.endswith(("_at","_timestamp","_through")) or f in {"retrieved_at"}:
        return "TIMESTAMPTZ"
    if f in {"probability","yes_probability","prior_probability","post_probability",
             "expected_probability_change","event_surprise_pp","shock_value",
             "factor_value","factor_return","adjusted_close","previous_close",
             "adj_close","close","volume","yes_bid","yes_ask","last_price",
             "reported_value","base_market_value","market_value","price",
             "quantity","base_fx_rate","beta","beta_rate","beta_spy",
             "standard_error","rate_bh_fdr_q","test_r2_vs_spy_only",
             "return_bps","shock_bps","yield_level_pct",
             "previous_yield_level_pct","residual_risk","confidence_interval",
             "large_return_observations","factor_direction_convention",
             "independent_market_beta"}:
        return "NUMERIC_OR_DEFINED"
    if f in {"contract_json","ontology_relation_ids"}:
        return "JSON"
    return "STRING_OR_DEFINED"


def standard_type_name(t):
    x=str(t).upper()
    if "TIMESTAMP WITH TIME ZONE" in x or "TIMESTAMPTZ" in x:
        return "TIMESTAMPTZ"
    if x in ("DATE",): return "DATE"
    if "JSON" in x:return "JSON"
    if x in ("VARCHAR","TEXT","STRING"):return "STRING"
    if any(x.startswith(prefix) for prefix in
           ("DOUBLE","FLOAT","DECIMAL","BIGINT","INTEGER","SMALLINT","TINYINT","UBIGINT","HUGEINT")):
        return "NUMERIC"
    if x=="BOOLEAN":return "BOOLEAN"
    return "OTHER"


def satisfies_type(expected, actual):
    if expected=="BOOLEAN":return actual=="BOOLEAN"
    if expected=="TIMESTAMPTZ":return actual=="TIMESTAMPTZ"
    if expected=="DATE_OR_TIMESTAMP":return actual in {"DATE","TIMESTAMPTZ"}
    if expected=="NUMERIC_OR_DEFINED":return actual=="NUMERIC"
    if expected=="JSON":return actual=="JSON"
    return True


def materialize(con,build,commit,code_hash):
    validate_contracts()
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_institutional_field_contracts_v1(
      build_id VARCHAR NOT NULL,dataset_id VARCHAR NOT NULL,
      source_table VARCHAR NOT NULL,grain VARCHAR NOT NULL,
      domain_tier VARCHAR NOT NULL,field_name VARCHAR NOT NULL,
      requirement_level VARCHAR NOT NULL,expected_type_class VARCHAR NOT NULL,
      unit_policy VARCHAR NOT NULL,temporal_policy VARCHAR NOT NULL,
      license_policy VARCHAR NOT NULL,methodology_notes VARCHAR NOT NULL,
      source_git_commit VARCHAR NOT NULL,source_script_sha256 VARCHAR NOT NULL)
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_institutional_field_audit_v1(
      build_id VARCHAR NOT NULL,dataset_id VARCHAR NOT NULL,
      source_table VARCHAR NOT NULL,field_name VARCHAR NOT NULL,
      requirement_level VARCHAR NOT NULL,source_table_exists BOOLEAN NOT NULL,
      actual_source_type VARCHAR,
      expected_type_class VARCHAR NOT NULL,
      type_class_pass BOOLEAN,
      source_table_rows BIGINT NOT NULL,
      nonnull_field_rows BIGINT NOT NULL,
      nonnull_rate DOUBLE,
      inventory_status VARCHAR NOT NULL,
      independently_certified_for_production BOOLEAN NOT NULL,
      source_git_commit VARCHAR NOT NULL)
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_institutional_dataset_audit_v1(
      build_id VARCHAR NOT NULL,dataset_id VARCHAR NOT NULL,
      source_table VARCHAR NOT NULL,grain VARCHAR NOT NULL,
      table_exists BOOLEAN NOT NULL,source_row_count BIGINT NOT NULL,
      total_fields_required BIGINT NOT NULL,
      required_fields_missing BIGINT NOT NULL,
      required_fields_unpopulated BIGINT NOT NULL,
      populated_required_fields BIGINT NOT NULL,
      source_certification_complete BOOLEAN NOT NULL,
      data_class VARCHAR NOT NULL,
      status VARCHAR NOT NULL,source_git_commit VARCHAR NOT NULL)
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_institutional_data_contract_builds_v1(
      build_id VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      source_git_commit VARCHAR NOT NULL,source_script_sha256 VARCHAR NOT NULL,
      contracts_defined BIGINT NOT NULL,field_rules_defined BIGINT NOT NULL,
      required_fields_missing BIGINT NOT NULL,
      required_fields_unpopulated BIGINT NOT NULL,
      uncertified_required_fields BIGINT NOT NULL,
      institutional_release_approved BOOLEAN NOT NULL,
      release_state VARCHAR NOT NULL)
    """)
    meta=con.execute("""
        SELECT table_name,column_name,data_type
        FROM information_schema.columns
        WHERE table_catalog=? AND table_schema='main'
    """,[DB]).fetchall()
    sources={}
    for table,field,t in meta:
        sources.setdefault(table,{})[field]=t
    inventory=[]
    audit=[]
    dataset_reports=[]
    for spec in CONTRACTS:
        columns=sources.get(spec.source_table,{})
        exists=bool(columns)
        definition=[(f,"technical") for f in spec.required_technical]+[
            (f,"institutional") for f in spec.required_institutional]+[
            (f,"optional") for f in spec.optional]
        distinct_present=[f for f,lv in definition if f in columns]
        # Aggregate all present columns in one bounded read scan per table.
        count=0
        nonnull={}
        if exists:
            pieces=["count(*) AS n"]
            for f in distinct_present:
                typ=standard_type_name(columns[f])
                if typ=="STRING":
                    pieces.append(f'count(NULLIF(trim("{f}"),\'\')) AS "{f}"')
                else:
                    pieces.append(f'count("{f}") AS "{f}"')
            curs=con.execute(
                f"SELECT {', '.join(pieces)} FROM {P}{spec.source_table}"
            ).fetchone()
            count=curs[0]
            nonnull=dict(zip(distinct_present,curs[1:]))
        missing=empty=populated=0
        for field,level in definition:
            expected=expected_type_class(field)
            observed=columns.get(field)
            actual=standard_type_name(observed) if observed is not None else None
            typok=satisfies_type(expected,actual) if observed is not None else None
            filled=nonnull.get(field,0)
            rate=filled/count if exists and count else None
            if not exists:
                state="MISSING_DATASET"
            elif observed is None:
                state="MISSING_FIELD"
            elif typok is False:
                state="TYPE_MISMATCH"
            elif count==0 or filled==0:
                state="EMPTY"
            elif filled<count:
                state="PARTIALLY_POPULATED"
            else:
                state="POPULATED_NOT_CERTIFIED"
            if level!="optional":
                if state in {"MISSING_DATASET","MISSING_FIELD","TYPE_MISMATCH"}:
                    missing+=1
                elif state=="EMPTY":
                    empty+=1
                elif state in {"PARTIALLY_POPULATED","POPULATED_NOT_CERTIFIED"}:
                    populated+=1
            inventory.append((
                build,spec.dataset,spec.source_table,spec.grain,spec.tier,
                field,level,expected,spec.unit_policy,spec.temporal_policy,
                spec.license_policy,spec.notes,commit,code_hash
            ))
            audit.append((
                build,spec.dataset,spec.source_table,field,level,exists,
                observed,expected,typok,count,filled,rate,state,False,commit
            ))
        total=len(spec.required_technical)+len(spec.required_institutional)
        status=(
            "DATASET_NOT_LOADED" if not exists else
            "REQUIRED_SOURCE_FIELDS_MISSING" if missing else
            "REQUIRED_SOURCE_FIELDS_UNPOPULATED" if empty else
            "UNVERIFIED_SOURCE_AND_MODEL_RELEASE"
        )
        dataset_reports.append((build,spec.dataset,spec.source_table,
            spec.grain,exists,count,total,missing,empty,populated,
            False,spec.tier,status,commit))
    con.execute("BEGIN TRANSACTION")
    try:
        con.executemany(f"""
          INSERT INTO {P}lab_institutional_field_contracts_v1
          VALUES ({','.join(['?']*14)})
        """,inventory)
        con.executemany(f"""
          INSERT INTO {P}lab_institutional_field_audit_v1
          VALUES ({','.join(['?']*15)})
        """,audit)
        con.executemany(f"""
          INSERT INTO {P}lab_institutional_dataset_audit_v1
          VALUES ({','.join(['?']*14)})
        """,dataset_reports)
        missing_total=sum(row[7] for row in dataset_reports)
        empty_total=sum(row[8] for row in dataset_reports)
        required_total=sum(row[6] for row in dataset_reports)
        con.execute(f"""
          INSERT INTO {P}lab_institutional_data_contract_builds_v1
          VALUES (?,current_timestamp,?,?,?,?,?,?,?,FALSE,
                  'RELEASE_BLOCKED_SOURCE_CERTIFICATIONS_INCOMPLETE')
        """,[
            build,commit,code_hash,len(CONTRACTS),len(inventory),
            missing_total,empty_total,required_total
        ])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return dataset_reports,len(inventory),missing_total,empty_total,required_total


def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(x not in "0123456789abcdef" for x in commit):
        raise RuntimeError("Internal-only scope and immutable 40-character source SHA required")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        datasets,fields,missing,empty,required=materialize(con,build,commit,digest)
    print("BUILD_ID="+build)
    print(f"DATA_CONTRACTS={len(datasets)} FIELD_RULES={fields} REQUIRED={required}")
    print(f"REQUIRED_FIELDS_MISSING={missing} REQUIRED_FIELDS_EMPTY={empty}")
    for rec in datasets:
        print(f"DATASET={rec[1]} ROWS={rec[5]} MISSING_REQUIRED={rec[7]} EMPTY_REQUIRED={rec[8]} STATUS={rec[12]}")
    print("INDEPENDENT_DATA_CERTIFICATION=NONE; INSTITUTIONAL_RELEASE=BLOCKED")


if __name__=="__main__":
    main()
