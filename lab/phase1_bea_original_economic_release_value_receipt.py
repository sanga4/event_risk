#!/usr/bin/env python3
"""Exact official BEA page packets and explicitly labeled values AS RECEIVED.

Research only. Does not backdate first-published time, certify pre-event
consensus, tradeability, institutional source rights, or publisher revisions.
Two original August 2026 BEA release pages, no guessed series mappings.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
import re

import bs4
import requests

VERSION="phase1-bea-original-release-values-receipt-v1.0.0"
DB="eventrisk_factor_lab"
P=DB+".main."
SOURCES=(
 ("aug2026_personal_income",
  "https://www.bea.gov/news/2026/personal-income-and-outlays-August-2026",
  "Personal Income and Outlays, August 2026"),
 ("aug2026_international_trade",
  "https://www.bea.gov/news/2026/us-international-trade-goods-and-services-august-2026",
  "U.S. International Trade in Goods and Services, August 2026"),
)
PI_ROWS=(
 "Current-dollar personal income","Current-dollar DPI","Real DPI",
 "Current-dollar PCE","Real PCE","PCE price index",
 "PCE price index excluding food and energy")
TRADE_ROWS=("Deficit:","Exports:","Imports:")
STATUS="ORIGINAL_BEA_RELEASE_PAGE_RETRIEVED_LATER_NOT_FIRST_PUBLICATION"
MAX_BYTES=1_000_000

def fetch(session,kind,url):
    if (kind,url) not in [(x[0],x[1]) for x in SOURCES]:
        raise ValueError("Unapproved BEA historical source URL")
    r=session.get(url,timeout=(15,45),allow_redirects=False,
                  headers={"User-Agent":"EventRiskFactorResearch/1.0 (research source receipt)"})
    if r.status_code!=200 or r.url!=url or r.is_redirect:
        raise ValueError("Official BEA response failed exact URL/status check")
    if "text/html" not in r.headers.get("Content-Type","").lower():
        raise ValueError("Original BEA source is not HTML")
    data=r.content
    if len(data)<10_000 or len(data)>MAX_BYTES:
        raise ValueError("Unexpected official BEA page byte count")
    return {"kind":kind,"url":url,"raw_html":data,
            "sha256":hashlib.sha256(data).hexdigest(),
            "received_at":datetime.now(timezone.utc)}

def parse(packet):
    kind=packet["kind"]
    if kind not in (SOURCES[0][0],SOURCES[1][0]):
        raise ValueError("Unknown immutable source")
    expected=next(x for x in SOURCES if x[0]==kind)
    if packet["url"]!=expected[1] or hashlib.sha256(packet["raw_html"]).hexdigest()!=packet["sha256"]:
        raise ValueError("Official BEA original packet mismatch")
    soup=bs4.BeautifulSoup(packet["raw_html"],"html.parser")
    headings=[e.get_text(" ",strip=True) for e in soup.select("h1")]
    if expected[2] not in headings:
        raise ValueError("Wrong BEA publisher release headline")
    if kind=="aug2026_personal_income":
        tabs=soup.select("table.table-md")
        if len(tabs)!=1 or "Personal Income and Related Measures" not in tabs[0].get_text(" ",strip=True):
            raise ValueError("BEA monthly personal income table missing")
        records=[]
        seen={}
        for row in tabs[0].select("tr"):
            cells=row.find_all(["td"],recursive=False)
            if len(cells)!=3:continue
            fields=[cell.get_text(" ",strip=True) for cell in cells]
            if fields[0] in PI_ROWS:
                if fields[0] in seen:
                    raise ValueError("Duplicate BEA personal income metric")
                try:
                    before=float(fields[1]);reported=float(fields[2])
                except ValueError as e:
                    raise ValueError("Invalid BEA monthly rate") from e
                if not (-100<reported<100 and -100<before<100):
                    raise ValueError("BEA monthly percent out of range")
                seen[fields[0]]=reported
                records.append({"metric":fields[0],"reported_value":reported,
                                "prior_month_reported_value":before,
                                "unit":"percent_change_from_previous_month",
                                "period":"2026-08"})
        if set(seen)!=set(PI_ROWS) or len(records)!=7:
            raise ValueError("Missing official seven personal income / PCE values")
        return records
    tabs=soup.select("table.table-release-trade")
    if len(tabs)!=1:
        raise ValueError("BEA international trade release summary table missing")
    records=[]
    seen=set()
    for row in tabs[0].select("tr"):
        cells=row.find_all(["td"],recursive=False)
        if len(cells)<2:continue
        metric=cells[0].get_text(" ",strip=True)
        if metric not in TRADE_ROWS:continue
        if metric in seen:
            raise ValueError("Duplicate BEA trade amount")
        data=cells[1].get_text(" ",strip=True)
        match=re.fullmatch(r"\$([\d,]+\.\d+) Billion",data)
        if match is None:
            raise ValueError("Malformed BEA trade dollar billions amount")
        value=float(match.group(1).replace(",",""))
        if value<=0 or value>10000:
            raise ValueError("BEA trade amount outside plausible bounds")
        seen.add(metric)
        records.append({"metric":metric.removesuffix(":").lower()+"_reported_magnitude",
                        "reported_value":value,"prior_month_reported_value":None,
                        "unit":"usd_billions",
                        "period":"2026-08"})
    if len(seen)!=3:
        raise ValueError("Missing three official BEA trade summary amounts")
    return records

def archive(con,packets,observations,run):
    if os.getenv("LAB_RESEARCH_WRITE_ACK")!="confirmed":
        raise RuntimeError("Explicit research-only write acknowledgment required")
    if len(packets)!=2 or any(len(v) not in (3,7) for v in observations.values()):
        raise ValueError("Incomplete two-page source collection")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_bea_original_release_page_receipts_v1(
        build_id VARCHAR NOT NULL,source_git_commit VARCHAR NOT NULL,
        source_kind VARCHAR NOT NULL,source_url VARCHAR NOT NULL,
        source_http_received_at TIMESTAMPTZ NOT NULL,
        original_payload_sha256 VARCHAR NOT NULL,original_html BLOB NOT NULL,
        parsed_observation_count BIGINT NOT NULL,
        warehouse_ingested_at TIMESTAMPTZ NOT NULL,
        provider_first_publication_verified BOOLEAN NOT NULL,
        original_revision_vintage_verified BOOLEAN NOT NULL,
        pre_event_consensus_verified BOOLEAN NOT NULL,
        redistribution_rights_approved BOOLEAN NOT NULL,
        institutional_event_model_approved BOOLEAN NOT NULL,
        source_status VARCHAR NOT NULL)""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_bea_original_reported_values_v1(
        build_id VARCHAR NOT NULL,source_kind VARCHAR NOT NULL,
        original_payload_sha256 VARCHAR NOT NULL,
        reported_period VARCHAR NOT NULL,reported_metric VARCHAR NOT NULL,
        reported_value DOUBLE NOT NULL,prior_month_value DOUBLE,
        reported_unit VARCHAR NOT NULL,
        source_http_received_at TIMESTAMPTZ NOT NULL,
        warehouse_ingested_at TIMESTAMPTZ NOT NULL,
        publisher_first_known_at TIMESTAMPTZ,
        verified_announcement_surprise DOUBLE,
        original_provider_first_release_certified BOOLEAN NOT NULL,
        survey_consensus_asof_verified BOOLEAN NOT NULL,
        licensed_downstream_use BOOLEAN NOT NULL,
        institutional_model_approved BOOLEAN NOT NULL)""")
    digests=[p["sha256"] for p in packets]
    count=con.execute(
        f"SELECT count(*) FROM {P}lab_bea_original_release_page_receipts_v1 WHERE original_payload_sha256 IN (?,?)",
        digests).fetchone()[0]
    if count:
        raise ValueError("One or more original BEA packets already stored: no duplicate writes")
    warehouse_at=datetime.now(timezone.utc)
    if any(p["received_at"]>warehouse_at for p in packets):
        raise ValueError("Source receipt cannot follow warehouse append timestamp")
    con.execute("BEGIN TRANSACTION")
    try:
        con.executemany(
            f"""INSERT INTO {P}lab_bea_original_release_page_receipts_v1
                VALUES (?,?,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,FALSE,FALSE,?)""",
            [(run,os.environ["LAB_PIPELINE_COMMIT"],p["kind"],p["url"],
              p["received_at"],p["sha256"],p["raw_html"],
              len(observations[p["kind"]]),warehouse_at,STATUS)
             for p in packets])
        con.executemany(
            f"""INSERT INTO {P}lab_bea_original_reported_values_v1
                VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,FALSE,FALSE,FALSE,FALSE)""",
            [(run,p["kind"],p["sha256"],row["period"],row["metric"],
              row["reported_value"],row["prior_month_reported_value"],
              row["unit"],p["received_at"],warehouse_at)
             for p in packets for row in observations[p["kind"]]])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--append-research",action="store_true")
    args=cli.parse_args()
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or not re.fullmatch(r"[0-9a-f]{40}",os.getenv("LAB_PIPELINE_COMMIT",""))):
        raise RuntimeError("Pinned research-only original-source receipts required")
    with requests.Session() as sess:
        packets=[fetch(sess,kind,url) for kind,url,_ in SOURCES]
    observations={p["kind"]:parse(p) for p in packets}
    run=VERSION+"-"+packets[-1]["received_at"].strftime("%Y%m%dT%H%M%S%fZ")
    if args.append_research:
        import duckdb
        with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
            con.execute("SET TimeZone='UTC'")
            archive(con,packets,observations,run)
    print(json.dumps({
        "build_id":run,"mode":"RESEARCH_APPEND" if args.append_research else "READ_ONLY_PREVIEW",
        "source_observation_period":"2026-08",
        "source_packets":[{"kind":p["kind"],"http_received_at":p["received_at"].isoformat(),
                           "url":p["url"],"sha256":p["sha256"],"bytes":len(p["raw_html"])}
                          for p in packets],
        "reported_values":[{"source":k,**x} for k,rows in observations.items() for x in rows],
        "source_reported_value_count":sum(map(len,observations.values())),
        "first_publisher_release_time_verified":False,
        "historical_as_first_known_pit_approved":False,
        "original_survey_consensus_verified":False,
        "contractual_downstream_use_approved":False,
        "institutional_event_beta_approved":False,
        "disposition":STATUS},sort_keys=True))

if __name__=="__main__":
    main()
