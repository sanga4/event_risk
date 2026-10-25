#!/usr/bin/env python3
"""Official FRED observation-date level snapshots across funding/macro/conditions.

An authenticated official FRED API response is a current/revised observation
snapshot and DOES NOT establish first-publication clocks, original ALFRED
revision timing or identified announcement surprises. No institutional release.
"""
from __future__ import annotations
import csv
import json
from datetime import date,datetime,timezone
import hashlib
import io
import math
import os
from pathlib import Path
import tempfile
import requests
import duckdb

DB="eventrisk_factor_lab"
P=f"{DB}.main."
VERSION="phase1-fred-cross-domain-raw-v1.1.0"
BASE="https://api.stlouisfed.org/fred/series/observations"
# (series_id,frequency,source_native_unit,descriptive_transform)
SERIES=(
 ("DFF","daily","annualized_percent_rate","rate_level_change_basis_points"),
 ("SOFR","daily","annualized_percent_rate","rate_level_change_basis_points"),
 ("NFCI","weekly","financial_conditions_index","native_index_point_change"),
 ("CPIAUCSL","monthly","cpi_seasonally_adjusted_index","trailing_12_month_pct"),
 ("UNRATE","monthly","unemployment_percent","unemployment_rate_pp_change"),
 ("WALCL","weekly","fed_total_assets_million_usd","weekly_log_change_bps"),
)
MAX_BYTES=8_000_000


def read_fred(blob:bytes,series_id:str,frequency:str):
    if not 50<len(blob)<MAX_BYTES:raise ValueError("Wrong FRED CSV response size")
    reader=csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
    if not reader.fieldnames or (
        "observation_date" not in reader.fieldnames or series_id not in reader.fieldnames
    ):
        raise ValueError(f"Wrong FRED source header for {series_id}: {reader.fieldnames}")
    points=[]
    last=None
    for row in reader:
        ds=(row.get("observation_date") or "").strip()
        if not ds:continue
        day=date.fromisoformat(ds)
        if day>datetime.now(timezone.utc).date() or day<date(1900,1,1):
            raise ValueError("Bad source observation date")
        if last is not None and day<=last:
            raise ValueError("Nonascending or duplicate provider observations")
        last=day
        value=(row.get(series_id) or "").strip()
        if not value or value==".":
            continue
        x=float(value)
        if not math.isfinite(x):raise ValueError("Nonfinite numeric source value")
        if series_id in ("DFF","SOFR","UNRATE") and not -5<x<100:
            raise ValueError("Implausible native percent unit")
        if series_id in ("CPIAUCSL","WALCL") and x<=0:
            raise ValueError("Invalid positive level series")
        points.append((day.isoformat(),x))
    if len(points)<250 or points[-1][0] < "2024-01-01":
        raise ValueError("Official source lacks expected modern history")
    return points


def fred_api_key():
    """Require a legitimate user-provisioned secret; never log or persist it."""
    value=os.getenv("api_secret_FRED_API_KEY") or os.getenv("FRED_API_KEY","")
    if len(value)!=32 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789" for c in value):
        raise RuntimeError("FRED_API_KEY_REQUIRED_FROM_SECRET_STORE")
    return value


def read_fred_api(blob:bytes,series_id:str,frequency:str):
    """Convert bounded official JSON to the existing strictly validated units."""
    if not 50<len(blob)<MAX_BYTES:
        raise ValueError("Unexpected FRED API response size")
    try:
        document=json.loads(blob)
    except (ValueError,UnicodeError):
        raise ValueError("Invalid FRED API response JSON") from None
    observations=document.get("observations") if isinstance(document,dict) else None
    if not isinstance(observations,list) or len(observations)>20000:
        raise ValueError("Invalid FRED response observation collection")
    buffer=io.StringIO()
    writer=csv.writer(buffer)
    writer.writerow(("observation_date",series_id))
    for item in observations:
        if not isinstance(item,dict):
            raise ValueError("Malformed FRED observation")
        start,end=item.get("realtime_start"),item.get("realtime_end")
        if not isinstance(start,str) or not isinstance(end,str):
            raise ValueError("FRED realtime vintage metadata absent")
        try:
            if date.fromisoformat(start)>date.fromisoformat(end):
                raise ValueError("Reversed FRED realtime metadata")
        except (TypeError,ValueError):
            raise ValueError("Invalid FRED realtime metadata") from None
        # Realtime *dates* are NOT original publication clock timestamps.
        writer.writerow((item.get("date"),item.get("value")))
    return read_fred(buffer.getvalue().encode("utf-8"),series_id,frequency)


