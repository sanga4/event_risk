#!/usr/bin/env python3
"""Original-byte, receipt-timed Treasury daily nominal/real XML rate refresh.

A bounded manually dispatched RESEARCH acquisition of the *current month* of
official U.S. Treasury yields. This is NOT independently validated Treasury
first-publication time: source observed DATE != provider published timestamp.

Default PREVIEW does not modify the warehouse. Explicit opt-in records exact
provider XML byte packets, true HTTP receipt timestamps, 18 factor series
(11 nominal, five real, and two clearly labeled derived par-minus-real gaps),
and a versioned build manifest. No pre-receipt as-known timestamp is invented.
No source rights, trading, historical PIT, or institutional release asserted.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import duckdb
import requests

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-treasury-current-xml-refresh-v1.2.0"
BASE="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
DATASET={"nominal":"daily_treasury_yield_curve",
         "real":"daily_treasury_real_yield_curve"}
ATOM="{http://www.w3.org/2005/Atom}"
DATA="{http://schemas.microsoft.com/ado/2007/08/dataservices}"
METADATA="{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
NOMINAL={
 "DGS1MO":"BC_1MONTH","DGS3MO":"BC_3MONTH","DGS6MO":"BC_6MONTH",
 "DGS1":"BC_1YEAR","DGS2":"BC_2YEAR","DGS3":"BC_3YEAR",
 "DGS5":"BC_5YEAR","DGS7":"BC_7YEAR","DGS10":"BC_10YEAR",
 "DGS20":"BC_20YEAR","DGS30":"BC_30YEAR",
}
# Treasury's REAL yield OData feed uses TC_ tenor tags; nominal par
# yields use BC_ tags. Confusing them would silently parse zero real rates
# from otherwise valid source packets (see Treasury/FRED series TC_5YEAR).
REAL={
 "DGS5R":"TC_5YEAR","DGS7R":"TC_7YEAR","DGS10R":"TC_10YEAR",
 "DGS20R":"TC_20YEAR","DGS30R":"TC_30YEAR",
}
DERIVED={"PAR_NOMINAL_REAL_GAP_5Y":("DGS5","DGS5R"),
         "PAR_NOMINAL_REAL_GAP_10Y":("DGS10","DGS10R")}
ALL_FACTORS=frozenset(NOMINAL)|frozenset(REAL)|frozenset(DERIVED)
MAX_RESPONSE_BYTES=2_000_000
MAX_RECENT_SOURCE_DAYS=10
MAX_MONTH_ENTRIES=35

def make_url(category,month):
    if category not in DATASET or not re.fullmatch(r"20\d{4}",month):
        raise ValueError("Unsupported Treasury source class/month")
    return BASE+"?"+urlencode({
        "data":DATASET[category],
        "field_tdr_date_value_month":month
    })

def bounded_fetch(session,category,month):
    """Network response bytes and our actual receipt clock, never publication."""
    url=make_url(category,month)
    response=session.get(url,timeout=30,allow_redirects=False,
                         headers={"Accept":"application/atom+xml,application/xml"})
    response.raise_for_status()
    if response.status_code != 200 or not 100<=len(response.content)<=MAX_RESPONSE_BYTES:
        raise ValueError("Empty or oversized official Treasury XML response")
    if not response.content.lstrip().startswith(b"<?xml") and not response.content.lstrip().startswith(b"<feed"):
        raise ValueError("Treasury returned non-XML payload")
    received=datetime.now(timezone.utc)
    return {"category":category,"url":url,"received":received,
            "bytes":bytes(response.content),
            "sha256":hashlib.sha256(response.content).hexdigest()}

def parse_xml(payload,expected_fields):
    """Parse only Treasury OData NEW_DATE and allowed tenor fields.

    Source data is untrusted XML: cap document bytes; reject dates, duplicate
    daily values, unsupported fields and nonsensical numeric estimates.
    Empty tenors are missing, never zeros. Do not invent missing trading days.
    """
    if not isinstance(payload,bytes) or len(payload)>MAX_RESPONSE_BYTES:
        raise ValueError("Malformed or oversized rate XML source")
    try:
        root=ET.fromstring(payload)
    except ET.ParseError as ex:
        raise ValueError("Malformed official Treasury XML") from ex
    if root.tag != ATOM+"feed":
        raise ValueError("Expected official Treasury Atom feed root")
    entries=root.findall(ATOM+"entry")
    if not entries or len(entries)>MAX_MONTH_ENTRIES:
        raise ValueError("Missing or excessive Treasury calendar entries")
    wanted=set(expected_fields.values())
    days={}
    for entry in entries:
        props=entry.find(".//"+METADATA+"properties")
        if props is None:
            raise ValueError("Missing Treasury OData entry properties")
        raw={p.tag.rsplit("}",1)[-1]:p.text for p in props
             if p.tag.startswith(DATA)}
        day_txt=raw.get("NEW_DATE")
        if not isinstance(day_txt,str) or not re.match(r"^\d{4}-\d\d-\d\d",day_txt):
            raise ValueError("Missing original Treasury observed date")
        try:
            day=date.fromisoformat(day_txt[:10])
        except ValueError as ex:
            raise ValueError("Invalid Treasury observed date") from ex
        values={}
        for name in wanted:
            txt=raw.get(name)
            if txt is None or not txt.strip():
                continue
            try:
                x=float(txt)
            except ValueError as ex:
                raise ValueError(f"Invalid Treasury {name} rate") from ex
            if not math.isfinite(x) or not -10.0<=x<=50.0:
                raise ValueError(f"Implausible or missing Treasury {name} rate")
            values[name]=round(x,9)
        if day in days:
            raise ValueError("Duplicate official Treasury source-date entry")
        days[day]=values
    return days

def assemble(nominal,real,received_at,month):
    """Full 18-factor same-day source panel for date candidates only."""
    if set(nominal)!=set(real) or not nominal:
        raise ValueError("Treasury nominal/real source-day mismatch")
    out=[]
    for day in sorted(nominal):
        if day.strftime("%Y%m")!=month:
            raise ValueError("Cross-month source rows not permitted")
        if day>received_at.date() or day<received_at.date()-timedelta(days=MAX_RECENT_SOURCE_DAYS):
            continue
        n=nominal[day];r=real[day]
        if set(NOMINAL.values())-set(n) or set(REAL.values())-set(r):
            # Refuse incomplete factor-day population. Do not fill a missing
            # tenor from yesterday and mislabel it a new original source day.
            raise ValueError(f"Incomplete official 18-factor curve on {day}")
        values={name:n[col] for name,col in NOMINAL.items()}
        values.update({name:r[col] for name,col in REAL.items()})
        values.update({name:round(values[x]-values[y],9)
                       for name,(x,y) in DERIVED.items()})
        if set(values)!=ALL_FACTORS:
            raise ValueError("Unexpected Treasury factor universe")
        out.append((day,values))
    return out

def prepare(raw, existing, run_id,now=None):
    """Build proposal from exact current source bytes and current warehouse.

    existing: (factor_id,observed_date,value) from previously captured
    ORIGINAL XML packet-backed vintages only. An equal retrospective CSV
    level does not prove a source HTTP receipt or provenance.
    """
    if len(raw)!=2 or {p["category"] for p in raw}!=set(DATASET):
        raise ValueError("Need both original nominal and real source packets")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware actual fetch receipt required")
    month=now.strftime("%Y%m")
    for packet in raw:
        if packet["url"]!=make_url(packet["category"],month):
            raise ValueError("Unexpected original Treasury URL")
        if packet["received"].tzinfo is None or packet["received"]>now+timedelta(seconds=30):
            raise ValueError("Unverifiable provider receipt chronology")
        if hashlib.sha256(packet["bytes"]).hexdigest()!=packet["sha256"]:
            raise ValueError("Original XML packet bytes fail SHA256")
    src={p["category"]:p for p in raw}
    nominal=parse_xml(src["nominal"]["bytes"],NOMINAL)
    real=parse_xml(src["real"]["bytes"],REAL)
    captures=assemble(nominal,real,max(p["received"] for p in raw),month)
    recent={}
    for name,day,value in existing:
        key=(name,day)
        if name not in ALL_FACTORS or key in recent or not math.isfinite(float(value)):
            raise ValueError("Invalid original warehouse latest-vintage inventory")
        recent[key]=float(value)
    result=[]
    both_sha=hashlib.sha256(
        (src["nominal"]["sha256"]+src["real"]["sha256"]).encode()).hexdigest()
    for day,values in captures:
        for name,value in sorted(values.items()):
            if (name,day) in recent and math.isclose(
                    value,recent[name,day],rel_tol=0,abs_tol=1e-9):
                continue
            category=("nominal" if name in NOMINAL else
                      "real" if name in REAL else "derived")
            packet=src.get(category,src["real"])
            digest=hashlib.sha256(json.dumps({
                "factor":name,"observed_date":day.isoformat(),
                "value_percent":value,"source_payload_sha256":
                    both_sha if category=="derived" else packet["sha256"],
                "source_type":category,"source_url":
                    "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"
                    if category=="derived" else packet["url"]
            },sort_keys=True,separators=(",",":")).encode()).hexdigest()
            result.append({
                "factor_id":name,"date":day,"value":value,"digest":digest,
                "provider":("US_TREASURY_DERIVED_CURRENT_XML"
                            if category=="derived" else
                            "US_TREASURY_CURRENT_XML"),
                "source_url":("https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"
                    if category=="derived" else packet["url"]),
                "received":max(p["received"] for p in raw)
                    if category=="derived" else packet["received"],
                "availability_basis":"official_xml_http_receipt_not_original_publication",
                "run_id":run_id,
            })
    return result,captures

def existing_inventory(con,now):
    oldest=(now-timedelta(days=MAX_RECENT_SOURCE_DAYS)).date()
    rows=con.execute(f"""
        SELECT factor_id,observed_date,value
        FROM (
          SELECT factor_id,observed_date,value,
          row_number() OVER(PARTITION BY factor_id,observed_date
                            ORDER BY ingested_at DESC,record_sha256 DESC) rank
          FROM {P}lab_factor_observations
          WHERE observed_date>=?
            AND provider IN ('US_TREASURY_CURRENT_XML',
                             'US_TREASURY_DERIVED_CURRENT_XML')
            AND availability_basis =
                'official_xml_http_receipt_not_original_publication'
            AND factor_id IN (
            {','.join(["'"+s+"'" for s in sorted(ALL_FACTORS)])})
        ) q WHERE rank=1
    """,[oldest]).fetchall()
    return rows

def append(con,proposed,raw,run,source_sha,script_hash,complete_days):
    """Only explicitly confirmed; atomic research rows plus literal bytes."""
    for category in ("nominal","real"):
        if sum(p["category"]==category for p in raw)!=1:
            raise ValueError("Source packet category mismatch")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_treasury_current_xml_packets_v1(
        run_id VARCHAR NOT NULL,source_category VARCHAR NOT NULL,
        source_url VARCHAR NOT NULL,source_received_at TIMESTAMPTZ NOT NULL,
        original_payload_sha256 VARCHAR NOT NULL,
        original_payload_bytes BLOB NOT NULL,
        original_publisher_first_release_verified BOOLEAN NOT NULL,
        licensed_institutional_risk_use_approved BOOLEAN NOT NULL)
    """)
    con.execute(f"""CREATE TABLE IF NOT EXISTS {P}lab_treasury_current_xml_runs_v1(
        run_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
        source_script_sha256 VARCHAR NOT NULL,finished_at TIMESTAMPTZ NOT NULL,
        source_nominal_sha256 VARCHAR NOT NULL,source_real_sha256 VARCHAR NOT NULL,
        source_observation_days BIGINT NOT NULL,new_factor_vintages BIGINT NOT NULL,
        original_publication_pit_verified BOOLEAN NOT NULL,
        licensed_distribution_approved BOOLEAN NOT NULL,
        institutional_beta_release BOOLEAN NOT NULL,
        status VARCHAR NOT NULL)
    """)
    # Exact external HTTP receipt is preserved separately in packet rows.
    # Database availability cannot be backdated to the earlier HTTP receipt.
    packets=[(run,p["category"],p["url"],p["received"],p["sha256"],
              p["bytes"],False,False) for p in raw]
    con.execute("BEGIN TRANSACTION")
    try:
        warehouse_load_at=datetime.now(timezone.utc)
        if any(p["received"]>warehouse_load_at for p in raw):
            raise ValueError("Treasury response received after warehouse load clock")
        rows=[(x["factor_id"],x["date"],x["value"],"percent",
              warehouse_load_at,warehouse_load_at,x["availability_basis"],
              x["provider"],x["source_url"],x["digest"],x["run_id"])
              for x in proposed]
        con.executemany(f"""
            INSERT INTO {P}lab_treasury_current_xml_packets_v1
            VALUES ({','.join(['?']*8)})""",packets)
        if rows:
            con.executemany(f"""
                INSERT INTO {P}lab_factor_observations
                VALUES ({','.join(['?']*11)})""",rows)
        con.execute(f"""INSERT INTO {P}lab_treasury_current_xml_runs_v1
            VALUES (?,?,?,?,?,?,?,?,FALSE,FALSE,FALSE,
              'OFFICIAL_XML_RECEIVED_RESEARCH_ONLY_NO_PROVIDER_PIT_OR_RIGHTS')
        """,[run,source_sha,script_hash,datetime.now(timezone.utc),
             next(p["sha256"] for p in raw if p["category"]=="nominal"),
             next(p["sha256"] for p in raw if p["category"]=="real"),
             complete_days,len(rows)])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

