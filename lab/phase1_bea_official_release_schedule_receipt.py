#!/usr/bin/env python3
"""Official BEA FUTURE SCHEDULE as OBSERVED on HTTP receipt, not released data.

Research-only, source-byte-preserving, bounded, on-demand. This is deliberately
NOT lab_source_release_vintages_v1: an advance schedule is never actual data,
a first-published timestamp, pre-event consensus, or source-license approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from zoneinfo import ZoneInfo

import bs4
import requests

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-bea-release-schedule-receipt-v1.0.0"
URL="https://www.bea.gov/news/schedule/"
STATUS="SCHEDULE_OBSERVED_AT_HTTP_RECEIPT_NOT_ACTUAL_RELEASE"
EASTERN=ZoneInfo("America/New_York")
MAX_BYTES=2_000_000

def fetch(session):
    r=session.get(URL,timeout=(15,40),allow_redirects=False,
                  headers={"User-Agent":"EventRiskFactorResearch/1.0"})
    if r.status_code!=200 or r.url!=URL or r.is_redirect:
        raise ValueError("Official BEA release schedule GET not authorized or unsuccessful")
    if "text/html" not in r.headers.get("Content-Type","").lower():
        raise ValueError("Expected publisher text/html")
    raw=r.content
    if not 1000<=len(raw)<=MAX_BYTES:
        raise ValueError("Malformed or oversized official BEA schedule packet")
    retrieved_at=datetime.now(timezone.utc)
    return raw,retrieved_at

def parse(raw,retrieved_at):
    if not isinstance(raw,bytes) or not raw or (
            not isinstance(retrieved_at,datetime) or retrieved_at.tzinfo is None):
        raise ValueError("Original source bytes and true UTC HTTP receipt required")
    soup=bs4.BeautifulSoup(raw,"html.parser")
    t=soup.select_one("table#release-schedule-table")
    if t is None:
        raise ValueError("Publisher release schedule HTML table missing")
    header=t.select_one("thead")
    if header is None:
        raise ValueError("Publisher release year heading missing")
    match=re.fullmatch(r"Year (\d{4})",header.get_text(" ",strip=True).replace(
        "  "," ").split("Release",1)[0].strip())
    if not match:
        raise ValueError("Cannot independently parse BEA release schedule year")
    year=int(match.group(1))
    if year<retrieved_at.year-1 or year>retrieved_at.year+1:
        raise ValueError("Release year outside source receipt window")
    rows=[]
    unparsed=0
    for tr in t.select("tbody tr"):
        cells=tr.select("td")
        if not cells:
            continue
        if len(cells)<3:
            raise ValueError("Official BEA release schedule changed column layout")
        when,kind,title=(v.get_text(" ",strip=True) for v in cells[:3])
        if not when or when.lower().startswith(("to be announced","tba")):
            unparsed+=1
            continue
        if not title or len(title)>400:
            raise ValueError("Official release title invalid")
        kind=" ".join(kind.split())
        if not kind or len(kind)>40:
            raise ValueError("Official release type invalid")
        try:
            scheduled=datetime.strptime(
                f"{year} {when}", "%Y %B %d %I:%M %p"
            ).replace(tzinfo=EASTERN).astimezone(timezone.utc)
        except ValueError as e:
            raise ValueError("Source scheduled UTC time cannot be parsed") from e
        if scheduled.year not in (year,year+1):
            raise ValueError("Scheduled release date outside publisher calendar")
        key=hashlib.sha256((scheduled.isoformat()+"|"+kind+"|"+title).encode()).hexdigest()
        rows.append({"source_key_sha256":key,"scheduled_at_utc":scheduled,
                     "scheduled_date_et":scheduled.astimezone(EASTERN).date(),
                     "release_type":kind,"release_title":title})
    if len(rows)<3 or len(rows)>250 or len(set(x["source_key_sha256"] for x in rows))!=len(rows):
        raise ValueError("Implausible, missing or duplicate authentic scheduled entries")
    return rows,unparsed,year

def append(con,run,source_sha,raw,received,rows,skipped,year):
    """Two source-history research tables; no event-vintage or approval products."""
    if os.getenv("LAB_RESEARCH_WRITE_ACK")!="confirmed":
        raise RuntimeError("Explicit research schedule archive acknowledgement required")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_bea_schedule_receipt_builds_v1(
        run_id VARCHAR NOT NULL,source_git_commit VARCHAR NOT NULL,
        retrieved_at TIMESTAMPTZ NOT NULL,source_url VARCHAR NOT NULL,
        raw_sha256 VARCHAR NOT NULL,raw_html BLOB NOT NULL,
        source_calendar_year INTEGER NOT NULL,release_entries BIGINT NOT NULL,
        tba_entries BIGINT NOT NULL,ingested_at TIMESTAMPTZ NOT NULL,
        actual_publication_time_verified BOOLEAN NOT NULL,
        reported_numeric_release_value_verified BOOLEAN NOT NULL,
        pre_event_consensus_verified BOOLEAN NOT NULL,
        downstream_rights_approved BOOLEAN NOT NULL,
        institutional_model_release BOOLEAN NOT NULL,status VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_bea_schedule_events_v1(
        run_id VARCHAR NOT NULL,source_key_sha256 VARCHAR NOT NULL,
        scheduled_at_utc TIMESTAMPTZ NOT NULL,
        scheduled_date_eastern DATE NOT NULL,
        release_type VARCHAR NOT NULL,release_title VARCHAR NOT NULL,
        source_retrieved_at TIMESTAMPTZ NOT NULL,source_html_sha256 VARCHAR NOT NULL,
        actual_published_at TIMESTAMPTZ,
        reported_numeric_value DOUBLE,
        original_publisher_release_verified BOOLEAN NOT NULL,
        licensed_risk_use BOOLEAN NOT NULL,
        institutional_event_model_approved BOOLEAN NOT NULL)""")
    if con.execute(f"SELECT COUNT(*) FROM {P}lab_bea_schedule_receipt_builds_v1 WHERE raw_sha256=?",
                   [source_sha]).fetchone()[0]:
        raise ValueError("Exact BEA calendar snapshot already archived; no duplicate write")
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"""INSERT INTO {P}lab_bea_schedule_receipt_builds_v1
           VALUES (?,?,?,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,FALSE,FALSE,?)""",
           [run,os.environ["LAB_PIPELINE_COMMIT"],received,URL,
            source_sha,raw,year,len(rows),skipped,datetime.now(timezone.utc),STATUS])
        con.executemany(f"""INSERT INTO {P}lab_bea_schedule_events_v1
            VALUES (?,?,?,?,?,?,?,?,NULL,NULL,FALSE,FALSE,FALSE)""",
            [(run,e["source_key_sha256"],e["scheduled_at_utc"],
              e["scheduled_date_et"],e["release_type"],e["release_title"],
              received,source_sha) for e in rows])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--append-research",action="store_true")
    args=parser.parse_args()
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or not re.fullmatch(
            r"[0-9a-f]{40}",commit):
        raise RuntimeError("Pinned immutable source commit, internal research only")
    with requests.Session() as session:
        raw,received=fetch(session)
    rows,skipped,year=parse(raw,received)
    digest=hashlib.sha256(raw).hexdigest()
    run=VERSION+"-"+received.strftime("%Y%m%dT%H%M%S%fZ")
    if args.append_research:
        import duckdb
        with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
            con.execute("SET TimeZone='UTC'")
            append(con,run,digest,raw,received,rows,skipped,year)
    print(json.dumps({
        "run_id":run,"source":"BEA_OFFICIAL_SCHEDULE_HTML",
        "source_url":URL,"mode":"RESEARCH_APPEND" if args.append_research else "READ_ONLY_PREVIEW",
        "original_packet_sha256":digest,"original_packet_bytes":len(raw),
        "source_http_received_at":received.isoformat(),
        "source_calendar_year":year,"valid_scheduled_entries":len(rows),
        "unparseable_or_tba_entries":skipped,
        "earliest_scheduled_at_utc":min(x["scheduled_at_utc"] for x in rows).isoformat(),
        "latest_scheduled_at_utc":max(x["scheduled_at_utc"] for x in rows).isoformat(),
        "scheduled_entries": [{
            "scheduled_at_utc":x["scheduled_at_utc"].isoformat(),
            "release_title":x["release_title"]
        } for x in rows[:5]],
        "actual_publication_verified":False,
        "reported_economic_value_verified":False,
        "pre_event_consensus_verified":False,
        "source_rights_approved":False,
        "institutional_event_beta_approved":False,
        "disposition":STATUS
    },sort_keys=True))

if __name__=="__main__":
    main()