def download(series_id,frequency,unit,transform):
    secret=fred_api_key()
    # The legacy schema's source_csv_* names are historic field names; this
    # provider payload is JSON and its SHA covers the original response bytes.
    params={"series_id":series_id,"api_key":secret,"file_type":"json",
            "observation_start":"1990-01-01"}
    try:
        response=requests.get(BASE,params=params,timeout=(10,25),
            headers={"User-Agent":"EventRiskFactor-InternalResearch/1.1",
                     "Accept":"application/json"})
    except requests.RequestException as exc:
        # Exception messages and response URLs may contain the API key.
        raise RuntimeError("FRED_PROVIDER_REQUEST_FAILED:"+type(exc).__name__) from None
    if response.status_code!=200:
        raise RuntimeError("FRED_PROVIDER_HTTP_"+str(response.status_code))
    points=read_fred_api(response.content,series_id,frequency)
    sha=hashlib.sha256(response.content).hexdigest()
    # Never store/log response.url or requests' URL with api_key.
    redacted_url=(BASE+"?series_id="+series_id+
                  "&file_type=json&observation_start=1990-01-01")
    return (series_id,frequency,unit,transform,redacted_url,sha,
            response.headers.get("Last-Modified"),len(response.content),points)


def derived(series_id:str,points:list[tuple[str,float]],method:str):
    """Descriptive transformations only; historical source vintage unverified."""
    result=[]
    for k,(ds,val) in enumerate(points):
        if method=="trailing_12_month_pct":
            if k<12:continue
            past_date,past=points[k-12]
            dt=date.fromisoformat(ds)
            pd=date.fromisoformat(past_date)
            months=(dt.year-pd.year)*12+dt.month-pd.month
            if months!=12 or past<=0:continue
            desc=(val/past-1)*100
            unit="year_over_year_percent_change_not_release_surprise"
        else:
            if k==0:continue
            past_date,past=points[k-1]
            dday=(date.fromisoformat(ds)-date.fromisoformat(past_date)).days
            if (method=="rate_level_change_basis_points" and dday>10) or (
              method in ("native_index_point_change","weekly_log_change_bps") and dday>21
            ) or (method=="unemployment_rate_pp_change" and dday>70):
                continue
            if method=="rate_level_change_basis_points":
                desc=100*(val-past);unit="rate_change_bps_not_surprise"
            elif method=="native_index_point_change":
                desc=val-past;unit="index_points_change_not_factor_return"
            elif method=="unemployment_rate_pp_change":
                desc=val-past;unit="unemployment_percentage_points_change_not_surprise"
            elif method=="weekly_log_change_bps":
                if past<=0:continue
                desc=10000*math.log(val/past)
                unit="federal_assets_weekly_log_change_bps"
            else:raise ValueError("Unknown transform")
        if math.isfinite(desc):
            result.append((ds,past_date,desc,unit))
    return result


