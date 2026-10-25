#!/usr/bin/env python3
"""Append-only event-factor temporal/units semantic firewall, never PIT approval.

v2 and v3 historically co-observe revised Treasury factors with event prices,
while the newer grid enforces warehouse-receipt timing only. Recheck both and
detect silent v2/v3 carry-date semantic changes before anyone can use a panel
in a production factor or event-causality model.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import os

P="eventrisk_factor_lab.main."
VERSION="phase1-event-panel-semantics-v1.0.0"
DATASETS=("RETROSPECTIVE_V2","RETROSPECTIVE_V3","WAREHOUSE_ASOF")
EXPECTED_FACTORS=18
# Per-factor fields: factor_id,n,after_cutoff,lookahead_warning,carried,paired,bad_contract
SQL={
"RETROSPECTIVE_V2":f"""
 SELECT factor_id,count(*),count(*) FILTER(WHERE factor_available_at>event_cutoff_at),
   count(*) FILTER(WHERE data_lookahead_warning),
   count(*) FILTER(WHERE factor_carried_forward),
   count(*) FILTER(WHERE event_delta_pp IS NOT NULL AND factor_daily_change IS NOT NULL),
   count(*) FILTER(WHERE probability<0 OR probability>1 OR NOT isfinite(probability)
     OR factor_observed_date>observed_date OR
     (factor_available_at>event_cutoff_at AND NOT data_lookahead_warning)
     OR factor_change_unit<>'bps' OR length(factor_source_sha256)<>64
     OR mode<>'retrospective')
 FROM {P}lab_event_factor_panel_v2 GROUP BY factor_id ORDER BY factor_id
""",
"RETROSPECTIVE_V3":f"""
 SELECT factor_id,count(*),count(*) FILTER(WHERE
      factor_available_at>event_known_at OR factor_ingested_at>event_known_at),
   count(*) FILTER(WHERE data_lookahead_warning),
   count(*) FILTER(WHERE factor_carried_forward),
   count(*) FILTER(WHERE event_delta_pp IS NOT NULL AND factor_change_bps IS NOT NULL),
   count(*) FILTER(WHERE event_probability<0 OR event_probability>1
      OR NOT isfinite(event_probability)
      OR factor_observed_date>observed_date
      OR ((factor_available_at>event_known_at OR factor_ingested_at>event_known_at)
         AND NOT data_lookahead_warning)
      OR factor_unit<>'percent' OR length(factor_source_sha256)<>64
      OR observed_mode<>'retrospective'
      OR relation_status<>'unreviewed_research_grid'
      OR data_use_class<>'internal_research_only')
 FROM {P}lab_event_factor_panel_v3 GROUP BY factor_id ORDER BY factor_id
""",
"WAREHOUSE_ASOF":f"""
 SELECT factor_id,count(*),count(*) FILTER(WHERE
       factor_available_at>event_capture_at OR factor_ingested_at>event_capture_at),
   0::BIGINT,
   0::BIGINT,
   count(*) FILTER(WHERE event_delta_pp IS NOT NULL),
   count(*) FILTER(WHERE event_probability<0 OR event_probability>1
       OR NOT isfinite(event_probability) OR
       factor_observed_date>CAST(event_capture_at AS DATE)
       OR NOT event_receipt_time_verified OR NOT factor_warehouse_asof_verified
       OR exchange_quote_time_independently_verified
       OR factor_publication_time_independently_verified
       OR event_to_factor_mapping_approved OR historical_backtest_released
       OR data_use_class<>'internal_research_only'
       OR factor_unit<>'percent'
       OR length(event_source_sha256)<>64 OR length(factor_source_sha256)<>64)
 FROM {P}lab_prospective_event_factor_grid_v1 GROUP BY factor_id ORDER BY factor_id
