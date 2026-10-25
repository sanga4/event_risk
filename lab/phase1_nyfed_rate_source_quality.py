#!/usr/bin/env python3
"""Research-only NY Fed full-history rate-level quality and vintage audit.

Official effective-date rates are not rate-release surprises, independently
first-published-at historical vintages, risk-factor betas, or licensed feeds.
"""
from __future__ import annotations
from datetime import datetime, timezone, date
from pathlib import Path
import hashlib
import os

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-nyfed-source-quality-v1.0.0"
SERIES=frozenset(("SOFR","EFFR"))
MIN_RESEARCH_DAYS=1500
RESEARCH_START_LIMIT=date(2018,12,31)
STRESS_JUMP_BPS=50.0

def validate(summaries, totals):
    """Validate independent source history and mark funding jumps as diagnostics.

    per series: sid,days,first,last,payloads,overlap_days,revision_days,
    extreme_daily_changes,max_abs_daily_change,approval_problems
    totals: source_rows,unique_series_day_rows,duplicate_exact_source_keys,
    unmatched_last_build_source_rows,incorrect_source_rights_or_pit_flags.
    """
    if len(summaries)!=2 or {r[0] for r in summaries}!=SERIES:
        raise ValueError("Missing or duplicate reference rate series")
    if len(totals)!=5:
        raise ValueError("Wrong original-source QA count contract")
    rows,distinct,duplicates,missing_latest,invalid=totals
    if rows<distinct or distinct<2*MIN_RESEARCH_DAYS or duplicates or missing_latest or invalid:
        raise ValueError("Unreconciled rate source identity, revision, or approval")
    out=[]
    for row in summaries:
        if len(row)!=10:
            raise ValueError("Wrong per-rate source contract")
        sid,n,first,last,versions,overlap,revisions,jumps,max_jump,false_claims=row
        if (n<MIN_RESEARCH_DAYS or first is None or last is None
           or first>RESEARCH_START_LIMIT or last<date(2024,1,1)
           or versions<1 or overlap<0 or overlap>n or revisions<0 or revisions>overlap
           or jumps<0 or jumps>n or max_jump is None or max_jump<0 or false_claims):
            raise ValueError("Incomplete, altered, unapproved or impossible rate coverage")
        out.append((sid,int(n),first,last,int(versions),int(overlap),
                    int(revisions),int(jumps),float(max_jump),
                    "ORIGINAL_PROVIDER_PUBLICATION_AND_RIGHTS_UNVERIFIED"
                    if revisions==0 else
                    "OBSERVED_CROSS_RETRIEVAL_REVISION_REQUIRES_SOURCE_REVIEW"))
    if sum(x[1] for x in out)!=distinct:
        raise ValueError("Distinct rate key counts drift from source")
    return out

