#!/usr/bin/env python3
"""NY Fed SOFR and EFFR original-publisher JSON backfill; internal-only.

percentRate is an annualized overnight interest rate in PERCENT, not a daily
security return; 100×daily rate-level difference gives change in yield bps.
effectiveDate is the underlying rate observation/effective date, NOT the
independently verified original publication timestamp. Keep revised source
snapshots and revisionIndicator, leave PIT/distribution approval FALSE.
"""
from __future__ import annotations
from datetime import date,datetime,timezone
from pathlib import Path
import csv,hashlib,io,json,math,os,tempfile
import requests,duckdb

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-nyfed-overnight-rates-v1.0.0"
BASE="https://markets.newyorkfed.org/api/rates"
SOURCES=(("SOFR","secured/sofr"),("EFFR","unsecured/effr"))
MAX_BYTES=5_000_000

def parse_records(raw:bytes,expect:str):
    if len(raw)<40 or len(raw)>MAX_BYTES:raise ValueError("Source payload unacceptable")
    obj=json.loads(raw)
    if not isinstance(obj,dict) or not isinstance(obj.get("refRates"),list):
        raise ValueError("Unexpected NY Fed JSON rate envelope")
    records=obj["refRates"]
    if len(records)<250:raise ValueError("Insufficient historical source rate observations")
    seen=set();out=[]
    for r in records:
        if not isinstance(r,dict):raise ValueError("Malformed source rate row")
        if r.get("type")!=expect:raise ValueError("NY Fed wrong rate type")
        day=date.fromisoformat(str(r["effectiveDate"]))
        if day>datetime.now(timezone.utc).date() or day<date(2010,1,1) or day in seen:
            raise ValueError("Invalid or duplicate effective-date row")
        seen.add(day)
        rate=float(r["percentRate"])
        if not math.isfinite(rate) or rate<-5 or rate>=100:
            raise ValueError("Implausible overnight annualized interest rate")
        volume=r.get("volumeInBillions")
        if volume is not None:
            volume=float(volume)
            if not math.isfinite(volume) or volume<0:raise ValueError("Bad trade volume")
        revision=str(r.get("revisionIndicator") or "")
        if len(revision)>64:raise ValueError("Invalid revision indicator")
        out.append((day.isoformat(),expect,rate,volume,revision))
    out.sort(key=lambda r:r[0])
    if out[-1][0]<"2024-01-01":raise ValueError("Historical endpoint stale")
    return out

def download(sid,part):
    url=f"{BASE}/{part}/last/250.json"
    r=requests.get(url,timeout=(10,40),
        headers={"Accept":"application/json",
                 "User-Agent":"EventRiskFactor-internal-research/1.0"})
    r.raise_for_status()
    raw=r.content
    parsed=parse_records(raw,sid)
    return sid,url,hashlib.sha256(raw).hexdigest(),len(raw),r.headers.get("Last-Modified"),parsed