"""
}
PAIR_SQL=f"""SELECT count(*) AS pairs,
    count(*) FILTER(WHERE a.factor_carried_forward IS DISTINCT FROM
                         b.factor_carried_forward) AS carry_disagree,
    count(*) FILTER(WHERE a.factor_observed_date IS DISTINCT FROM
                         b.factor_observed_date) AS observed_date_disagree,
    count(*) FILTER(WHERE abs(a.factor_value-b.factor_value)>1e-9
      OR abs(a.probability-b.event_probability)>1e-9
      OR a.event_delta_pp IS DISTINCT FROM b.event_delta_pp) AS value_disagree,
    count(*) FILTER(WHERE a.factor_carried_forward AND
      NOT b.factor_carried_forward AND
      a.factor_observed_date<>b.factor_observed_date) AS carried_date_relabelled
    FROM {P}lab_event_factor_panel_v2 a JOIN {P}lab_event_factor_panel_v3 b
    USING(proposition_id,factor_id,observed_date)"""
KEY_SQL={
"RETROSPECTIVE_V2":f"""SELECT count(*) FROM (SELECT proposition_id,factor_id,
  observed_date,count(*) n FROM {P}lab_event_factor_panel_v2
  GROUP BY 1,2,3 HAVING count(*)>1)""",
"RETROSPECTIVE_V3":f"""SELECT count(*) FROM (SELECT proposition_id,factor_id,
  observed_date,count(*) n FROM {P}lab_event_factor_panel_v3
  GROUP BY 1,2,3 HAVING count(*)>1)""",
"WAREHOUSE_ASOF":f"""SELECT count(*) FROM (SELECT event_run_id,venue,market_id,
  factor_id,count(*) n FROM {P}lab_prospective_event_factor_grid_v1
  GROUP BY 1,2,3,4 HAVING count(*)>1)"""
}


def summarize(bydataset, pairs, duplicates):
    """Fail closed on integrity failures, but REPORT historic lookahead as blocked."""
    if set(bydataset)!=set(DATASETS) or set(duplicates)!=set(DATASETS):
        raise ValueError("Missing expected research panels")
    totals={}
    for name in DATASETS:
        factors=bydataset[name]
        if len(factors)!=EXPECTED_FACTORS or len({row[0] for row in factors})!=EXPECTED_FACTORS:
            raise ValueError("Factor contract or uniqueness changed")
        if any(len(x)!=7 or x[1]<=0 or any(v is None or v<0 for v in x[1:])
               or x[6]!=0 or x[2]>x[1] or x[3]>x[1] or x[4]>x[1] or x[5]>x[1]
               for x in factors):
            raise ValueError("Factor panel invalid source values, units, provenance or timing")
        if duplicates[name]!=0:
            raise ValueError("Duplicate factor keys")
        totals[name]=tuple(sum(int(row[i]) for row in factors) for i in range(1,6))
        if name=="WAREHOUSE_ASOF":
            if totals[name][1] or totals[name][2]:
                raise ValueError("Prospective factor grid violates warehouse as-of semantics")
        elif totals[name][1] and totals[name][1]!=totals[name][2]:
            # No unflagged lookahead: in the current retrospective contract
            # every flag is expected to correspond to a warehouse-late factor.
            raise ValueError("Retrospective lookahead warnings inconsistent")
    if len(pairs)!=5 or pairs[0]!=totals["RETROSPECTIVE_V2"][0] or pairs[0]!=totals["RETROSPECTIVE_V3"][0] or pairs[3]:
        raise ValueError("v2/v3 keys or event and factor values do not reconcile")
    if any(v<0 or v>pairs[0] for v in pairs[1:]):
        raise ValueError("Invalid cross-version discrepancy counts")
    if pairs[4]>pairs[1] or pairs[4]>pairs[2]:
        raise ValueError("Relabelled carried dates exceed mismatch inventory")
    # Original published-at, licensed inputs, mappings and causal approval all zero.
    return dict(totals=totals,pairs=tuple(int(v) for v in pairs),
                subjects=[(name,row[0],*(int(v) for v in row[1:6]),
                           "RETROSPECTIVE_LOOKAHEAD_UNAPPROVED" if name!="WAREHOUSE_ASOF"
                           else "WAREHOUSE_RECEIPT_KNOWN_ONLY_NOT_PROVIDER_PIT")
                          for name in DATASETS for row in bydataset[name]])


def load(con):
    counts={key:con.execute(sql).fetchall() for key,sql in SQL.items()}
    duplicates={key:int(con.execute(sql).fetchone()[0]) for key,sql in KEY_SQL.items()}
    pair=con.execute(PAIR_SQL).fetchone()
    return counts,pair,duplicates


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_panel_semantic_audit_builds_v1(
        build_id VARCHAR NOT NULL, source_git_sha VARCHAR NOT NULL,
        source_script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
        v2_rows BIGINT NOT NULL,v3_rows BIGINT NOT NULL,
        warehouse_asof_rows BIGINT NOT NULL,
        v2_factor_after_event_cutoff BIGINT NOT NULL,
        v3_factor_after_event_known_at BIGINT NOT NULL,
        warehouse_asof_future_factor_rows BIGINT NOT NULL,
        v2v3_matched_rows BIGINT NOT NULL,
        v2v3_carry_flag_disagreements BIGINT NOT NULL,
        v2v3_factor_observation_date_disagreements BIGINT NOT NULL,
        v2v3_carried_date_relabellings BIGINT NOT NULL,
        certified_original_publication_rows BIGINT NOT NULL,
        institutional_release_approved BOOLEAN NOT NULL,
        disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_panel_semantic_audit_factors_v1(
        build_id VARCHAR NOT NULL,panel_id VARCHAR NOT NULL,factor_id VARCHAR NOT NULL,
        audited_rows BIGINT NOT NULL,warehouse_late_factor_rows BIGINT NOT NULL,
        lookahead_warning_rows BIGINT NOT NULL,carried_forward_rows BIGINT NOT NULL,
        measurable_event_factor_pairs BIGINT NOT NULL,
        research_classification VARCHAR NOT NULL,
        independently_certified_original_source_pit BOOLEAN NOT NULL,
        approved_institutional_event_factor_relation BOOLEAN NOT NULL)""")


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("Require pinned 40-character Git SHA and research-only scope")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        result=summarize(*load(con))
        total=result["totals"];pair=result["pairs"]
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_event_panel_semantic_audit_builds_v1
                VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,0,FALSE,
                'HISTORICAL_PANELS_EX_POST_AND_GRID_WAREHOUSE_ONLY_PIT_UNVERIFIED')""",
                [build,sha,digest,total["RETROSPECTIVE_V2"][0],
                 total["RETROSPECTIVE_V3"][0],total["WAREHOUSE_ASOF"][0],
                 total["RETROSPECTIVE_V2"][1],total["RETROSPECTIVE_V3"][1],
                 total["WAREHOUSE_ASOF"][1],pair[0],pair[1],pair[2],pair[4]])
            con.executemany(f"""INSERT INTO {P}lab_event_panel_semantic_audit_factors_v1
                VALUES ({','.join('?' for _ in range(11))})""",
                [(build,*row,False,False) for row in result["subjects"]])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} V2={total['RETROSPECTIVE_V2'][0]} V3={total['RETROSPECTIVE_V3'][0]} WAREHOUSE_ASOF={total['WAREHOUSE_ASOF'][0]}")
    print(f"V2_LATE={total['RETROSPECTIVE_V2'][1]} V3_LATE={total['RETROSPECTIVE_V3'][1]} GRID_FUTURE={total['WAREHOUSE_ASOF'][1]}")
    print(f"V2_V3_CARRY_MISMATCH={pair[1]} DATE_MISMATCH={pair[2]} CARRIED_DATE_RELABEL={pair[4]} VALUE_MISMATCH={pair[3]}")
    print("SOURCE_PUBLISHED_AT_CERTIFICATIONS=0 CAUSAL_RELATION_APPROVALS=0 INSTITUTIONAL_RELEASE=FALSE")


if __name__=="__main__":
    main()
