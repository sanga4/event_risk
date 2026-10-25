#!/usr/bin/env python3
"""Forward-only research v3.1 correction from independently joined lab source rows.

Preserves original v2 and v3. Reconstructs the actual factor_observed_date
using the exact factor-record hash+run ID, and the aligned daily change from
the v2 factor alignment. This is a source-consistency correction, NOT source
first-published-at PIT evidence, a causal event factor or a licensed beta.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib,os

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-v3.1-source-reconciled-v1.0.0"
EXPECTED_FACTORS=18


def review(metrics):
    """Reject any ambiguous record join, original source mismatch or leaked approval.

    Input: rows_v2,rows_v3,joined_rows,unique_joined_keys,source_factor_families,
    wrong_v2_source_dates,wrong_v2_source_carry,source_clock_mismatch,
    source_value_or_unit_mismatch,unmarked_lookahead_or_rights,corrected_dates,
    corrected_carried_labels,changed_material_factor_deltas,legacy_v3_builds.
    """
    if len(metrics)!=14:
        raise ValueError("Unexpected v3.1 source preflight metrics")
    (v2,v3,joined,unique,factors,wrong_v2date,wrong_v2carry,wrong_clocks,
     wrong_value,unauthorized,repaired_dates,repaired_carry,repaired_change,builds)=metrics
    if min(v2,v3,joined,unique)<1 or v2!=v3 or joined!=unique or v3!=joined:
        raise ValueError("Missing/duplicated v2/v3/factor source records")
    if factors!=EXPECTED_FACTORS or builds!=1:
        raise ValueError("Unrecognized source factor build or universe")
    if any(x!=0 for x in (wrong_v2date,wrong_v2carry,wrong_clocks,wrong_value,unauthorized)):
        raise ValueError("Source hashes, vintage fields or approvals failed independent reconciliation")
    if not (0<=repaired_dates<=joined and 0<=repaired_carry<=joined and
            0<=repaired_change<=joined):
        raise ValueError("Impossible correction count")
    # Repair counts need not always remain >0: on a fixed upstream builder
    # a rerun should have zero corrections, not refuse a correct source.
    return {"rows":int(joined),"factors":int(factors),
            "source_date_repaired":int(repaired_dates),
            "carry_flag_repaired":int(repaired_carry),
            "material_daily_change_repaired":int(repaired_change)}


def build_stage(con,build):
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE p1_v31_corrected AS
      SELECT v3.* REPLACE (
          f.observed_date AS factor_observed_date,
          v2.previous_aligned_factor_value AS previous_aligned_factor_value,
          v2.factor_daily_change AS factor_change_bps,
          (f.observed_date<v3.observed_date) AS factor_carried_forward,
          '{VERSION}'::VARCHAR AS pipeline_version,
          ?::VARCHAR AS build_id,
          current_timestamp AS built_at
      ),
      v3.build_id AS source_v3_build_id,
      v2.research_run_id AS source_v2_research_run_id,
      TRUE::BOOLEAN AS reconciled_to_existing_factor_hash_and_run,
      FALSE::BOOLEAN AS original_publication_pit_independently_certified,
      FALSE::BOOLEAN AS institutional_event_factor_approved
      FROM {P}lab_event_factor_panel_v3 v3
      JOIN {P}lab_event_factor_panel_v2 v2
        USING (proposition_id,factor_id,observed_date)
      JOIN {P}lab_factor_observations f
        ON f.factor_id=v3.factor_id
        AND f.record_sha256=v3.factor_source_sha256
        AND f.run_id=v3.factor_source_run
    """,[build])


