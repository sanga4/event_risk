#!/usr/bin/env python3
"""Backfill U.S. French daily research factors, source-versioned and UNLICENSED FOR SERVING.

Pull the official *daily* 5-factor and momentum archives over HTTPS, validate
headers/date granularity/units/sentinels, and append content-addressed source
versions. Factor values are decimal simple DAILY returns (not percentages,
annualized returns, market security total returns or Treasury yield changes).

No claim that a historical date was available as-of that date: today's archive
may have revised old values. Neither original-publication PIT, corporate
action revision history nor commercial redistribution rights are verified.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import io
import math
import os
from pathlib import Path
import tempfile
import zipfile
import requests
import duckdb

DB="eventrisk_factor_lab"
P=f"{DB}.main."
VERSION="phase1-french-daily-factors-v1.0.0"
BASE="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
SOURCES=(
    ("FF5_US_DAILY","F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
     ("Mkt-RF","SMB","HML","RMW","CMA","RF")),
    ("MOM_US_DAILY","F-F_Momentum_Factor_daily_CSV.zip",("Mom",)),
)
IDS={
    "Mkt-RF":"FF_US_MKT_RF","SMB":"FF_US_SMB","HML":"FF_US_HML",
    "RMW":"FF_US_RMW","CMA":"FF_US_CMA","RF":"FF_US_RF",
    "Mom":"FF_US_MOM"
}
MAX_ARCHIVE_BYTES=15_000_000


def parse_daily_archive(blob:bytes,required:tuple[str,...]):
    """Return (date, factor_id, decimal_return, native_percent) rows.

    Only the first contiguous block of YYYYMMDD observations after an exact
    expected CSV column header. No accidental monthly YYYYMM ingestion.
    """
    if len(blob)>MAX_ARCHIVE_BYTES:
        raise ValueError("Archive too large")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        infos=[i for i in z.infolist() if i.filename.lower().endswith(".csv")
               and not i.is_dir()]
        if len(infos)!=1 or infos[0].file_size>20_000_000:
            raise ValueError("Expected one bounded source CSV member")
        raw=z.read(infos[0])
    reader=csv.reader(io.StringIO(raw.decode("utf-8-sig",errors="replace")))
    found_header=False
    seen_daily=False
    last=None
    dates=set()
    parsed=[]
    norm=lambda v:v.strip().replace(" ","").upper()
    wanted=[norm(x) for x in required]
    for row in reader:
        if not row:continue
        cleaned=[norm(x) for x in row]
        if not found_header:
            if len(cleaned)>=len(wanted)+1 and cleaned[1:len(wanted)+1]==wanted:
                found_header=True
            continue
        token=row[0].strip()
        if not (len(token)==8 and token.isascii() and token.isdigit()):
            if seen_daily:break
            continue
        when=date(int(token[:4]),int(token[4:6]),int(token[6:]))
        if when>datetime.now(timezone.utc).date():
            raise ValueError("Future-dated factor source row")
        if last is not None and when<=last:
            raise ValueError("Source dates not strictly increasing")
        last=when
        seen_daily=True
        if len(row)<len(wanted)+1:
            raise ValueError("Incomplete daily factor row")
        dates.add(when)
        for idx,key in enumerate(required,1):
            text=row[idx].strip()
            if not text or text==".":
                continue
            try:
                pct=float(text)
            except ValueError:
                raise ValueError("Unexpected nonnumerical factor row")
            if not math.isfinite(pct) or pct in (-99.,-99.99,-999.,-999.99):
                continue
            # This is a sanity check for the daily table, not winsorization.
            if abs(pct)>99:
                raise ValueError("Implausible non-sentinel daily factor return")
            parsed.append((when.isoformat(),IDS[key],pct/100.,pct))
    if not found_header or len(dates)<1000 or max(dates)<date(2024,1,1):
        raise ValueError("Missing expected header or insufficient DAILY coverage")
    return parsed, len(dates), min(dates), max(dates)


def download_source(filename):
    url=BASE+filename
    r=requests.get(url,timeout=(15,60),headers={
        "User-Agent":"Mozilla/5.0 (compatible; EventRiskFactorResearch/1.0)",
        "Accept":"application/zip,application/octet-stream,*/*",
    })
    r.raise_for_status()
    blob=r.content
    if len(blob)>MAX_ARCHIVE_BYTES or len(blob)<100:
        raise ValueError("Invalid source archive size")
    return url,blob,r.headers.get("Last-Modified")


def ensure_schema(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_style_factor_source_archives_v1 (
       provider VARCHAR NOT NULL,source_dataset VARCHAR NOT NULL,
       source_url VARCHAR NOT NULL,source_zip_sha256 VARCHAR NOT NULL,
       bytes_downloaded BIGINT NOT NULL,source_last_modified_http VARCHAR,
       first_retrieved_at TIMESTAMPTZ NOT NULL,
       historical_publication_vintage_verified BOOLEAN NOT NULL,
       internal_research_use_only BOOLEAN NOT NULL,
       redistribution_rights_verified BOOLEAN NOT NULL,
       first_build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_style_factor_returns_v1 (
       provider VARCHAR NOT NULL,region VARCHAR NOT NULL,
       factor_id VARCHAR NOT NULL,observed_date DATE NOT NULL,
       factor_return DOUBLE NOT NULL,unit VARCHAR NOT NULL,
       currency VARCHAR NOT NULL,benchmark VARCHAR NOT NULL,
       portfolio_construction_id VARCHAR NOT NULL,
       vintage_date DATE NOT NULL,downloaded_at TIMESTAMPTZ NOT NULL,
       source_dataset VARCHAR NOT NULL,source_zip_sha256 VARCHAR NOT NULL,
       source_url VARCHAR NOT NULL,source_value_percent DOUBLE NOT NULL,
       source_publication_time_independently_verified BOOLEAN NOT NULL,
       historical_point_in_time_verified BOOLEAN NOT NULL,
       licensed_for_distribution BOOLEAN NOT NULL,
       approved_for_institutional_risk_use BOOLEAN NOT NULL,
       research_status VARCHAR NOT NULL,first_build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_style_factor_ingest_builds_v1 (
       build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
       source_script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
       provider_archives_checked BIGINT NOT NULL,
       archives_new BIGINT NOT NULL,rows_downloaded BIGINT NOT NULL,
       rows_appended BIGINT NOT NULL,distinct_style_series BIGINT NOT NULL,
       oldest_factor_date DATE,newest_factor_date DATE,
       bad_or_duplicate_source_days BIGINT NOT NULL,
       source_publication_vintages_verified BIGINT NOT NULL,
       production_risk_factors_approved BIGINT NOT NULL,
       release_state VARCHAR NOT NULL
    )""")


