#!/usr/bin/env python3
"""Independently reconstruct event-aligned Treasury factors from source rows.

No dependence on v2/v3 in production transformation. The existing corrected
v3.1 panel is a separate, bounded acceptance oracle for overlapping keys.
Retrospective research only; no original provider first-published-at proof.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os

DB = "eventrisk_factor_lab"
P = DB + ".main."
VERSION = "phase1-v4-native-event-factor-v1.0.0"
EXPECTED_FACTORS = 18


def construct(con):
    """Explicitly separate event day and *source factor* observed day."""
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE v4_dates AS
        SELECT DISTINCT observed_date AS event_day, cutoff_at AS event_cutoff
        FROM {P}lab_event_features
        WHERE known_at <= cutoff_at AND last_quote_at <= cutoff_at
          AND isfinite(probability) AND probability BETWEEN 0 AND 1
    """)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE v4_source AS
        SELECT f.factor_id,
          f.observed_date AS source_factor_day,
          f.value AS source_factor_value,
          f.unit AS source_factor_unit,
          f.availability_at AS provider_record_available_at,
          f.ingested_at AS warehouse_ingested_at,
          f.provider AS source_provider,
          f.record_sha256 AS source_record_sha,
          f.run_id AS source_run_id
        FROM {P}lab_factor_observations f
        JOIN {P}lab_factor_catalog c ON f.factor_id=c.factor_id
        WHERE c.active=TRUE AND c.license_class NOT LIKE 'restricted%'
          AND f.unit=c.unit AND f.unit='percent'
          AND isfinite(f.value)
          AND length(f.record_sha256)=64
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE v4_selected AS
        WITH ranked AS (
          SELECT d.event_day,d.event_cutoff,s.*,
            row_number() OVER(
              PARTITION BY d.event_day,d.event_cutoff,s.factor_id
              ORDER BY s.source_factor_day DESC,
                s.warehouse_ingested_at DESC,s.source_record_sha DESC,
                s.source_run_id DESC
            ) AS selection_rank
          FROM v4_dates d
          JOIN v4_source s ON s.source_factor_day<=d.event_day
        )
        SELECT * EXCLUDE(selection_rank)
        FROM ranked WHERE selection_rank=1
    """)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE v4_aligned AS
        SELECT e.proposition_id,e.observed_date AS event_day,
          e.cutoff_at AS event_cutoff_at,e.known_at AS event_known_at,
          e.last_quote_at AS event_last_quote_at,e.probability AS event_probability,
          e.delta_pp AS event_delta_pp,e.source_run AS event_source_run,
          f.factor_id,f.source_factor_day,f.source_factor_value,
          f.source_factor_unit,f.provider_record_available_at,
          f.warehouse_ingested_at,f.source_provider,f.source_record_sha,
          f.source_run_id,
          lag(f.source_factor_value) OVER (
            PARTITION BY e.proposition_id,f.factor_id
            ORDER BY e.observed_date,e.cutoff_at
          ) AS previous_proposition_aligned_value
        FROM {P}lab_event_features e
        JOIN v4_selected f ON e.observed_date=f.event_day
          AND e.cutoff_at=f.event_cutoff
        WHERE e.known_at<=e.cutoff_at AND e.last_quote_at<=e.cutoff_at
          AND isfinite(e.probability) AND e.probability BETWEEN 0 AND 1
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE v4_candidate AS
        SELECT proposition_id,factor_id,event_day AS observed_date,
          event_cutoff_at,event_known_at,event_last_quote_at,
          event_probability,event_delta_pp,
          source_factor_day AS factor_observed_date,
          source_factor_value AS factor_value,
          source_factor_unit AS factor_unit,
          previous_proposition_aligned_value AS previous_aligned_factor_value,
          CASE WHEN previous_proposition_aligned_value IS NULL THEN NULL
               ELSE round(100.0*(source_factor_value-
                 previous_proposition_aligned_value),8) END AS factor_change_bps,
          (source_factor_day<event_day) AS factor_carried_forward,
          provider_record_available_at AS factor_available_at,
          warehouse_ingested_at AS factor_ingested_at,
          source_provider AS factor_provider,
          source_record_sha AS factor_source_sha256,
          event_source_run,
          source_run_id AS factor_source_run,
          'retrospective'::VARCHAR AS observed_mode,
          (provider_record_available_at>event_cutoff_at
            OR warehouse_ingested_at>event_cutoff_at
            OR event_known_at>event_cutoff_at
            OR event_last_quote_at>event_cutoff_at) AS data_lookahead_warning,
          'unreviewed_research_grid'::VARCHAR AS relation_status,
          'internal_research_only'::VARCHAR AS data_use_class,
          FALSE::BOOLEAN AS original_source_pit_verified,
          FALSE::BOOLEAN AS independently_approved_causal_mapping,
          FALSE::BOOLEAN AS institutional_risk_release
        FROM v4_aligned
    """)


