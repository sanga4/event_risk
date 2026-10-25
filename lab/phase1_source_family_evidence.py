#!/usr/bin/env python3
"""Institutional source-family availability and provenance-gap evidence matrix.

This is a measured snapshot of warehouse SOURCE COUNTS, NOT a legal or PIT
certification. Never manufacture original-published-at or release approval.
Absent vendor datasets are zero/NOT_LOADED rather than synthetic observations.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime,timezone
from pathlib import Path
import hashlib,os
import duckdb

DB="eventrisk_factor_lab";P=DB+".main."
VERSION="phase1-source-gap-matrix-v1.0.0"

@dataclass(frozen=True)
class Spec:
    domain:str
    table:str
    date_col:str
    frequency:str
    usage:str
    next_evidence:str
    received_col:str|None=None

SOURCES=(
 Spec("venue_prospective_receipts","lab_live_market_captures_v1","capture_received_at","on_demand","FORWARD_RECEIPT_ONLY","Original venue quote timestamps/terms and scheduled capture","capture_received_at"),
 Spec("historical_market_snapshots","market_snapshots","ts","mixed_retrospective","RETROSPECTIVE_ONLY","Original source provider publication and first-local-capture history"),
 Spec("usd_security_prices","security_prices","date","daily","RETROSPECTIVE_ADJUSTED","Licensed original security IDs, split/dividend vintages, delisted universe","fetched_at"),
 Spec("treasury_par_yields","lab_factor_observations","observed_date","daily","RETROSPECTIVE_RATES","Historical original provider publication/revisions and source rights"),
 Spec("us_equity_style_factors","lab_style_factor_returns_v1","observed_date","daily","RETROSPECTIVE_STYLE","Ken French/CRSP usage rights, historical source snapshots as-known","downloaded_at"),
 Spec("ecb_eur_fx_reference","lab_fx_reference_rates_retro_v1","observed_date","daily","INFORMATION_ONLY_NOT_TRADABLE","Exact source release/vintages, source reuse and executable prices separately","source_retrieved_at"),
 Spec("nyfed_sofr_effr_reference","lab_nyfed_rate_observations_retro_v1","effective_date","daily","ANNUALIZED_RATE_LEVELS_ONLY","Original publication/revisions, NYFed reuse rights, identified policy surprises","source_response_received_at"),
 Spec("fred_macro_economic","lab_fred_native_observations_v1","observed_date","mixed_daily_weekly_monthly","NOT_LOADED_FRED_SOURCE_TIMEOUT","Accessible official FRED API, vintage histories, native release calendars","warehouse_fetched_at"),
 Spec("security_corporate_actions","lab_security_corporate_actions_v1","effective_date","event_time","NOT_LOADED","Issuer master, delist history, first-published split/dividend and adjustment versions"),
 Spec("independent_tradeable_fx","lab_tradeable_fx_quotes_v1","quote_at","intraday","NOT_LOADED","Broker/venue licensed executable bid/ask times, currency pair/terms"),
 Spec("licensed_credit_spreads","lab_licensed_credit_spreads_v1","observed_date","daily","NOT_LOADED_RESTRICTED","Vendor ICE/credit rights and point-in-time OAS/index levels"),
 Spec("commodities_futures_rolls","lab_commodity_futures_v1","observed_date","daily","NOT_LOADED","Original futures contract/exchange and roll/corporate data"),
 Spec("options_volatility","lab_options_volatility_v1","observed_date","daily_intraday","NOT_LOADED","Licensed option strikes/expiry/liquidity and VIX source construction"),
 Spec("portfolio_positions","lab_portfolio_positions_v1","asof_at","portfolio_asof","NOT_LOADED","Authorized holdings, asset IDs, currencies, owner approval"),
 Spec("macro_release_consensus","lab_macro_release_surprises_v1","source_published_at","event_intraday","NOT_LOADED","Timestamped pre-release consensus, original first-print and amendments"),
 Spec("event_evidence_archive","lab_evidence","","event_publication","CANDIDATE_ONLY","Attributable original evidence, first publication, license and independent reviewer"),
)


def validate_snapshot_span(n:int,first:date|None,last:date|None,today:date):
    """Source *observation day* coverage, not original quote published-at PIT."""
    if n<=0 or first is None or last is None or first>last or last>today or first<date(2000,1,1):
        raise ValueError("Historical market snapshot observation-date coverage invalid")
    return (last-first).days+1


def main():
    gitsha=os.getenv("LAB_PIPELINE_COMMIT","")
    if os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or len(gitsha)!=40 or any(x not in "0123456789abcdef" for x in gitsha):
        raise RuntimeError("internal-only source snapshot requires immutable Git SHA")
    build=VERSION+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    con=duckdb.connect(f"md:{DB}?attach_mode=single")
    con.execute("SET TimeZone='UTC'")
    try:
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_source_family_evidence_v1 (
          build_id VARCHAR NOT NULL,
          domain VARCHAR NOT NULL,
          source_table VARCHAR NOT NULL,
          source_table_exists BOOLEAN NOT NULL,
          source_row_count BIGINT NOT NULL,
          first_observed_date DATE,
          latest_observed_date DATE,
          last_local_retrieved_at TIMESTAMPTZ,
          expected_frequency VARCHAR NOT NULL,
          research_semantics VARCHAR NOT NULL,
          next_required_evidence VARCHAR NOT NULL,
          provider_original_publication_verified BOOLEAN NOT NULL,
          commercial_reuse_approved BOOLEAN NOT NULL,
          institutional_factor_model_approved BOOLEAN NOT NULL,
          diagnostic_only BOOLEAN NOT NULL
        )""")
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {P}lab_source_family_evidence_builds_v1 (
          build_id VARCHAR NOT NULL,git_sha VARCHAR NOT NULL,
          code_sha256 VARCHAR NOT NULL,created_at TIMESTAMPTZ NOT NULL,
          expected_domains BIGINT NOT NULL,loaded_domains BIGINT NOT NULL,
          missing_domains BIGINT NOT NULL,loaded_source_observations BIGINT NOT NULL,
          independent_original_pit_certified_domains BIGINT NOT NULL,
          independent_rights_certified_domains BIGINT NOT NULL,
          risk_production_released BOOLEAN NOT NULL
        )""")
        available={x[0] for x in con.execute("""
         SELECT table_name FROM information_schema.tables
         WHERE table_catalog='eventrisk_factor_lab'
           AND table_schema='main'
        """).fetchall()}
        cols={}
        for name in available:
            if name in {s.table for s in SOURCES}:
                cols[name]={x[0] for x in con.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_catalog='eventrisk_factor_lab'
                  AND table_schema='main' AND table_name=?
                """,[name]).fetchall()}
        out=[]
        for s in SOURCES:
            exists=s.table in available
            first=last=retrieved=None
            count=0
            if exists:
                # Only static whitelisted source identifiers from this code are interpolated.
                count=con.execute(f"SELECT count(*) FROM {P}{s.table}").fetchone()[0]
                if count>0 and s.date_col and s.date_col in cols[s.table]:
                    first,last=con.execute(
                      f"SELECT MIN(CAST({s.date_col} AS DATE)),"
                      f"MAX(CAST({s.date_col} AS DATE)) FROM {P}{s.table}"
                    ).fetchone()
                if s.domain=="historical_market_snapshots" and count>0:
                    # Source event timestamps support a descriptive calendar span.
                    # NEVER label these as provider first-publication clocks.
                    validate_snapshot_span(count,first,last,datetime.now(timezone.utc).date())
                if count>0 and s.received_col and s.received_col in cols[s.table]:
                    retrieved=con.execute(
                      f"SELECT MAX({s.received_col}) FROM {P}{s.table}"
                    ).fetchone()[0]
            out.append((build,s.domain,s.table,exists,count,first,last,retrieved,
               s.frequency,s.usage,s.next_evidence,False,False,False,True))
        nloaded=sum(z[4]>0 for z in out)
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany(
              f"INSERT INTO {P}lab_source_family_evidence_v1 VALUES ({','.join(['?']*15)})",out)
            con.execute(f"""
              INSERT INTO {P}lab_source_family_evidence_builds_v1
              VALUES (?,?,?,current_timestamp,?,?,?,?,0,0,FALSE)
            """,[build,gitsha,checksum,len(SOURCES),nloaded,len(SOURCES)-nloaded,
                 sum(z[4] for z in out)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        print(f"BUILD_ID={build} DOMAINS={len(SOURCES)} LOADED={nloaded} NOT_LOADED={len(SOURCES)-nloaded}")
        for z in out:
            print(f"DOMAIN={z[1]} LOADED_RECORDS={z[4]} LATEST_OBSERVED={z[6]} PIT_VERIFIED=FALSE RIGHTS_APPROVED=FALSE")
        print("PRODUCTION_RELEASE_APPROVED=FALSE")
    finally:
        con.close()


if __name__=="__main__":
    main()