def compute(con):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE p1_nyfed_latest AS
      WITH ranked AS (
        SELECT *,row_number() OVER(
          PARTITION BY series_id,effective_date
          ORDER BY source_response_received_at DESC,
                   source_json_sha256 DESC,first_build_id DESC) AS rn
        FROM {P}lab_nyfed_rate_observations_retro_v1
      ) SELECT * EXCLUDE(rn) FROM ranked WHERE rn=1""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE p1_nyfed_change_diag AS
      WITH s AS (
        SELECT series_id,effective_date,annual_rate_percent,
          lag(effective_date) OVER(PARTITION BY series_id ORDER BY effective_date) AS prior_date,
          lag(annual_rate_percent) OVER(PARTITION BY series_id ORDER BY effective_date) AS prior_level
        FROM p1_nyfed_latest
      )
      SELECT series_id,effective_date,
        100.0*(annual_rate_percent-prior_level) AS delta_bps
      FROM s
      WHERE prior_date IS NOT NULL
        AND date_diff('day',prior_date,effective_date) BETWEEN 1 AND 7""")
    summaries=con.execute(f"""WITH versioned AS (
         SELECT series_id,effective_date,count(*) as archives,
           count(DISTINCT annual_rate_percent) distinct_values
         FROM {P}lab_nyfed_rate_observations_retro_v1
         GROUP BY series_id,effective_date),
       rev AS (
         SELECT series_id,
           count(*) FILTER(WHERE archives>1) overlap,
           count(*) FILTER(WHERE distinct_values>1) revisions
         FROM versioned GROUP BY series_id),
       source AS (
         SELECT series_id,count(DISTINCT source_json_sha256) payloads,
           count(*) FILTER(WHERE first_published_timestamp_verified
             OR provider_historical_revision_asof_verified
             OR downstream_license_approved OR production_risk_input_approved
             OR original_provider_published_at IS NOT NULL
             OR NOT research_only
             OR length(source_json_sha256)<>64) flagged
         FROM {P}lab_nyfed_rate_observations_retro_v1
         GROUP BY series_id),
       jumps AS (
         SELECT series_id,
            count(*) FILTER(WHERE ABS(delta_bps)>={STRESS_JUMP_BPS}) extreme,
            max(ABS(delta_bps)) maximum
         FROM p1_nyfed_change_diag GROUP BY series_id
       )
       SELECT l.series_id,count(*) distinct_dates,
          min(l.effective_date) first_date,max(l.effective_date) last_date,
          max(s.payloads),max(r.overlap),max(r.revisions),
          max(j.extreme),max(j.maximum),max(s.flagged)
       FROM p1_nyfed_latest l JOIN source s USING(series_id)
       JOIN rev r USING(series_id) JOIN jumps j USING(series_id)
       GROUP BY l.series_id ORDER BY l.series_id""").fetchall()
    totals=con.execute(f"""SELECT
       (SELECT count(*) FROM {P}lab_nyfed_rate_observations_retro_v1),
       (SELECT count(*) FROM p1_nyfed_latest),
       (SELECT count(*) FROM (
          SELECT series_id,effective_date,source_json_sha256,count(*) n
          FROM {P}lab_nyfed_rate_observations_retro_v1
          GROUP BY 1,2,3 HAVING count(*)>1)),
       (SELECT count(*) FROM p1_nyfed_latest
          WHERE source_json_sha256 IS NULL
            OR length(source_json_sha256)<>64),
       (SELECT count(*) FROM p1_nyfed_latest
          WHERE annual_rate_percent IS NULL
            OR NOT isfinite(annual_rate_percent)
            OR annual_rate_percent<-5 OR annual_rate_percent>=100
            OR effective_date>CAST(current_timestamp AS DATE)
            OR original_provider_published_at IS NOT NULL
            OR first_published_timestamp_verified
            OR provider_historical_revision_asof_verified
            OR downstream_license_approved OR production_risk_input_approved
            OR NOT research_only)""").fetchone()
    return summaries,totals

def schema(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_nyfed_rate_source_quality_builds_v1(
       build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
       source_code_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
       recorded_source_rows BIGINT NOT NULL,distinct_effective_date_records BIGINT NOT NULL,
       official_rate_series BIGINT NOT NULL,overlapping_retrieval_days BIGINT NOT NULL,
       materially_revised_rate_days BIGINT NOT NULL,
       stress_move_rows_ge_50bps BIGINT NOT NULL,
       original_release_vintages_approved BOOLEAN NOT NULL,
       institutional_funding_shocks_approved BOOLEAN NOT NULL,
       disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_nyfed_rate_source_quality_series_v1(
       build_id VARCHAR NOT NULL,series_id VARCHAR NOT NULL,
       distinct_effective_dates BIGINT NOT NULL,
       first_effective_date DATE NOT NULL,last_effective_date DATE NOT NULL,
       retained_raw_payload_versions BIGINT NOT NULL,
       overlapping_retrieval_days BIGINT NOT NULL,
       materially_revised_rate_days BIGINT NOT NULL,
       absolute_rate_changes_ge_50bps BIGINT NOT NULL,
       maximum_absolute_rate_change_bps DOUBLE NOT NULL,
       original_publisher_release_and_licensing_status VARCHAR NOT NULL,
       policy_surprise_beta_approved BOOLEAN NOT NULL)""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or
        any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Require pinned Git commit and internal-only rate QA")
    import duckdb
    built=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        per_series,totals=compute(con)
        results=validate(per_series,totals)
        schema(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_nyfed_rate_source_quality_builds_v1
               VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,FALSE,FALSE,
                 'HISTORICAL_RESEARCH_RATE_LEVELS_NO_SOURCE_FIRST_PUBLICATION_OR_POLICY_SURPRISE')""",
               [built,sha,checksum,totals[0],totals[1],len(results),
                sum(x[5] for x in results),sum(x[6] for x in results),
                sum(x[7] for x in results)])
            con.executemany(f"""INSERT INTO {P}lab_nyfed_rate_source_quality_series_v1
               VALUES ({','.join('?' for _ in range(12))})""",
               [(built,*x,False) for x in results])
            con.execute(f"""CREATE OR REPLACE VIEW
                {P}lab_nyfed_rate_levels_latest_retro_v1 AS
               WITH ranked AS (
                 SELECT *,ROW_NUMBER() OVER(
                    PARTITION BY series_id,effective_date
                    ORDER BY source_response_received_at DESC,
                         source_json_sha256 DESC,first_build_id DESC) rn
                 FROM {P}lab_nyfed_rate_observations_retro_v1
               ) SELECT * EXCLUDE(rn) FROM ranked WHERE rn=1""")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD={built} RAW_SOURCE_ROWS={totals[0]} UNIQUE_SERIES_EFFECTIVE_DATES={totals[1]}")
    for x in results:
        print(f"SERIES={x[0]} DAYS={x[1]} FIRST={x[2]} LAST={x[3]} OVERLAP={x[5]} REVISIONS={x[6]} STRESS_MOVES={x[7]} MAX_ABS_BPS={x[8]}")
    print("RESEARCH_LEVEL_VIEW_ONLY=TRUE ORIGINAL_PUBLISHED_AT=UNVERIFIED CAUSAL_BETA_RELEASE=FALSE")

if __name__=="__main__":
    main()