def accept(coverage, source_check):
    """Validate local history and mandatory independent v3.1 overlap parity.

    coverage: (n,factors,duplicates,bad_values,bad_clock_flags,
               invalid_source_date,unflagged_expost,carried,paired,late)
    source_check: (oracle_n,matched,unmatched,semantic_errors).
    """
    if len(coverage)!=10 or len(source_check)!=4:
        raise ValueError("Unexpected v4 acceptance contract")
    (n,factors,dups,bad_values,wrong_guards,future_source,unflagged,
     carried,paired,late)=coverage
    oracle_n,matched,unmatched,disagreements=source_check
    if n<=0 or factors!=EXPECTED_FACTORS or any(v!=0 for v in
            (dups,bad_values,wrong_guards,future_source,unflagged)):
        raise ValueError("Source-native v4 factor integrity or research-only guard failure")
    if any(x<0 or x>n for x in (carried,paired,late)):
        raise ValueError("Invalid factor counts")
    if (oracle_n<=0 or matched!=oracle_n or unmatched!=0 or
        disagreements!=0 or n<oracle_n):
        raise ValueError("Source-native v4 failed corrected v3.1 overlap reconciliation")
    return dict(rows=n,factors=factors,carried=carried,paired=paired,
                retrospective_late=late,matched_oracle=matched)


