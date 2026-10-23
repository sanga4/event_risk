#!/usr/bin/env python3
"""Materialize auditable Phase I release gates; never self-approve a release."""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import duckdb

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-gates-v1.0.0"

def main():
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only":
        raise RuntimeError("LAB_RESEARCH_SCOPE must be internal-only")
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("require full source commit SHA")
    code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    build_id=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    gates=[
        ("genuine_pit_factor_panel",
         f"SELECT COUNT(*) FROM {P}lab_event_factor_panel_v3 WHERE observed_mode='as_known' AND data_lookahead_warning=FALSE",
         10000,"MIN_COUNT", "Require >=10,000 vintage-correct as-known observations; zero currently"),
        ("reviewed_factor_evidence",
         f"SELECT COUNT(*) FROM {P}lab_relations WHERE status IN ('approved','accepted') AND evidence_id IS NOT NULL",
         1,"MIN_COUNT","Require independently approved factor mappings linked to evidence"),
        ("source_evidence",
         f"SELECT COUNT(*) FROM {P}lab_evidence",
         1,"MIN_COUNT","Evidence records must support signed reviewer decisions"),
        ("independent_mapping_reviews",
         f"SELECT COUNT(*) FROM {P}lab_mapping_review_cases WHERE reviewer IS NOT NULL AND reviewed_at IS NOT NULL AND analyst_decision IS NOT NULL",
         10,"MIN_COUNT","At least 10 analyst-reviewed mapping samples; not an approval by itself"),
        ("real_time_venue_data_recent",
         f"SELECT COALESCE(date_diff('hour',MAX(ts),current_timestamp),999999) FROM {P}market_snapshots WHERE source='realtime'",
         12,"MAX_HOURS","Realtime snapshots must be younger than 12 hours"),
        ("historical_quote_pit_fraction",
         f"SELECT 100.0 * COALESCE(AVG(CASE WHEN point_in_time_verified THEN 1.0 ELSE 0.0 END),0) FROM {P}lab_market_daily_historical_v1",
         80,"MIN_PERCENT","At least 80% of eligible history must have independently verified capture provenance"),
        ("independent_oos_candidate_signals",
         f"SELECT COUNT(*) FROM {P}lab_robust_regressions_v2 WHERE benjamini_hochberg_q < 0.05 AND oos_r2_vs_train_mean > 0 AND point_in_time_verified = TRUE",
         1,"MIN_COUNT","Pre-specified PIT holdout candidate; exploratory fits cannot satisfy this gate"),
        ("historical_research_pipeline_built",
         f"SELECT COUNT(*) FROM {P}lab_history_build_runs_v1",
         1,"MIN_COUNT","Historical research materialization exists; not PIT validity"),
        ("robust_diagnostics_pipeline_built",
         f"SELECT COUNT(*) FROM {P}lab_robust_regression_builds_v2",
         1,"MIN_COUNT","HAC/holdout/FDR diagnostic build exists; not causal approval")
    ]
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_release_gate_history_v1 (
      build_id VARCHAR NOT NULL,
      gate_id VARCHAR NOT NULL,
      measured_value DOUBLE,
      threshold DOUBLE,
      rule VARCHAR NOT NULL,
      gate_state VARCHAR NOT NULL,
      explanation VARCHAR NOT NULL,
      asof_utc TIMESTAMPTZ NOT NULL,
      source_commit VARCHAR NOT NULL,
      source_script_sha256 VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_release_gate_summary_v1 (
      build_id VARCHAR NOT NULL,
      asof_utc TIMESTAMPTZ NOT NULL,
      computed_gates BIGINT NOT NULL,
      passed_gates BIGINT NOT NULL,
      blocked_gates BIGINT NOT NULL,
      external_manual_gates BIGINT NOT NULL,
      released_to_institutional_production BOOLEAN NOT NULL,
      release_state VARCHAR NOT NULL
    )""")
    rows=[]
    for gate_id,sql,threshold,rule,explanation in gates:
        value=con.execute(sql).fetchone()[0]
        value=float(value) if value is not None else None
        passed = value is not None and (
            (rule=="MIN_COUNT" and value>=threshold) or
            (rule=="MAX_HOURS" and 0 <= value <= threshold) or
            (rule=="MIN_PERCENT" and value>=threshold)
        )
        rows.append((build_id,gate_id,value,float(threshold),rule,
                     "PASS" if passed else "BLOCKED",explanation,
                     datetime.now(timezone.utc),commit,code_sha))
    manual=[
        ("railway_service_data_rights", "Requires owner-confirmed Railway LAB_DATA_RIGHTS_ACK, scoped token and API keys"),
        ("independent_research_signoff", "Requires independent statistical and governance approval, not automatic data metrics"),
        ("licensed_market_data_review", "Review redistribution and credit licenses before external serving"),
        ("institutional_access_controls", "Requires verified authentication, monitoring, alerting and rollback"),
    ]
    for name,why in manual:
        rows.append((build_id,name,None,None,"MANUAL_EXTERNAL",
                     "BLOCKED_MANUAL",why,datetime.now(timezone.utc),commit,code_sha))
    n_pass=sum(row[5]=="PASS" for row in rows)
    con.execute("BEGIN TRANSACTION")
    try:
        con.executemany(f"INSERT INTO {P}lab_release_gate_history_v1 VALUES (?,?,?,?,?,?,?,?,?,?)",rows)
        con.execute(f"""INSERT INTO {P}lab_release_gate_summary_v1
            VALUES (?,current_timestamp,?,?,?, ?,FALSE,'BLOCKED_NOT_INSTITUTIONALLY_APPROVED')""",
            [build_id,len(gates),n_pass,len(gates)-n_pass,len(manual)])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    print(f"BUILD_ID={build_id}")
    print(f"AUTOMATIC_GATES={len(gates)} PASS={n_pass} BLOCKED={len(gates)-n_pass}")
    print(f"MANUAL_RELEASE_GATES_BLOCKED={len(manual)}")
    print("INSTITUTIONAL_RELEASE=BLOCKED")


if __name__=="__main__":
    main()