def setup(con):
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_fred_source_snapshots_v1(
       provider VARCHAR NOT NULL,series_id VARCHAR NOT NULL,
       frequency VARCHAR NOT NULL,source_native_unit VARCHAR NOT NULL,
       source_csv_url VARCHAR NOT NULL,source_csv_sha256 VARCHAR NOT NULL,
       source_bytes BIGINT NOT NULL,http_last_modified VARCHAR,
       first_warehouse_fetched_at TIMESTAMPTZ NOT NULL,
       build_id VARCHAR NOT NULL,original_publication_vintages_verified BOOLEAN NOT NULL,
       licensed_for_institutional_reuse BOOLEAN NOT NULL)
    """)
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_fred_native_observations_v1(
        provider VARCHAR NOT NULL,series_id VARCHAR NOT NULL,
        observed_date DATE NOT NULL,native_level DOUBLE NOT NULL,
        native_unit VARCHAR NOT NULL,frequency VARCHAR NOT NULL,
        source_csv_sha256 VARCHAR NOT NULL,source_url VARCHAR NOT NULL,
        warehouse_fetched_at TIMESTAMPTZ NOT NULL,
        source_original_publication_at TIMESTAMPTZ,
        source_realtime_vintage_start DATE,
        source_realtime_vintage_end DATE,
        original_historical_pit_verified BOOLEAN NOT NULL,
        rights_approved_for_distribution BOOLEAN NOT NULL,
        approved_for_risk_beta_use BOOLEAN NOT NULL,
        research_only BOOLEAN NOT NULL,first_build_id VARCHAR NOT NULL)
    """)
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_fred_descriptive_changes_v1(
        build_id VARCHAR NOT NULL,source_series_id VARCHAR NOT NULL,
        frequency VARCHAR NOT NULL,observation_date DATE NOT NULL,
        previous_observation_date DATE NOT NULL,
        descriptive_change_value DOUBLE NOT NULL,
        descriptive_change_unit VARCHAR NOT NULL,
        transformation_name VARCHAR NOT NULL,
        source_csv_sha256 VARCHAR NOT NULL,
        historical_publication_pit_verified BOOLEAN NOT NULL,
        source_rights_independently_approved BOOLEAN NOT NULL,
        is_identified_economic_surprise BOOLEAN NOT NULL,
        approved_for_institutional_risk_use BOOLEAN NOT NULL)
    """)
    con.execute(f"""
     CREATE TABLE IF NOT EXISTS {P}lab_fred_backfill_builds_v1(
       build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
       source_script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
       downloaded_series BIGINT NOT NULL,new_file_versions BIGINT NOT NULL,
       parsed_native_rows BIGINT NOT NULL,inserted_native_versions BIGINT NOT NULL,
       descriptive_change_rows BIGINT NOT NULL,
       original_release_vintages_verified BIGINT NOT NULL,
       approved_institutional_macro_surprises BIGINT NOT NULL,
       release_status VARCHAR NOT NULL)
    """)


def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or os.getenv("LAB_ALLOW_FRED_RESEARCH")!="true"
        or len(commit)!=40 or any(ch not in "0123456789abcdef" for ch in commit)):
        raise RuntimeError("Internal research opt-in + pinned 40-char Git SHA required")
    fred_api_key()  # Fail before external requests or any warehouse changes.
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    scriptsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source=[download(*spec) for spec in SERIES]
    now=datetime.now(timezone.utc)
    rawrows=[]
    drows=[]
    for series_id,freq,unit,transform,url,sha,header,nbytes,points in source:
        rawrows.extend((series_id,ds,val,unit,freq,sha,url) for ds,val in points)
        drows.extend((series_id,freq,ds,prev,x,changeunit,transform,sha)
                     for ds,prev,x,changeunit in derived(series_id,points,transform))
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        setup(con)
        def load_csv(rows,fields,tablename):
            with tempfile.NamedTemporaryFile("w",encoding="utf-8",newline="",suffix=".csv",delete=False) as tmp:
                filepath=tmp.name
                w=csv.writer(tmp);w.writerow(fields);w.writerows(rows)
            try:
                con.execute(f"CREATE TEMP TABLE {tablename} AS "
                            "SELECT * FROM read_csv(?,header=true,auto_detect=true)",[filepath])
            finally:
                os.unlink(filepath)
            if con.execute(f"SELECT COUNT(*) FROM {tablename}").fetchone()[0]!=len(rows):
                raise RuntimeError("Staged rows mismatched source counts")
        load_csv(rawrows,("series_id","ds","native","native_unit","frequency","sha","url"),"p1_fred_native_stage")
        load_csv(drows,("series_id","freq","ds","prev","change","unit","method","sha"),"p1_fred_change_stage")
        new_archives=sum(not con.execute(f"""
          SELECT COUNT(*) FROM {P}lab_fred_source_snapshots_v1
          WHERE series_id=? AND source_csv_sha256=?
        """,[s[0],s[5]]).fetchone()[0] for s in source)
        new_rows=con.execute(f"""
          SELECT COUNT(*) FROM p1_fred_native_stage s WHERE NOT EXISTS(
            SELECT 1 FROM {P}lab_fred_native_observations_v1 f
            WHERE f.series_id=s.series_id AND f.observed_date=CAST(s.ds AS DATE)
              AND f.source_csv_sha256=s.sha
          )
        """).fetchone()[0]
        con.execute("BEGIN TRANSACTION")
        try:
            for series_id,freq,unit,transform,url,sha,lastmodified,nbytes,points in source:
                con.execute(f"""
                 INSERT INTO {P}lab_fred_source_snapshots_v1
                 SELECT 'FRED',?,?,?,?,?,?,?,?,?,FALSE,FALSE
                 WHERE NOT EXISTS (SELECT 1 FROM {P}lab_fred_source_snapshots_v1
                   WHERE series_id=? AND source_csv_sha256=?)
                """,[series_id,freq,unit,url,sha,nbytes,lastmodified,now,build,series_id,sha])
            con.execute(f"""
              INSERT INTO {P}lab_fred_native_observations_v1
              SELECT 'FRED',s.series_id,CAST(s.ds AS DATE),
                CAST(s.native AS DOUBLE),s.native_unit,s.frequency,
                s.sha,s.url,CAST(? AS TIMESTAMPTZ),NULL,NULL,NULL,
                FALSE,FALSE,FALSE,TRUE,?
              FROM p1_fred_native_stage s
              WHERE NOT EXISTS(
                SELECT 1 FROM {P}lab_fred_native_observations_v1 f
                WHERE f.series_id=s.series_id AND f.observed_date=CAST(s.ds AS DATE)
                  AND f.source_csv_sha256=s.sha
              )
            """,[now,build])
            con.execute(f"""
              INSERT INTO {P}lab_fred_descriptive_changes_v1
              SELECT ?,s.series_id,
                (SELECT MIN(native.frequency) FROM p1_fred_native_stage native
                   WHERE native.series_id=s.series_id),
                CAST(s.ds AS DATE),CAST(s.prev AS DATE),
                CAST(s.change AS DOUBLE),s.unit,s.method,s.sha,
                FALSE,FALSE,FALSE,FALSE
              FROM p1_fred_change_stage s
            """,[build])
            con.execute(f"""
              INSERT INTO {P}lab_fred_backfill_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,0,0,
                'REVISED_OBSERVATIONS_UNVERIFIED_RELEASE_VINTAGES_AND_VENDOR_RIGHTS')
            """,[build,commit,scriptsha,len(source),new_archives,
                 len(rawrows),new_rows,len(drows)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print("BUILD_ID="+build)
    print(f"SOURCE_SERIES={len(source)} RAW_ROWS={len(rawrows)} NEW_ROWS={new_rows}")
    print(f"NEW_SOURCE_FILE_VERSIONS={new_archives}")
    print(f"DESCRIPTIVE_TRANSFORMED_ROWS={len(drows)}")
    for series_id,freq,unit,transform,url,sha,_,_,points in source:
        print(f"SERIES={series_id} FREQ={freq} FROM={points[0][0]} TO={points[-1][0]} ROWS={len(points)} SHA256={sha}")
    print("IDENTIFIED_MACRO_RELEASE_SURPRISES=0")
    print("ORIGINAL_PROVIDER_RELEASE_TIMES_VERIFIED=FALSE; INSTITUTIONAL_USE=BLOCKED")


if __name__=="__main__":
    main()