def main():
    commit=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError("Research-only scope and pinned 40-char Git SHA required")
    if os.getenv("LAB_ALLOW_FRENCH_INTERNAL_RESEARCH")!="true":
        raise RuntimeError("Explicit internal research source-download opt-in required")
    source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    built_at=datetime.now(timezone.utc)
    build_id=VERSION+"-"+built_at.strftime("%Y%m%dT%H%M%S%fZ")
    sources=[]
    factor_rows=[]
    for label,filename,expected in SOURCES:
        url,blob,http_last=download_source(filename)
        rows,days,dmin,dmax=parse_daily_archive(blob,expected)
        archive_sha=hashlib.sha256(blob).hexdigest()
        sources.append((label,url,archive_sha,len(blob),http_last,days,dmin,dmax))
        factor_rows.extend((label,archive_sha,url,*row) for row in rows)
    if len({(r[0],r[3],r[4]) for r in factor_rows})!=len(factor_rows):
        raise ValueError("Duplicate file/factor/date keys")
    if len({r[4] for r in factor_rows})!=7:
        raise ValueError("Seven independent source factor labels required")
    con=duckdb.connect(f"md:{DB}?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    tmpname=None
    try:
        ensure_schema(con)
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",newline="",suffix=".csv",delete=False) as t:
            tmpname=t.name
            writer=csv.writer(t)
            writer.writerow(("source_dataset","source_zip_sha256","source_url","observed_date",
                             "factor_id","factor_return","source_value_percent"))
            writer.writerows(factor_rows)
        con.execute("CREATE TEMP TABLE p1_style_stage AS "
                    "SELECT * FROM read_csv(?,header=true,auto_detect=true)",[tmpname])
        staged=con.execute("SELECT count(*) FROM p1_style_stage").fetchone()[0]
        if staged!=len(factor_rows):
            raise RuntimeError("Source CSV staging count mismatch")
        num_new=con.execute(f"""
           SELECT count(*) FROM p1_style_stage s
           WHERE NOT EXISTS (
             SELECT 1 FROM {P}lab_style_factor_returns_v1 t
             WHERE t.factor_id=s.factor_id AND t.observed_date=s.observed_date
               AND t.source_zip_sha256=s.source_zip_sha256
           )
        """).fetchone()[0]
        new_archives=sum(con.execute(f"""
           SELECT count(*) FROM {P}lab_style_factor_source_archives_v1
           WHERE source_dataset=? AND source_zip_sha256=?
        """,[label,sha]).fetchone()[0]==0 for label,_,sha,*_ in sources)
        con.execute("BEGIN TRANSACTION")
        try:
            for label,url,sha,nbytes,http_last,_,_,_ in sources:
                con.execute(f"""
                  INSERT INTO {P}lab_style_factor_source_archives_v1
                  SELECT 'KENNETH_FRENCH_DATA_LIBRARY',?,?,?,?,?,
                    FALSE,TRUE,FALSE,?
                  WHERE NOT EXISTS(
                    SELECT 1 FROM {P}lab_style_factor_source_archives_v1
                    WHERE source_dataset=? AND source_zip_sha256=?
                  )
                """,[label,url,sha,nbytes,http_last,built_at,build_id,label,sha])
            con.execute(f"""
             INSERT INTO {P}lab_style_factor_returns_v1
             SELECT
                'KENNETH_FRENCH_DATA_LIBRARY', 'US',s.factor_id,
                CAST(s.observed_date AS DATE), CAST(s.factor_return AS DOUBLE),
                'daily_simple_return_decimal','USD',
                CASE WHEN s.factor_id='FF_US_RF' THEN 'research_daily_risk_free_rate'
                     WHEN s.factor_id='FF_US_MKT_RF' THEN 'market_excess_return'
                     ELSE 'long_short_research_portfolio' END,
                'KEN_FRENCH_RESEARCH_US_CIZ_HISTORY_REVISED',
                CAST(? AS DATE), CAST(? AS TIMESTAMPTZ),
                s.source_dataset,s.source_zip_sha256,s.source_url,
                CAST(s.source_value_percent AS DOUBLE),
                FALSE,FALSE,FALSE,FALSE,
                'EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED',?
             FROM p1_style_stage s
             WHERE NOT EXISTS(
               SELECT 1 FROM {P}lab_style_factor_returns_v1 t
               WHERE t.factor_id=s.factor_id AND t.observed_date=CAST(s.observed_date AS DATE)
                 AND t.source_zip_sha256=s.source_zip_sha256
             )
            """,[built_at.date(),built_at,build_id])
            con.execute(f"""
             INSERT INTO {P}lab_style_factor_ingest_builds_v1
             VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,?,0,0,0,
                     'INTERNAL_RESEARCH_ONLY_NO_HISTORICAL_SOURCE_VINTAGE_OR_DISTRIBUTION_RIGHTS')
            """,[build_id,commit,source_sha,len(sources),new_archives,
                 staged,num_new,7,min(x[6] for x in sources),max(x[7] for x in sources)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print("BUILD_ID="+build_id)
        print("ARCHIVES="+str(len(sources))+" NEW_ARCHIVES="+str(new_archives))
        print("SOURCE_DAILY_ROWS="+str(staged)+" NEW_VERSIONED_ROWS="+str(num_new))
        print("FACTORS=FF_US_MKT_RF,FF_US_SMB,FF_US_HML,FF_US_RMW,FF_US_CMA,FF_US_RF,FF_US_MOM")
        for label,url,sha,bytes_,_,days,start,end in sources:
            print(f"SOURCE={label} SHA256={sha} BYTES={bytes_} DATES={days} FIRST={start} LAST={end}")
        print("INDEPENDENT_HISTORICAL_VINTAGES_VERIFIED=0")
        print("REDISTRIBUTION_RIGHTS_VERIFIED=FALSE; PRODUCTION_RELEASE=BLOCKED")
    finally:
        con.close()
        if tmpname and os.path.exists(tmpname):
            os.unlink(tmpname)


if __name__=="__main__":
    main()