def setup(con):
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_nyfed_rate_source_vintages_v1(
       provider VARCHAR NOT NULL,source_rate_id VARCHAR NOT NULL,
       source_url VARCHAR NOT NULL,json_sha256 VARCHAR NOT NULL,
       source_bytes BIGINT NOT NULL,http_last_modified VARCHAR,
       original_retrieved_at TIMESTAMPTZ NOT NULL,
       first_build_id VARCHAR NOT NULL,
       original_publication_clock_verified BOOLEAN NOT NULL,
       downstream_external_rights_approved BOOLEAN NOT NULL)
    """)
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_nyfed_rate_observations_retro_v1(
       provider VARCHAR NOT NULL,series_id VARCHAR NOT NULL,
       effective_date DATE NOT NULL,annual_rate_percent DOUBLE NOT NULL,
       source_volume_billion_usd DOUBLE,
       source_revision_indicator VARCHAR,
       source_url VARCHAR NOT NULL,source_json_sha256 VARCHAR NOT NULL,
       source_response_received_at TIMESTAMPTZ NOT NULL,
       original_provider_published_at TIMESTAMPTZ,
       provider_historical_revision_asof_verified BOOLEAN NOT NULL,
       first_published_timestamp_verified BOOLEAN NOT NULL,
       downstream_license_approved BOOLEAN NOT NULL,
       production_risk_input_approved BOOLEAN NOT NULL,
       research_only BOOLEAN NOT NULL,first_build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_nyfed_daily_rate_deltas_retro_v1(
       build_id VARCHAR NOT NULL,series_id VARCHAR NOT NULL,
       effective_date DATE NOT NULL,previous_effective_date DATE NOT NULL,
       annual_rate_percent DOUBLE NOT NULL,previous_rate_percent DOUBLE NOT NULL,
       interest_rate_change_basis_points DOUBLE NOT NULL,
       source_json_sha256 VARCHAR NOT NULL,
       first_original_publication_verified BOOLEAN NOT NULL,
       is_identified_policy_or_funding_surprise BOOLEAN NOT NULL,
       production_risk_input_approved BOOLEAN NOT NULL
    )""")
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_nyfed_rate_backfill_builds_v1(
       build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
       source_code_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
       source_rates BIGINT NOT NULL,new_source_versions BIGINT NOT NULL,
       raw_reference_records BIGINT NOT NULL,new_reference_records BIGINT NOT NULL,
       daily_rate_deltas BIGINT NOT NULL,independently_verified_vintages BIGINT NOT NULL,
       institutional_rate_shocks_released BIGINT NOT NULL,release_state VARCHAR NOT NULL
    )""")

def main():
    sha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or os.getenv("LAB_ALLOW_NYFED_RATES_RESEARCH")!="true"
        or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha)):
        raise RuntimeError("Require internal scoped source opt-in and pinned Git commit")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    scriptsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    received=datetime.now(timezone.utc)
    sources=[download(*x) for x in SOURCES]
    rows=[(date_,kind,rate,volume,revised,jsonhash,url)
          for _,url,jsonhash,_,_,data in sources
          for date_,kind,rate,volume,revised in data]
    con=duckdb.connect(f"md:{DB}?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        setup(con)
        with tempfile.NamedTemporaryFile("w",suffix=".csv",newline="",delete=False,encoding="utf-8") as f:
            filepath=f.name
            w=csv.writer(f)
            w.writerow(("day","sid","percent_rate","volume","revision","sha","source_url"))
            w.writerows(rows)
        try:
            con.execute("CREATE TEMP TABLE tmp_nyfed_source AS "
                        "SELECT * FROM read_csv(?,header=true,auto_detect=true)",[filepath])
        finally:
            os.unlink(filepath)
        n=con.execute("SELECT COUNT(*) FROM tmp_nyfed_source").fetchone()[0]
        if n!=len(rows):raise RuntimeError("Rate records corrupt in CSV staging")
        new_sources=0
        for sid,url,jsonsha,_,_,_ in sources:
            new_sources+=int(not con.execute(f"""
              SELECT COUNT(*) FROM {P}lab_nyfed_rate_source_vintages_v1
              WHERE source_rate_id=? AND json_sha256=?
            """,[sid,jsonsha]).fetchone()[0])
        new_rows=con.execute(f"""
        SELECT COUNT(*) FROM tmp_nyfed_source s
        WHERE NOT EXISTS (
           SELECT 1 FROM {P}lab_nyfed_rate_observations_retro_v1 p
           WHERE p.series_id=s.sid AND p.effective_date=CAST(s.day AS DATE)
           AND p.source_json_sha256=s.sha)
        """).fetchone()[0]
        con.execute("BEGIN TRANSACTION")
        try:
            for sid,url,jhash,nbytes,http_last,data in sources:
                con.execute(f"""
                 INSERT INTO {P}lab_nyfed_rate_source_vintages_v1
                 SELECT 'NYFED',?,?,?,?,?,?,?,FALSE,FALSE
                 WHERE NOT EXISTS (
                    SELECT 1 FROM {P}lab_nyfed_rate_source_vintages_v1
                    WHERE source_rate_id=? AND json_sha256=?)
                """,[sid,url,jhash,nbytes,http_last,received,build,sid,jhash])
            con.execute(f"""
              INSERT INTO {P}lab_nyfed_rate_observations_retro_v1
              SELECT 'NYFED',s.sid,CAST(s.day AS DATE),CAST(s.percent_rate AS DOUBLE),
                 TRY_CAST(s.volume AS DOUBLE),s.revision,s.source_url,s.sha,
                 CAST(? AS TIMESTAMPTZ),NULL,FALSE,FALSE,FALSE,FALSE,TRUE,?
              FROM tmp_nyfed_source s WHERE NOT EXISTS (
                SELECT 1 FROM {P}lab_nyfed_rate_observations_retro_v1 p
                WHERE p.series_id=s.sid AND p.effective_date=CAST(s.day AS DATE)
                  AND p.source_json_sha256=s.sha)
            """,[received,build])
            con.execute(f"""
              CREATE OR REPLACE TEMP TABLE tmp_nyfed_changes AS
              WITH ranked AS (
                SELECT *,
                  ROW_NUMBER() OVER (PARTITION BY series_id,effective_date
                    ORDER BY source_response_received_at DESC,source_json_sha256 DESC) rn
                FROM {P}lab_nyfed_rate_observations_retro_v1
              ), latest AS (
                SELECT * EXCLUDE(rn) FROM ranked WHERE rn=1
              ), t AS (
                SELECT *,LAG(effective_date) OVER(
                  PARTITION BY series_id ORDER BY effective_date) prev_date,
                  LAG(annual_rate_percent) OVER(
                  PARTITION BY series_id ORDER BY effective_date) prev_rate
                FROM latest
              )
              SELECT * FROM t WHERE prev_date IS NOT NULL
                AND date_diff('day',prev_date,effective_date) BETWEEN 1 AND 7
              """)
            n_changes=con.execute("SELECT COUNT(*) FROM tmp_nyfed_changes").fetchone()[0]
            con.execute(f"""
               INSERT INTO {P}lab_nyfed_daily_rate_deltas_retro_v1
               SELECT ?,series_id,effective_date,prev_date,
                 annual_rate_percent,prev_rate,
                 100.0*(annual_rate_percent-prev_rate),
                 source_json_sha256,FALSE,FALSE,FALSE
               FROM tmp_nyfed_changes
            """,[build])
            con.execute(f"""
               INSERT INTO {P}lab_nyfed_rate_backfill_builds_v1
               VALUES (?,?,?,current_timestamp,?,?,?,?,?,0,0,
                    'NYFED_OFFICIAL_REFERENCE_LEVEL_RESEARCH_NOT_PIT_OR_LICENSED')
            """,[build,sha,scriptsha,len(sources),new_sources,n,new_rows,n_changes])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build}")
        print(f"SOURCES={len(sources)} NEW_SOURCE_VERSIONS={new_sources}")
        print(f"RAW_NYFED_ROWS={n} NEW_RATE_VERSIONS={new_rows}")
        print(f"DESCRIPTIVE_RATE_DELTAS={n_changes}")
        for sid,url,jhash,nbytes,http_last,values in sources:
            print(f"SOURCE={sid} SHA256={jhash} COUNT={len(values)} FIRST={values[0][0]} LAST={values[-1][0]}")
        print("ORIGINAL_PUBLICATION_AT_VERIFIED=FALSE")
        print("SOURCE_RIGHTS_AND_POLICY_SURPRISE_APPROVAL=BLOCKED")
    finally:
        con.close()

if __name__=="__main__":
    main()
