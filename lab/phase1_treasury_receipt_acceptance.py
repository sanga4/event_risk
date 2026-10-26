#!/usr/bin/env python3
"""Independent SELECT-only receipt and original-byte acceptance of Treasury XML.

Runs *after* an explicitly authorized manual research source refresh, or on
demand. Verifies raw packet SHA256, provider URL + receipt clocks, the exact
Git/source-code producer, all persisted candidate rate values/hashes/units,
and manifest counters. Treasury observation date is NOT original publication
time. Historical PIT, rights, event causality and risk beta remain unapproved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import duckdb

import phase1_treasury_current_xml_refresh as source

P="eventrisk_factor_lab.main."
STATUS="OFFICIAL_XML_RECEIVED_RESEARCH_ONLY_NO_PROVIDER_PIT_OR_RIGHTS"
VERIFIED="TREASURY_INTERNAL_SOURCE_RECEIPT_RESEARCH_LINEAGE_ONLY"
GIT_SHA=re.compile(r"^[0-9a-f]{40}$")

def audit(manifest, packets, values,expected_git,expected_code_sha,
          prior_source_inventory=()):
    """Validate persisted source packets, derived values and exact research state.

    manifest = run,source git,script SHA,finished,nominal SHA,real SHA,
      provider observed days,new factor vintages,pit,rights,institutional,status
    packets = run,category,url,receipt,payload SHA,payload bytes,
      pit,rights
    values = factor_id,observed_date,value,unit,ingested_at,availability_at,
      availability_basis,provider,source_url,record_sha256,run_id
    """
    if not GIT_SHA.fullmatch(expected_git):
        raise ValueError("Acceptance needs exact pinned source Git SHA")
    if not re.fullmatch(r"[0-9a-f]{64}",expected_code_sha):
        raise ValueError("Acceptance needs original producer script SHA256")
    if manifest is None or len(manifest)!=12:
        raise ValueError("No complete persisted Treasury receipt manifest")
    (run,commit,source_hash,finished,nom_hash,real_hash,n_days,new_rows,
     pit,rights,risk,status)=manifest
    if (not isinstance(run,str) or not run or
        commit!=expected_git or source_hash!=expected_code_sha
        or not isinstance(finished,datetime) or finished.tzinfo is None
        or not isinstance(n_days,int) or n_days<0 or n_days>35
        or not isinstance(new_rows,int) or new_rows<0 or
        any(x is not False for x in (pit,rights,risk))
        or status!=STATUS):
        raise ValueError("Treasury producer build/approval state inconsistent")
    if len(packets)!=2 or len(values)!=new_rows:
        raise ValueError("Treasury source packets or observed rows missing")
    seen=set()
    raw=[]
    for row in packets:
        if len(row)!=8:
            raise ValueError("Malformed archived source packet identity")
        (packet_run,category,url,received,digest,content,
         authenticated_pub,rights_approved)=row
        if (category not in source.DATASET or category in seen or
            packet_run!=run or not isinstance(received,datetime)
            or received.tzinfo is None or received>finished
            or any(x is not False for x in (authenticated_pub,rights_approved))
            or not isinstance(content,(bytes,bytearray,memoryview))):
            raise ValueError("Unreconciled archived source packet / clock / approval")
        payload=bytes(content)
        if (len(payload)>source.MAX_RESPONSE_BYTES or
            not re.fullmatch(r"[0-9a-f]{64}",digest)
            or hashlib.sha256(payload).hexdigest()!=digest or
            url!=source.make_url(category,received.strftime("%Y%m"))):
            raise ValueError("Original Treasury response content SHA/URL changed")
        seen.add(category)
        raw.append({"category":category,"url":url,"received":received,
                    "bytes":payload,"sha256":digest})
    if seen!=set(source.DATASET) or any(
        p["received"].strftime("%Y%m")!=finished.strftime("%Y%m")
        for p in raw):
        raise ValueError("Treasury packet months/families do not match")
    psha={x["category"]:x["sha256"] for x in raw}
    if psha["nominal"]!=nom_hash or psha["real"]!=real_hash:
        raise ValueError("Manifest response SHA256 not backed by original XML")
    proposed,coverage=source.prepare(raw,prior_source_inventory,run,
                                     now=max(p["received"] for p in raw))
    if len(coverage)!=n_days:
        raise ValueError("Manifest research factor observed-date coverage wrong")
    if len(proposed)!=new_rows:
        raise ValueError("Source manifest does not match actual new/revised rate values")
    lookup={(p["factor_id"],p["date"]):p for p in proposed}
    found=set()
    for row in values:
        if len(row)!=11:
            raise ValueError("Invalid persisted factor-source schema")
        (factor,day,val,unit,ingest,available,basis,provider,url,digest,run_id)=row
        key=(factor,day)
        if key in found or key not in lookup or run_id!=run:
            raise ValueError("Duplicated or invented Treasury observed-source identity")
        sample=lookup[key]
        if (type(val) not in (int,float) or not math.isfinite(val) or
            not math.isclose(float(val),sample["value"],rel_tol=0,
                             abs_tol=1e-9) or
            unit!="percent" or
            not isinstance(ingest,datetime) or ingest.tzinfo is None or
            not isinstance(available,datetime) or available.tzinfo is None or
            ingest<sample["received"] or ingest>finished or
            available!=ingest or
            basis!=sample["availability_basis"] or
            provider!=sample["provider"] or
            url!=sample["source_url"] or
            digest!=sample["digest"]):
            raise ValueError("Treasury rate value, source digest, or availability drift")
        found.add(key)
    if found!=set(lookup):
        raise ValueError("Missing original Treasury new/revised source factor rows")
    # Source manifest must match the *exact* delta against earlier as-received
    # history, including legitimate no-op runs. A forged zero-row build without
    # corresponding prior rate levels is never accepted.
    return {
        "status":VERIFIED,"build_run_id":run,
        "source_git_sha":commit,"source_script_sha256":source_hash,
        "received_xml_categories":sorted(seen),
        "archived_payload_sha256":psha,
        "complete_recent_source_observation_days":n_days,
        "new_or_revised_factor_rows":len(found),
        "official_first_published_at_independently_verified":False,
        "historical_point_in_time_certified":False,
        "commercial_data_redistribution_approved":False,
        "identified_event_factor_causality":False,
        "institutional_model_beta_approved":False,
    }

def inspect(con,expected_git,producer_code_sha,prefix=P):
    manifest=con.execute(f"""SELECT run_id,source_git_sha,source_script_sha256,
       finished_at,source_nominal_sha256,source_real_sha256,
       source_observation_days,new_factor_vintages,
       original_publication_pit_verified,licensed_distribution_approved,
       institutional_beta_release,status
       FROM {prefix}lab_treasury_current_xml_runs_v1
       ORDER BY finished_at DESC,run_id DESC LIMIT 1""").fetchone()
    if manifest is None:
        raise ValueError("No materialized Treasury source receipt run exists")
    packets=con.execute(f"""SELECT run_id,source_category,source_url,
       source_received_at,original_payload_sha256,original_payload_bytes,
       original_publisher_first_release_verified,
       licensed_institutional_risk_use_approved
       FROM {prefix}lab_treasury_current_xml_packets_v1
       WHERE run_id=? ORDER BY source_category""",[manifest[0]]).fetchall()
    rows=con.execute(f"""SELECT factor_id,observed_date,value,unit,
       ingested_at,availability_at,availability_basis,provider,source_url,
       record_sha256,run_id
       FROM {prefix}lab_factor_observations
       WHERE run_id=? ORDER BY factor_id,observed_date""",[manifest[0]]).fetchall()
    received_max=max(x[3] for x in packets) if packets else None
    if received_max is None:
        raise ValueError("No original Treasury source packets")
    cutoff=(received_max-source.timedelta(
        days=source.MAX_RECENT_SOURCE_DAYS)).date()
    # Reconstruct only previously ORIGINAL-PACKET-backed warehouse vintages
    # known by source receipt time. Legacy retrospective CSV values are not
    # independent captured XML evidence and must not suppress first intake.
    factor_sql=",".join("'"+x+"'" for x in sorted(source.ALL_FACTORS))
    inventory=con.execute(f"""
       SELECT factor_id,observed_date,value FROM (
         SELECT factor_id,observed_date,value,
           row_number() OVER (
             PARTITION BY factor_id,observed_date
             ORDER BY ingested_at DESC,record_sha256 DESC) AS n
         FROM {prefix}lab_factor_observations
         WHERE run_id != ? AND ingested_at <= ?
           AND observed_date >= ?
           AND provider IN ('US_TREASURY_CURRENT_XML',
                            'US_TREASURY_DERIVED_CURRENT_XML')
           AND availability_basis =
                 'official_xml_http_receipt_not_original_publication'
           AND factor_id IN ({factor_sql})
       ) q WHERE n=1
    """,[manifest[0],received_max,cutoff]).fetchall()
    return audit(manifest,packets,rows,expected_git,producer_code_sha,
                 prior_source_inventory=inventory)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-commit",required=True)
    args=parser.parse_args()
    original_source=Path(__file__).with_name(
        "phase1_treasury_current_xml_refresh.py")
    code_sha=hashlib.sha256(original_source.read_bytes()).hexdigest()
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        # MotherDuck's default remote session may identify as Etc/Unknown.
        # DuckDB->Python TIMESTAMPTZ conversion then fails inside pytz
        # BEFORE the source audit even sees the row. Pin UTC per connection
        # rather than altering authentic stored source receipt timestamps.
        con.execute("SET TimeZone='UTC'")
        result=inspect(con,args.source_commit,code_sha)
    print(json.dumps(result,sort_keys=True,indent=2))
    print("PROVIDER_FIRST_PUBLICATION_PIT=UNVERIFIED RIGHTS=UNAPPROVED INSTITUTIONAL_RELEASE=FALSE")

if __name__=="__main__":
    sys.exit(main())