def main():
    write="--append-research" in sys.argv[1:]
    if len(sys.argv)>2 or (sys.argv[1:] and sys.argv[1:]!=["--append-research"]):
        raise ValueError("Only --append-research is supported; default preview is read-only")
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if (not re.fullmatch(r"[0-9a-f]{40}",commit) or
        os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"):
        raise ValueError("Exact source Git SHA and internal-only research scope required")
    if write and os.getenv("LAB_SOURCE_REFRESH_WRITE_ACK")!="confirmed":
        raise ValueError("Explicit Treasury source research append approval required")
    now=datetime.now(timezone.utc)
    run=VERSION+"-"+now.strftime("%Y%m%dT%H%M%S%fZ")
    script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    month=now.strftime("%Y%m")
    with requests.Session() as session:
        raw=[bounded_fetch(session,k,month) for k in ("nominal","real")]
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        inventory=existing_inventory(con,now)
        proposed,coverage=prepare(raw,inventory,run,now=now)
        if write:
            append(con,proposed,raw,run,commit,script_hash,len(coverage))
    print(json.dumps({
        "mode":"APPEND_ONLY_RESEARCH" if write else "READ_ONLY_PREVIEW",
        "research_source":"US_TREASURY_OFFICIAL_CURRENT_MONTH_NOMINAL_AND_REAL_XML",
        "source_observation_days":len(coverage),
        "proposed_new_research_factor_records":len(proposed),
        "new_factor_observed_dates":sorted({x["date"].isoformat() for x in proposed}),
        "run_id":run if write else None,
        "original_publisher_first_release_verified":False,
        "external_license_approved":False,
        "institutional_beta_release":False,
    },sort_keys=True,indent=2))

if __name__=="__main__":
    main()
