#!/usr/bin/env python3
"""Institutional source-family temporal-depth diagnostic; never grant PIT rights.

Compare one frozen source-family manifest to independent warehouse counts.
Separate (a) retrieved record volume, (b) distinct historical dates, and
(c) independently licensed original publication-time evidence.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-source-temporal-adequacy-v1.0.0"
EXPECTED_FAMILIES=16
MIN_NYFED_RATE_DAYS_RESEARCH=1500
MIN_PROSPECTIVE_CAPTURE_DATES_RESEARCH=60
MIN_EVENT_FACTOR_PAIRED_DATES_RESEARCH=60
RATE_IDS=frozenset(("SOFR","EFFR"))

def assess(family_build, families, venue, nyfed, grid, panel):
    """Validate source coverage and derive *research-only* unblock priorities.

    family rows: domain,source_table_exists,source_row_count,
     first_observed_date,latest_observed_date,last_local_retrieved_at,
     provider_original_publication_verified,commercial_reuse_approved,
     institutional_factor_model_approved,expected_frequency,next_required_evidence
    venue: number of rows, distinct runs, distinct capture dates, false approval
    nyfed: rate_id, native rows, distinct days, oldest, newest, false approvals
    grid: rows, distinct event capture days, future join rows, false approvals
    panel: factor rows, distinct paired event days, false approvals
    """
    if not family_build or len(families)!=EXPECTED_FAMILIES:
        raise ValueError("Missing institutional source family inventory")
    names=[f[0] for f in families]
    if len(set(names))!=EXPECTED_FAMILIES:
        raise ValueError("Duplicate source family")
    if len(venue)!=4 or len(grid)!=4 or len(panel)!=3:
        raise ValueError("Wrong independent data depth contract")
    venue_rows,venue_runs,venue_days,venue_false=venue
    grid_rows,grid_days,grid_future,grid_false=grid
    panel_rows,panel_paired_dates,panel_false=panel
    if (min(venue_rows,venue_runs,venue_days,grid_rows,grid_days,
            panel_rows,panel_paired_dates)<1
        or venue_false or grid_future or grid_false or panel_false
        or venue_days>venue_runs or grid_days>venue_days
        or panel_paired_dates>MIN_EVENT_FACTOR_PAIRED_DATES_RESEARCH*1000):
        raise ValueError("Invalid warehouse temporal or approval evidence")
    rates={row[0]:row for row in nyfed}
    if set(rates)!=RATE_IDS or len(nyfed)!=2:
        raise ValueError("Missing or duplicated official NYFed rate series")
    for sid,n,dates,first,last,false in nyfed:
        if n<1 or dates<1 or dates>n or first is None or last is None or first>last or false:
            raise ValueError("Invalid official rate source coverage or false release")
    counts={f[0]:int(f[2]) for f in families}
    if counts.get("venue_prospective_receipts")!=venue_rows:
        raise ValueError("Venue source-family count disagrees with native receipts")
    if counts.get("nyfed_sofr_effr_reference")!=sum(r[1] for r in nyfed):
        raise ValueError("NYFed source-family count disagrees with original reference rows")
    if "fred_macro_economic" not in counts or counts["fred_macro_economic"]<0:
        raise ValueError("Missing FRED research family contract")

    details=[]
    for f in families:
        (domain,exists,n,first,last,retrieved,pit,rights,approved,freq,evidence)=f
        if not domain or not freq or not evidence or n<0 or (n>0 and not exists):
            raise ValueError("Malformed source family domain or record count")
        if n and (first is None or last is None or first>last):
            raise ValueError("Malformed family first/last observation dates")
        if (pit or rights or approved):
            # An asserted TRUE flag requires a wholly different independent
            # document review: this diagnostic never converts it to approval.
            state="UPSTREAM_RIGHTS_OR_PIT_ASSERTION_NEEDS_HUMAN_EVIDENCE_REVIEW"
        elif n==0:
            state="MISSING_SOURCE_OR_CREDENTIAL_OR_ORIGINAL_EVIDENCE"
        elif domain=="nyfed_sofr_effr_reference" and any(
            r[2]<MIN_NYFED_RATE_DAYS_RESEARCH or r[3].isoformat()>"2018-12-31"
            for r in nyfed
        ):
            state="NYFED_REFERENCE_HISTORY_INCOMPLETE_RESEARCH_ONLY"
        elif domain=="venue_prospective_receipts" and venue_days<MIN_PROSPECTIVE_CAPTURE_DATES_RESEARCH:
            state="PROSPECTIVE_INDEPENDENT_CAPTURE_DAYS_BELOW_RESEARCH_SCREEN"
        else:
            state="POPULATED_BUT_ORIGINAL_PUBLICATION_PIT_AND_RIGHTS_UNVERIFIED"
        details.append((domain,int(n),first,last,retrieved,str(freq),state,str(evidence),
                        False,False,False))
    return {"families":len(details),"loaded":sum(x[1]>0 for x in details),
            "missing":sum(x[1]==0 for x in details),"venue_rows":int(venue_rows),
            "capture_days":int(venue_days),"rate_rows":sum(int(x[1]) for x in nyfed),
            "minimum_nyfed_days":min(int(x[2]) for x in nyfed),
            "nyfed_history_sufficient":all(
                x[2]>=MIN_NYFED_RATE_DAYS_RESEARCH and
                x[3].isoformat()<="2018-12-31" for x in nyfed),
            "grid_rows":int(grid_rows),"grid_capture_days":int(grid_days),
            "panel_rows":int(panel_rows),"paired_event_days":int(panel_paired_dates),
            "details":details}

def inspect(con):
    b=con.execute(f"""SELECT build_id FROM {P}lab_source_family_evidence_builds_v1
                       ORDER BY created_at DESC LIMIT 1""").fetchone()
    if not b: raise ValueError("Missing source inventory build")
    rows=con.execute(f"""SELECT domain,source_table_exists,source_row_count,
       first_observed_date,latest_observed_date,last_local_retrieved_at,
       provider_original_publication_verified,commercial_reuse_approved,
       institutional_factor_model_approved,expected_frequency,next_required_evidence
       FROM {P}lab_source_family_evidence_v1 WHERE build_id=?
       ORDER BY domain""",[b[0]]).fetchall()
    venue=con.execute(f"""SELECT count(*),count(DISTINCT run_id),
       count(DISTINCT CAST(capture_received_at AS DATE)),
       count(*) FILTER(WHERE provider_quote_freshness_verified OR historical_point_in_time_released)
       FROM {P}lab_live_market_captures_v1""").fetchone()
    nyfed=con.execute(f"""SELECT series_id,count(*),count(DISTINCT effective_date),
       min(effective_date),max(effective_date),
       count(*) FILTER(WHERE first_published_timestamp_verified
          OR provider_historical_revision_asof_verified
          OR downstream_license_approved OR production_risk_input_approved)
       FROM {P}lab_nyfed_rate_observations_retro_v1
       GROUP BY series_id ORDER BY series_id""").fetchall()
    grid=con.execute(f"""SELECT count(*),
       count(DISTINCT CAST(event_capture_at AS DATE)),
       count(*) FILTER(WHERE factor_available_at>event_capture_at OR
           factor_ingested_at>event_capture_at),
       count(*) FILTER(WHERE exchange_quote_time_independently_verified OR
           factor_publication_time_independently_verified OR
           event_to_factor_mapping_approved OR historical_backtest_released)
       FROM {P}lab_prospective_event_factor_grid_v1""").fetchone()
    panel=con.execute(f"""SELECT count(*),
        count(DISTINCT observed_date) FILTER(WHERE
           event_delta_pp IS NOT NULL AND factor_change_bps IS NOT NULL),
        count(*) FILTER(WHERE original_source_pit_verified OR
           independently_approved_causal_mapping OR institutional_risk_release)
        FROM {P}lab_event_factor_panel_v4_latest""").fetchone()
    return b[0],rows,venue,nyfed,grid,panel

def setup(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_source_temporal_depth_audit_builds_v1(
       build_id VARCHAR NOT NULL,source_family_build VARCHAR NOT NULL,
       source_git_sha VARCHAR NOT NULL,script_sha256 VARCHAR NOT NULL,
       built_at TIMESTAMPTZ NOT NULL,source_families BIGINT NOT NULL,
       loaded_families BIGINT NOT NULL,missing_families BIGINT NOT NULL,
       prospectively_received_market_records BIGINT NOT NULL,
       independent_warehouse_capture_dates BIGINT NOT NULL,
       official_nyfed_reference_rows BIGINT NOT NULL,
       minimum_nyfed_source_days BIGINT NOT NULL,
       historical_rate_research_screen_met BOOLEAN NOT NULL,
       asof_grid_rows BIGINT NOT NULL,asof_grid_capture_dates BIGINT NOT NULL,
       retrospective_panel_rows BIGINT NOT NULL,
       paired_event_factor_calendar_dates BIGINT NOT NULL,
       original_release_pit_approved BOOLEAN NOT NULL,
       commercial_reuse_approved BOOLEAN NOT NULL,
       institutional_event_model_approved BOOLEAN NOT NULL,
       disposition VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_source_temporal_depth_audit_domains_v1(
       build_id VARCHAR NOT NULL,domain VARCHAR NOT NULL,rows BIGINT NOT NULL,
       first_observed_date DATE,latest_observed_date DATE,
       last_local_retrieved_at TIMESTAMPTZ,expected_frequency VARCHAR NOT NULL,
       research_acceptance_state VARCHAR NOT NULL,next_required_evidence VARCHAR NOT NULL,
       original_release_pit_independently_verified BOOLEAN NOT NULL,
       commercial_reuse_rights_independently_approved BOOLEAN NOT NULL,
       institutional_event_or_beta_model_approved BOOLEAN NOT NULL)""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(sha)!=40 or any(
        x not in "0123456789abcdef" for x in sha):
        raise RuntimeError("Require pinned 40-character source and research-only scope")
    import duckdb
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        family_build,rows,venue,nyfed,grid,panel=inspect(con)
        summary=assess(family_build,rows,venue,nyfed,grid,panel)
        setup(con)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO {P}lab_source_temporal_depth_audit_builds_v1
               VALUES (?,?,?,?,current_timestamp,?,?,?,?,?,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,
                 'COVERAGE_AUDIT_ONLY_NO_ORIGINAL_PIT_OR_INSTITUTIONAL_LICENSE_APPROVAL')""",
               [build,family_build,sha,script_sha,summary["families"],
                summary["loaded"],summary["missing"],summary["venue_rows"],
                summary["capture_days"],summary["rate_rows"],
                summary["minimum_nyfed_days"],
                summary["nyfed_history_sufficient"],summary["grid_rows"],
                summary["grid_capture_days"],summary["panel_rows"],
                summary["paired_event_days"]])
            con.executemany(f"""INSERT INTO {P}lab_source_temporal_depth_audit_domains_v1
                VALUES ({','.join('?' for _ in range(12))})""",
                [(build,*d) for d in summary["details"]])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"BUILD_ID={build} FAMILY_BUILD={family_build}")
    print(f"SOURCES_LOADED={summary['loaded']}/{summary['families']} MISSING={summary['missing']}")
    print(f"VENUE_RECEIPTS={summary['venue_rows']} DISTINCT_CAPTURE_DATES={summary['capture_days']}")
    print(f"NYFED_REFERENCE_ROWS={summary['rate_rows']} MIN_NYFED_DAYS={summary['minimum_nyfed_days']} HISTORICAL_SCREEN={summary['nyfed_history_sufficient']}")
    print(f"ASOF_GRID={summary['grid_rows']} RETRO_PANEL={summary['panel_rows']} PAIRED_EVENT_DATES={summary['paired_event_days']}")
    print("SOURCE_PUBLISHED_AT_AND_REUSE_APPROVAL=FALSE CAUSAL_MODEL_RELEASE=FALSE")

if __name__=="__main__":
    main()