def validate(con):
    coverage=con.execute("""
       SELECT count(*),count(DISTINCT factor_id),
         (SELECT count(*) FROM(
            SELECT proposition_id,factor_id,observed_date,count(*) n
            FROM v4_candidate GROUP BY 1,2,3 HAVING count(*)>1)),
         count(*) FILTER(WHERE factor_value IS NULL OR NOT isfinite(factor_value)
           OR factor_unit<>'percent'
           OR NOT isfinite(event_probability)
           OR NOT event_probability BETWEEN 0 AND 1
           OR factor_source_sha256 IS NULL OR length(factor_source_sha256)<>64
           OR factor_change_bps IS NOT NULL AND
               (previous_aligned_factor_value IS NULL
                OR abs(factor_change_bps-
                100*(factor_value-previous_aligned_factor_value))>1e-6)),
         count(*) FILTER(WHERE institutional_risk_release
            OR independently_approved_causal_mapping OR original_source_pit_verified
            OR data_use_class<>'internal_research_only'
            OR observed_mode<>'retrospective' OR relation_status<>'unreviewed_research_grid'),
         count(*) FILTER(WHERE factor_observed_date>observed_date),
         count(*) FILTER(WHERE
           (factor_available_at>event_cutoff_at OR
            factor_ingested_at>event_cutoff_at) AND NOT data_lookahead_warning),
         count(*) FILTER(WHERE factor_carried_forward),
         count(*) FILTER(WHERE event_delta_pp IS NOT NULL
            AND factor_change_bps IS NOT NULL),
         count(*) FILTER(WHERE factor_available_at>event_cutoff_at
            OR factor_ingested_at>event_cutoff_at)
       FROM v4_candidate
    """).fetchone()
    oracle=con.execute(f"""
       WITH joined AS(
         SELECT o.proposition_id,o.factor_id,o.observed_date,
           c.proposition_id IS NOT NULL AS has_new,
           (c.factor_observed_date IS DISTINCT FROM o.factor_observed_date
             OR c.factor_carried_forward IS DISTINCT FROM o.factor_carried_forward
             OR c.factor_value IS DISTINCT FROM o.factor_value
             OR c.factor_unit IS DISTINCT FROM o.factor_unit
             OR c.factor_available_at IS DISTINCT FROM o.factor_available_at
             OR c.factor_source_sha256 IS DISTINCT FROM o.factor_source_sha256
             OR c.factor_source_run IS DISTINCT FROM o.factor_source_run
             OR c.event_probability IS DISTINCT FROM o.event_probability
             OR c.event_delta_pp IS DISTINCT FROM o.event_delta_pp
             OR c.previous_aligned_factor_value IS DISTINCT FROM
                o.previous_aligned_factor_value
             OR (c.factor_change_bps IS NULL) IS DISTINCT FROM
                (o.factor_change_bps IS NULL)
             OR (c.factor_change_bps IS NOT NULL
                AND o.factor_change_bps IS NOT NULL
                AND abs(c.factor_change_bps-o.factor_change_bps)>1e-6)
           ) AS differs
         FROM {P}lab_event_factor_panel_v3_1_latest o
         LEFT JOIN v4_candidate c USING(proposition_id,factor_id,observed_date)
       )
       SELECT count(*),count(*) FILTER(WHERE has_new),
         count(*) FILTER(WHERE NOT has_new),
         count(*) FILTER(WHERE differs)
       FROM joined
    """).fetchone()
    return accept(coverage,oracle)


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_factor_panel_v4
       AS SELECT *,''::VARCHAR AS build_id,
       current_timestamp AS built_at FROM v4_candidate WHERE FALSE""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_factor_v4_builds_v1(
       build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
       source_script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
       panel_rows BIGINT NOT NULL,factor_count BIGINT NOT NULL,
       proposition_carried_forward_rows BIGINT NOT NULL,
       paired_event_factor_changes BIGINT NOT NULL,
       historically_later_ingested_rows BIGINT NOT NULL,
       matched_corrected_v31_oracle_rows BIGINT NOT NULL,
       independent_source_pit_approved BOOLEAN NOT NULL,
       institutional_risk_release BOOLEAN NOT NULL,
       model_disposition VARCHAR NOT NULL)""")


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40
        or any(ch not in "0123456789abcdef" for ch in sha)):
        raise RuntimeError("Pinned commit and internal research scope required")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        construct(con)
        result=validate(con)
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_event_factor_panel_v4
                SELECT *,?::VARCHAR AS build_id,current_timestamp AS built_at
                FROM v4_candidate""",[build])
            con.execute(f"""INSERT INTO {P}lab_event_factor_v4_builds_v1 VALUES
                (?,?,?,current_timestamp,?,?,?,?,?,?,FALSE,FALSE,
                'RESEARCH_ALIGNED_ONLY_NOT_PIT_OR_CAUSAL_APPROVED')""",
                [build,sha,digest,result["rows"],result["factors"],
                 result["carried"],result["paired"],
                 result["retrospective_late"],result["matched_oracle"]])
            con.execute(f"""CREATE OR REPLACE VIEW {P}lab_event_factor_panel_v4_latest AS
                SELECT * FROM {P}lab_event_factor_panel_v4
                WHERE build_id=(SELECT build_id FROM
                 {P}lab_event_factor_v4_builds_v1
                 ORDER BY built_at DESC LIMIT 1)""")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} ROWS={result['rows']} FACTORS={result['factors']}")
    print(f"CORRECTED_V31_INDEPENDENT_ORACLE_MATCH={result['matched_oracle']}")
    print(f"CARRIED={result['carried']} PAIRED={result['paired']} LATE={result['retrospective_late']}")
    print("SOURCE_FIRST_PUBLISHED_CLOCK_VERIFIED=FALSE MODEL_APPROVED=FALSE")


if __name__=="__main__":
    main()
