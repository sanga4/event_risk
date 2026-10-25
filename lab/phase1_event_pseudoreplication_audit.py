#!/usr/bin/env python3
"""Fail-closed event-factor pseudo-replication and model-identification audit.

Multiple event propositions observed on one market date do not create new
independent Treasury factor return outcomes. No covariance beta, causal
attribution, risk model, historical PIT or licensing approval is inferred.
"""
from __future__ import annotations
import hashlib
import os
from datetime import datetime,timezone
from pathlib import Path

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-event-pseudoreplication-v1.0.0"
EXPECTED_FACTORS=18
MIN_EXPLORATORY_DISTINCT_PAIRED_DATES=60


def evaluate(factors,source):
    """Check aggregate chronology and descriptive clustered-sampling gaps.

    factor row = factor_id, rows, paired_rows, distinct_event_days,
      distinct_paired_days, factor_level_day_groups, propositions,
      late_source_rows, unauthorized_rows,invalid_source_rows.
    """
    if (len(factors)!=EXPECTED_FACTORS or
        len({f[0] for f in factors})!=EXPECTED_FACTORS):
        raise ValueError("Missing or duplicate source factor family")
    if len(source)!=4:
        raise ValueError("Unexpected source build manifest")
    source_id,source_rows,source_factors,source_released=source
    if not source_id or source_factors!=EXPECTED_FACTORS or source_released:
        raise ValueError("Source v4 absent or falsely released")
    results=[]
    for row in factors:
        if len(row)!=10:
            raise ValueError("Factor sampling contract changed")
        name,n,paired,days,paired_days,level_day,events,late,unauthorized,invalid=row
        if (not name or n<=0 or paired<0 or paired>n or days<=0
            or paired_days<0 or paired_days>days or level_day!=days
            or events<=0 or events>n or late<0 or late>n
            or unauthorized!=0 or invalid!=0):
            raise ValueError("Invalid factor chronology, legal or model release state")
        max_directly_observed_outcome_days=int(paired_days)
        results.append((name,int(n),int(paired),int(days),
                        max_directly_observed_outcome_days,int(events),
                        float(paired / max(paired_days,1)),
                        max_directly_observed_outcome_days>=MIN_EXPLORATORY_DISTINCT_PAIRED_DATES,
                        "INSUFFICIENT_DISTINCT_PAIRED_DATES_FOR_EXPLORATORY_EVENT_FACTOR_FIT"
                        if paired_days<MIN_EXPLORATORY_DISTINCT_PAIRED_DATES else
                        "HISTORY_COUNT_ONLY_SOURCE_PIT_AND_CAUSAL_IDENTIFICATION_UNVERIFIED"))
    if sum(x[1] for x in results)!=source_rows:
        raise ValueError("Source manifest observation count drift")
    # Distinct outcome *days* are not iid effective sample sizes.
    return results


def gather(con):
    source=con.execute(f"""SELECT build_id,panel_rows,factor_count,
      institutional_risk_release
      FROM {P}lab_event_factor_v4_builds_v1
      ORDER BY built_at DESC LIMIT 1""").fetchone()
    if source is None:
        raise RuntimeError("Missing source-native v4 research build")
    factors=con.execute(f"""SELECT factor_id,count(*) AS panel_rows,
      count(*) FILTER(WHERE event_delta_pp IS NOT NULL
          AND factor_change_bps IS NOT NULL) AS paired_rows,
      count(DISTINCT observed_date) AS event_days,
      count(DISTINCT observed_date) FILTER(WHERE
          event_delta_pp IS NOT NULL AND factor_change_bps IS NOT NULL)
          AS event_days_with_paired_factor_change,
      count(DISTINCT (observed_date,factor_value)) AS
          unique_factor_level_day_groups,
      count(DISTINCT proposition_id) AS propositions,
      count(*) FILTER(WHERE data_lookahead_warning) AS lookahead_warning,
      count(*) FILTER(WHERE original_source_pit_verified
         OR independently_approved_causal_mapping OR institutional_risk_release)
         AS false_release,
      count(*) FILTER(WHERE factor_observed_date>observed_date
         OR factor_unit<>'percent'
         OR factor_carried_forward IS DISTINCT FROM
            (factor_observed_date<observed_date)
         OR NOT isfinite(factor_value)
         OR event_probability<0 OR event_probability>1 OR NOT isfinite(event_probability)
         OR length(factor_source_sha256)<>64
         OR data_use_class<>'internal_research_only')
         AS invalid
      FROM {P}lab_event_factor_panel_v4_latest
      GROUP BY factor_id ORDER BY factor_id""").fetchall()
    return source,factors


def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_pseudoreplication_builds_v1(
        build_id VARCHAR NOT NULL,source_v4_build VARCHAR NOT NULL,
        source_git_sha VARCHAR NOT NULL,script_sha256 VARCHAR NOT NULL,
        built_at TIMESTAMPTZ NOT NULL,source_rows BIGINT NOT NULL,
        paired_event_factor_rows BIGINT NOT NULL,
        distinct_factors BIGINT NOT NULL,
        minimum_required_exploratory_paired_event_dates INTEGER NOT NULL,
        factor_families_below_minimum BIGINT NOT NULL,
        original_source_pit_approved BOOLEAN NOT NULL,
        institutional_event_attribution_approved BOOLEAN NOT NULL,
        release_state VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_event_pseudoreplication_factors_v1(
        build_id VARCHAR NOT NULL,factor_id VARCHAR NOT NULL,
        proposition_factor_rows BIGINT NOT NULL,
        paired_proposition_factor_rows BIGINT NOT NULL,
        observed_event_calendar_days BIGINT NOT NULL,
        observed_paired_factor_event_days BIGINT NOT NULL,
        distinct_propositions BIGINT NOT NULL,
        apparent_paired_rows_per_observed_paired_day DOUBLE NOT NULL,
        at_least_60_paired_dates BOOLEAN NOT NULL,
        methodological_review_state VARCHAR NOT NULL,
        approved_causal_event_factor_beta BOOLEAN NOT NULL)""")


def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40
        or any(k not in "0123456789abcdef" for k in sha)):
        raise RuntimeError("Pinned SHA and research-only scope required")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        source,factors=gather(con)
        assessed=evaluate(factors,source)
        rows=sum(f[1] for f in assessed)
        paired=sum(f[2] for f in assessed)
        blocked=sum(not f[7] for f in assessed)
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_event_pseudoreplication_builds_v1
                VALUES (?,?,?,?,current_timestamp,?,?,?,?,?,FALSE,FALSE,
                'RETROSPECTIVE_DUPLICATED_OUTCOME_DAYS_NO_INDEPENDENT_EVENT_EFFECTS')""",
                [build,source[0],sha,digest,rows,paired,len(assessed),
                 MIN_EXPLORATORY_DISTINCT_PAIRED_DATES,blocked])
            con.executemany(f"""INSERT INTO {P}lab_event_pseudoreplication_factors_v1
                VALUES ({','.join('?' for _ in range(11))})""",
                [(build,*f,False) for f in assessed])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} SOURCE_V4_BUILD={source[0]}")
    print(f"PAIRED_ROWS={paired} DISTINCT_FACTOR_FAMILIES={len(assessed)}")
    print(f"MIN_OBSERVED_PAIRED_DAYS={min(f[4] for f in assessed)} MAX_OBSERVED_PAIRED_DAYS={max(f[4] for f in assessed)} BELOW_60_DAYS={blocked}")
    print("CLAIMED_IID_OBSERVATIONS=NONE SOURCE_PIT=FALSE EVENT_CAUSAL_BETA=FALSE")


if __name__=="__main__":
    main()