def verify_sources(con):
    return con.execute(f"""
      WITH matched AS(
       SELECT v3.proposition_id,v3.factor_id,v3.observed_date,
         v3.build_id AS old_build,
         v3.factor_observed_date AS old_factor_day,
         v3.factor_carried_forward AS old_carried,
         v3.factor_change_bps AS old_factor_change,
         v3.factor_available_at AS old_available,
         v3.factor_ingested_at AS old_ingested,
         v3.factor_value AS old_value,
         v3.factor_unit AS old_unit,
         v3.event_probability AS old_probability,
         v3.event_delta_pp AS old_delta,
         v3.data_lookahead_warning AS old_lookahead,
         v3.data_use_class AS old_rights_class,
         v3.relation_status AS old_relation,
         v2.factor_observed_date AS v2_source_day,
         v2.factor_carried_forward AS v2_carried,
         v2.factor_daily_change AS v2_change,
         v2.factor_value AS v2_value,
         v2.probability AS v2_probability,
         v2.event_delta_pp AS v2_delta,
         f.observed_date AS source_day,f.value AS source_value,
         f.unit AS source_unit, f.availability_at AS source_available,
         f.ingested_at AS source_ingested
       FROM {P}lab_event_factor_panel_v3 v3
       JOIN {P}lab_event_factor_panel_v2 v2
         USING(proposition_id,factor_id,observed_date)
       JOIN {P}lab_factor_observations f
         ON f.factor_id=v3.factor_id
           AND f.record_sha256=v3.factor_source_sha256
           AND f.run_id=v3.factor_source_run
      )
      SELECT
       (SELECT count(*) FROM {P}lab_event_factor_panel_v2),
       (SELECT count(*) FROM {P}lab_event_factor_panel_v3),
       count(*),count(DISTINCT (proposition_id,factor_id,observed_date)),
       count(DISTINCT factor_id),
       count(*) FILTER(WHERE v2_source_day<>source_day),
       count(*) FILTER(WHERE v2_carried IS DISTINCT FROM
         (source_day<observed_date)),
       count(*) FILTER(WHERE old_available IS DISTINCT FROM source_available
         OR old_ingested IS DISTINCT FROM source_ingested),
       count(*) FILTER(WHERE old_value IS DISTINCT FROM source_value
         OR v2_value IS DISTINCT FROM source_value
         OR old_unit IS DISTINCT FROM source_unit
         OR abs(old_probability-v2_probability)>1e-9
         OR old_delta IS DISTINCT FROM v2_delta),
       count(*) FILTER(WHERE NOT old_lookahead
         OR old_rights_class<>'internal_research_only'
         OR old_relation<>'unreviewed_research_grid'
         OR source_available<=CAST(observed_date AS TIMESTAMPTZ)),
       count(*) FILTER(WHERE old_factor_day<>source_day),
       count(*) FILTER(WHERE old_carried IS DISTINCT FROM
         (source_day<observed_date)),
       count(*) FILTER(WHERE (old_factor_change IS NULL AND v2_change IS NOT NULL)
         OR (old_factor_change IS NOT NULL AND v2_change IS NULL)
         OR (old_factor_change IS NOT NULL AND v2_change IS NOT NULL
             AND abs(old_factor_change-v2_change)>1e-6)),
       count(DISTINCT old_build)
      FROM matched
    """).fetchone()


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_factor_panel_v3_1
       AS SELECT * FROM p1_v31_corrected WHERE FALSE""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_factor_v31_repairs_v1(
      build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
      script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      original_v3_build_id VARCHAR NOT NULL, source_v2_research_run_id VARCHAR NOT NULL,
      original_v3_rows BIGINT NOT NULL,source_factor_families BIGINT NOT NULL,
      corrected_factor_observed_dates BIGINT NOT NULL,
      corrected_carried_labels BIGINT NOT NULL,
      corrected_material_factor_deltas BIGINT NOT NULL,
      verified_join_rows BIGINT NOT NULL,
      original_source_pit_verified BOOLEAN NOT NULL,
      independently_approved_event_factor_model BOOLEAN NOT NULL,
      institutional_release_approved BOOLEAN NOT NULL,
      disposition VARCHAR NOT NULL)""")


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or
        any(ch not in "0123456789abcdef" for ch in sha)):
        raise RuntimeError("Require pinned Git commit and internal-only scope")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        metrics=review(verify_sources(con))
        old=con.execute(f"SELECT DISTINCT build_id FROM {P}lab_event_factor_panel_v3").fetchone()[0]
        v2run=con.execute(f"SELECT DISTINCT research_run_id FROM {P}lab_event_factor_panel_v2").fetchall()
        if len(v2run)!=1:
            raise RuntimeError("Multiple legacy v2 source builds")
        build_stage(con,build)
        rows=con.execute("SELECT count(*) FROM p1_v31_corrected").fetchone()[0]
        mismatch=con.execute("""SELECT count(*) FROM p1_v31_corrected
          WHERE factor_observed_date>observed_date
            OR factor_carried_forward IS DISTINCT FROM
             (factor_observed_date<observed_date)
            OR NOT data_lookahead_warning
            OR original_publication_pit_independently_certified
            OR institutional_event_factor_approved
            OR data_use_class<>'internal_research_only'""").fetchone()[0]
        if rows!=metrics["rows"] or mismatch:
            raise RuntimeError("Staged corrected panel violates semantic contract")
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_event_factor_panel_v3_1
              SELECT * FROM p1_v31_corrected""")
            con.execute(f"""INSERT INTO {P}lab_event_factor_v31_repairs_v1 VALUES
              (?,?,?,current_timestamp,?,?,?,?,?,?,?, ?,FALSE,FALSE,FALSE,
                 'SOURCE_RECONCILED_RETROSPECTIVE_ONLY_PIT_UNVERIFIED')""",
              [build,sha,digest,old,v2run[0][0],metrics["rows"],metrics["factors"],
               metrics["source_date_repaired"],metrics["carry_flag_repaired"],
               metrics["material_daily_change_repaired"],rows])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} SOURCE_V3={old} V2_SOURCE={v2run[0][0]} ROWS={rows}")
    print(f"DATE_CORRECTIONS={metrics['source_date_repaired']} CARRY_CORRECTIONS={metrics['carry_flag_repaired']} MATERIAL_CHANGE_CORRECTIONS={metrics['material_daily_change_repaired']}")
    print("ORIGINAL_PIT_VERIFIED=FALSE LICENSED_EVENT_EFFECTS=FALSE INSTITUTIONAL_RELEASE=FALSE")


if __name__=="__main__":
    main()
