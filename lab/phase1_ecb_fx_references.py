#!/usr/bin/env python3
"""ECB daily EUR-base FX reference-rate vintage snapshots (research-only).

Rates are QUOTE currency units per 1 EUR. Daily returns equal
10,000*ln(quote_per_eur_t / quote_per_eur_previous): quote-currency
depreciation against EUR is POSITIVE, not an investable trading return.
ECB rates are INFORMATION ONLY, not transaction or hedge execution prices.
A 2026 retrieval does NOT certify each historical 16:00 CET publication.
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
import requests
import duckdb

DB="eventrisk_factor_lab"
P=DB+".main."
VERSION="phase1-ecb-eur-reference-fx-v1.0.0"
ECB_BASE="https://data-api.ecb.europa.eu/service/data/EXR/"
CURRENCIES=("USD","JPY","GBP","CHF","CAD","AUD","CNY")
START="2005-01-01"
MAX_BYTES=10_000_000


def parse_ecb_csv(raw:bytes,currency:str):
    """Required SDMX dimensions and semantic orientation; skip null OBS_VALUE."""
    if not (0<len(raw)<MAX_BYTES):
        raise ValueError("Unexpected official FX data size")
    rawtext=raw.decode("utf-8-sig")
    rows=csv.DictReader(io.StringIO(rawtext))
    expected={"TIME_PERIOD","OBS_VALUE","FREQ","CURRENCY","CURRENCY_DENOM",
              "EXR_TYPE","EXR_SUFFIX"}
    if not rows.fieldnames or not expected.issubset(set(rows.fieldnames)):
        raise ValueError(f"Missing ECB SDMX dimensions: {rows.fieldnames}")
    parsed=[]
    seen=set()
    last=None
    for rec in rows:
        if not rec.get("TIME_PERIOD"):continue
        if (rec["FREQ"].strip()!="D"
            or rec["CURRENCY"].strip()!=currency
            or rec["CURRENCY_DENOM"].strip()!="EUR"
            or rec["EXR_TYPE"].strip()!="SP00"
            or rec["EXR_SUFFIX"].strip()!="A"):
            raise ValueError("Incorrect ECB FX currency pair orientation or reference type")
        at=date.fromisoformat(rec["TIME_PERIOD"])
        if at>datetime.now(timezone.utc).date() or at<date(1999,1,1):
            raise ValueError("Implausible source observation date")
        if at in seen or (last is not None and at<=last):
            raise ValueError("Duplicated or unordered official FX observation")
        seen.add(at);last=at
        val=rec["OBS_VALUE"].strip() if rec.get("OBS_VALUE") else ""
        if not val or val in {".","NaN"}:continue
        rate=float(val)
        if not math.isfinite(rate) or rate<=0 or rate>=1_000_000:
            raise ValueError("Invalid reference rate")
        parsed.append((at.isoformat(),currency,rate,rec.get("OBS_STATUS") or ""))
    if len(parsed)<250 or parsed[-1][0] < "2024-01-01":
        raise ValueError("Not a credible daily FX historical source")
    return parsed


def fetch_ecb(currency):
    url=f"{ECB_BASE}D.{currency}.EUR.SP00.A"
    response=requests.get(url,params={"format":"csvdata","startPeriod":START},
        timeout=(12,65),headers={"Accept":"text/csv","User-Agent":"EventRiskFactor-Lab-Research/1.0"})
    response.raise_for_status()
    if len(response.content)>MAX_BYTES:raise ValueError("Oversized ECB response")
    data=parse_ecb_csv(response.content,currency)
    return (currency,url,response.content,
            response.headers.get("Last-Modified"),data)


def ensure_schema(con):
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_fx_source_snapshots_v1(
       source VARCHAR NOT NULL,series_key VARCHAR NOT NULL,
       source_url VARCHAR NOT NULL,source_csv_sha256 VARCHAR NOT NULL,
       byte_size BIGINT NOT NULL,http_last_modified VARCHAR,
       first_warehouse_retrieved_at TIMESTAMPTZ NOT NULL,
       first_build_id VARCHAR NOT NULL,
       provider_individual_publication_time_certified BOOLEAN NOT NULL,
       permitted_tradable_benchmark BOOLEAN NOT NULL,
       independent_reuse_rights_approved BOOLEAN NOT NULL)
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_fx_reference_rates_retro_v1(
      provider VARCHAR NOT NULL,frequency VARCHAR NOT NULL,
      base_currency VARCHAR NOT NULL,quote_currency VARCHAR NOT NULL,
      observed_date DATE NOT NULL,reference_rate DOUBLE NOT NULL,
      unit VARCHAR NOT NULL,source_obs_status VARCHAR,
      original_source_series_key VARCHAR NOT NULL,
      source_csv_sha256 VARCHAR NOT NULL,source_url VARCHAR NOT NULL,
      source_retrieved_at TIMESTAMPTZ NOT NULL,
      original_provider_publication_at TIMESTAMPTZ,
      provider_publish_time_independently_verified BOOLEAN NOT NULL,
      rights_for_risk_redistribution_verified BOOLEAN NOT NULL,
      is_executable_spot_fx_quote BOOLEAN NOT NULL,
      historical_point_in_time_verified BOOLEAN NOT NULL,
      research_only BOOLEAN NOT NULL,first_build_id VARCHAR NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_fx_returns_retro_v1(
      build_id VARCHAR NOT NULL,provider VARCHAR NOT NULL,
      base_currency VARCHAR NOT NULL,quote_currency VARCHAR NOT NULL,
      observed_date DATE NOT NULL,previous_date DATE NOT NULL,
      reference_rate DOUBLE NOT NULL,previous_rate DOUBLE NOT NULL,
      quote_per_eur_log_change_bps DOUBLE NOT NULL,
      calendar_gap_days INTEGER NOT NULL,
      current_version_sha256 VARCHAR NOT NULL,
      source_snapshot_retrieved_at TIMESTAMPTZ NOT NULL,
      historical_original_publication_verified BOOLEAN NOT NULL,
      executable_fx_return BOOLEAN NOT NULL,
      approved_for_institutional_use BOOLEAN NOT NULL
    )""")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {P}lab_fx_backfill_builds_v1(
      build_id VARCHAR NOT NULL,source_git_sha VARCHAR NOT NULL,
      source_script_sha256 VARCHAR NOT NULL,built_at TIMESTAMPTZ NOT NULL,
      retrieved_series BIGINT NOT NULL,new_archive_versions BIGINT NOT NULL,
      parsed_reference_rows BIGINT NOT NULL,new_reference_versions BIGINT NOT NULL,
      daily_return_rows BIGINT NOT NULL,currencies BIGINT NOT NULL,
      original_source_publish_times_verified BIGINT NOT NULL,
      source_rights_approved BOOLEAN NOT NULL,release_state VARCHAR NOT NULL
    )""")


def main():
    gitsha=os.getenv("LAB_PIPELINE_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only"
        or os.getenv("LAB_ALLOW_ECB_INFORMATIONAL_DATA")!="true"
        or len(gitsha)!=40 or any(c not in "0123456789abcdef" for c in gitsha)):
        raise RuntimeError("Internal-only, approved fetch opt-in and pinned full Git SHA required")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    codehash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    sources=[fetch_ecb(c) for c in CURRENCIES]
    time_loaded=datetime.now(timezone.utc)
    staged=[]
    for curr,url,raw,_,records in sources:
        sha=hashlib.sha256(raw).hexdigest()
        staged.extend((day,c,rate,status,sha,url) for day,c,rate,status in records)
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        ensure_schema(con)
        with tempfile.NamedTemporaryFile("w",newline="",suffix=".csv",encoding="utf-8",delete=False) as f:
            filename=f.name
            writer=csv.writer(f)
            writer.writerow(("day","ccy","val","status","sha","source_url"))
            writer.writerows(staged)
        try:
            con.execute("CREATE TEMP TABLE p1_ebc_input AS "
                "SELECT * FROM read_csv(?,header=true,auto_detect=true)",[filename])
        finally:
            os.unlink(filename)
        if con.execute("SELECT COUNT(*) FROM p1_ebc_input").fetchone()[0]!=len(staged):
            raise ValueError("CSV staging cardinality mismatch")
        new_rows=con.execute(f"""
            SELECT COUNT(*) FROM p1_ebc_input s
            WHERE NOT EXISTS (
              SELECT 1 FROM {P}lab_fx_reference_rates_retro_v1 f
              WHERE f.quote_currency=s.ccy AND f.observed_date=CAST(s.day AS DATE)
                AND f.source_csv_sha256=s.sha
            )
        """).fetchone()[0]
        new_archives=0
        for curr,url,raw,_,_ in sources:
            srcsha=hashlib.sha256(raw).hexdigest()
            new_archives+=int(not con.execute(f"""
                SELECT COUNT(*) FROM {P}lab_fx_source_snapshots_v1
                WHERE series_key=? AND source_csv_sha256=?
            """,[f"D.{curr}.EUR.SP00.A",srcsha]).fetchone()[0])
        # Treat "latest downloaded version" as RETROSPECTIVE ONLY. Do not
        # mutate previously stored versions or backdate provider publications.
        con.execute(f"""
        CREATE TEMP TABLE p1_ebc_daily AS
        WITH latest AS (
          SELECT quote_currency,observed_date,reference_rate,
            source_csv_sha256,source_retrieved_at,
            ROW_NUMBER() OVER (PARTITION BY quote_currency,observed_date
              ORDER BY source_retrieved_at DESC,source_csv_sha256 DESC) rn
          FROM {P}lab_fx_reference_rates_retro_v1
        )
        SELECT * EXCLUDE(rn) FROM latest WHERE rn=1
        """)
        # Calculate after appending with exact source hashes; new input is
        # not yet in the permanent table.
        con.execute("BEGIN TRANSACTION")
        try:
            for curr,url,raw,lastmod,_ in sources:
                sha=hashlib.sha256(raw).hexdigest()
                con.execute(f"""
                 INSERT INTO {P}lab_fx_source_snapshots_v1
                 SELECT 'ECB',?,?,?,?,?,?,?,FALSE,FALSE,FALSE
                 WHERE NOT EXISTS (
                   SELECT 1 FROM {P}lab_fx_source_snapshots_v1
                   WHERE series_key=? AND source_csv_sha256=?
                 )
                """,[f"D.{curr}.EUR.SP00.A",url,sha,len(raw),lastmod,
                     time_loaded,build,f"D.{curr}.EUR.SP00.A",sha])
            con.execute(f"""
              INSERT INTO {P}lab_fx_reference_rates_retro_v1
              SELECT 'ECB','D','EUR',s.ccy,CAST(s.day AS DATE),
                     CAST(s.val AS DOUBLE),'quote_currency_units_per_one_EUR',
                     s.status,'D.'||s.ccy||'.EUR.SP00.A',s.sha,s.source_url,
                     CAST(? AS TIMESTAMPTZ),NULL,FALSE,FALSE,FALSE,FALSE,TRUE,?
              FROM p1_ebc_input s
              WHERE NOT EXISTS (
                SELECT 1 FROM {P}lab_fx_reference_rates_retro_v1 f
                WHERE f.quote_currency=s.ccy
                  AND f.observed_date=CAST(s.day AS DATE)
                  AND f.source_csv_sha256=s.sha
              )
            """,[time_loaded,build])
            con.execute(f"""
              CREATE OR REPLACE TEMP TABLE p1_current_daily AS
              WITH latest AS (
                SELECT quote_currency,observed_date,reference_rate,
                  source_csv_sha256,source_retrieved_at,
                  ROW_NUMBER() OVER(PARTITION BY quote_currency,observed_date
                     ORDER BY source_retrieved_at DESC,source_csv_sha256 DESC) rn
                FROM {P}lab_fx_reference_rates_retro_v1
              ), picked AS (
                SELECT * EXCLUDE(rn) FROM latest WHERE rn=1
              ), lags AS (
                SELECT *,LAG(observed_date) OVER(
                  PARTITION BY quote_currency ORDER BY observed_date) prev_day,
                  LAG(reference_rate) OVER(
                  PARTITION BY quote_currency ORDER BY observed_date) prev_rate
                FROM picked
              )
              SELECT * FROM lags
              WHERE prev_rate>0 AND date_diff('day',prev_day,observed_date)
                BETWEEN 1 AND 7
              """)
            n_returns=con.execute("SELECT COUNT(*) FROM p1_current_daily").fetchone()[0]
            con.execute(f"""
              INSERT INTO {P}lab_fx_returns_retro_v1
              SELECT ?,'ECB','EUR',quote_currency,observed_date,prev_day,
                reference_rate,prev_rate,10000.0*LN(reference_rate/prev_rate),
                CAST(date_diff('day',prev_day,observed_date) AS INTEGER),
                source_csv_sha256,source_retrieved_at,FALSE,FALSE,FALSE
              FROM p1_current_daily
            """,[build])
            con.execute(f"""
              INSERT INTO {P}lab_fx_backfill_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,?,?,0,FALSE,
                 'ECB_INFORMATIONAL_REFERENCE_ONLY_UNVERIFIED_PIT_LICENSE_AND_TRADABILITY')
            """,[build,gitsha,codehash,len(sources),new_archives,
                 len(staged),new_rows,n_returns,len(CURRENCIES)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print("BUILD_ID="+build)
    print("ECB_FX_REFERENCE_PAIRS="+str(len(CURRENCIES)))
    print("SOURCE_ROWS="+str(len(staged)))
    print("NEW_VERSIONED_ROWS="+str(new_rows)+" NEW_SNAPSHOTS="+str(new_archives))
    print("BACKFILLED_FX_RETURN_ROWS="+str(n_returns))
    print("ORIGINAL_PROVIDER_PUBLICATION_PIT_VERIFIED=FALSE")
    print("FX_EXECUTABLE_QUOTE=FALSE; EXTERNAL_RISK_RELEASE=BLOCKED")


if __name__=="__main__":
    main()
