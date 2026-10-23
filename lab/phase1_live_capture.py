#!/usr/bin/env python3
"""Prospective, independently timestamped public-market capture.

New data ONLY. Never relabel backfilled snapshots or historical estimates as
point-in-time observations. This is a bounded, internal-research collector;
Gamma/Kalshi public metadata may be delayed versus executable order books.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DB = "eventrisk_factor_lab"
P = f"{DB}.main."
VERSION = "phase1-capture-v1.0.0"
KALSHI = "https://external-api.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
MAX_PAGES = 3
MAX_QUOTES = 3000
HEADERS = {"User-Agent": "EventRisk-InternalResearch/1.0"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return utcnow().isoformat(timespec="microseconds")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def finite_probability(value: Any) -> float | None:
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    if v != v or not 0 <= v <= 1:
        return None
    return v


def source_number(value: Any) -> float | None:
    try:
        v = float(value)
        return v if v == v and abs(v) < 1e14 else None
    except (ValueError, TypeError):
        return None


def safe_yes_quote(bid: Any, ask: Any, last: Any) -> tuple[float | None, float | None, float | None, float | None, str]:
    b, a, l = map(finite_probability, (bid, ask, last))
    if b is not None and a is not None and a >= b:
        return (b + a) / 2, b, a, l, "indicative_bid_ask_midpoint"
    if l is not None:
        return l, b, a, l, "reported_last_trade_price"
    return None, b, a, l, "no_valid_yes_price"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=2, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",), respect_retry_after_header=True
    )))
    return session


def fetch_page(session: requests.Session, url: str, params: dict[str, Any]) -> tuple[Any, str, str]:
    response = session.get(url, params=params, timeout=(8, 30))
    response.raise_for_status()
    received_at = timestamp()  # after receiving bytes, never exchange quote timestamp
    response_sha = hashlib.sha256(response.content).hexdigest()
    return response.json(), received_at, response_sha


def make_market(venue: str, market_id: str, event_id: str, title: str,
                question: str, status: str, record: dict, contract: dict,
                received_at: str, page_sha: str, source_url: str, run_id: str,
                bid: Any, ask: Any, last: Any) -> dict | None:
    price, bid, ask, last, basis = safe_yes_quote(bid, ask, last)
    if price is None:
        return None
    return {
        "run_id": run_id, "venue": venue, "market_id": market_id,
        "event_id": event_id, "event_title": title[:1024],
        "question": question[:2048], "status": status[:60],
        "capture_received_at": received_at,
        "provider_quote_at": None,
        "yes_bid": bid, "yes_ask": ask, "last_price": last,
        "yes_probability": price, "quote_basis": basis,
        "contract_sha256": stable_hash(contract),
        "source_record_sha256": stable_hash(record),
        "source_response_sha256": page_sha,
        "source_url": source_url,
        "capture_time_verified": True,
        "provider_quote_freshness_verified": False,
        "historical_point_in_time_released": False,
        "data_use_class": "internal_research_only",
        "contract_json": json.dumps(contract, sort_keys=True, default=str)
    }


def collect_polymarket(session, run_id):
    result, seen = [], set()
    for tag in ("geopolitics", "politics"):
        # Gamma's documented event filter is numeric tag_id, not tag_slug.
        # Resolve each taxonomy slug at capture time to avoid hardcoded IDs.
        tag_payload, _, _ = fetch_page(session, GAMMA + "/tags/slug/" + tag, {})
        tag_id = tag_payload.get("id") if isinstance(tag_payload, dict) else None
        if not tag_id or not str(tag_id).isdigit():
            raise RuntimeError("Gamma tag lookup returned no numeric tag id")
        for offset in range(0, MAX_PAGES*100, 100):
            url = GAMMA + "/events"
            payload, at, digest = fetch_page(session, url, {
                "tag_id": int(tag_id), "active": "true", "closed": "false",
                "limit": 100, "offset": offset
            })
            if not isinstance(payload, list):
                raise RuntimeError("Gamma API did not return an events list")
            for event in payload:
                for market in event.get("markets") or []:
                    mid = str(market.get("id") or "")
                    if not mid or mid in seen:
                        continue
                    seen.add(mid)
                    contract = {
                        "venue": "polymarket",
                        "event_id": str(event.get("id") or ""),
                        "question": market.get("question"),
                        "description": market.get("description"),
                        "condition_id": market.get("conditionId"),
                        "outcomes": market.get("outcomes"),
                        "clob_token_ids": market.get("clobTokenIds"),
                        "end_date": market.get("endDate"),
                        "slug": market.get("slug")
                    }
                    quote = make_market(
                        "polymarket", mid, str(event.get("id") or ""),
                        str(event.get("title") or ""), str(market.get("question") or ""),
                        "active" if market.get("active") else "inactive",
                        market, contract, at, digest, url, run_id,
                        market.get("bestBid"), market.get("bestAsk"),
                        market.get("lastTradePrice")
                    )
                    if quote is not None:
                        result.append(quote)
                        if len(result) >= MAX_QUOTES:
                            return result
            if len(payload) < 100:
                break
    return result


def collect_kalshi(session, run_id):
    result, cursor, seen = [], None, set()
    for _ in range(MAX_PAGES):
        url = KALSHI + "/events"
        params = {"status": "open", "with_nested_markets": "true", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        payload, at, digest = fetch_page(session, url, params)
        if not isinstance(payload, dict):
            raise RuntimeError("Kalshi API did not return an events envelope")
        for event in payload.get("events") or []:
            if str(event.get("category") or "").lower() not in {
                "world", "politics", "economics", "financials", "climate"
            }:
                continue
            for market in event.get("markets") or []:
                mid = str(market.get("ticker") or "")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                contract = {
                    "venue": "kalshi",
                    "event_ticker": event.get("event_ticker"),
                    "series_ticker": event.get("series_ticker"),
                    "title": market.get("title"),
                    "subtitle": market.get("yes_sub_title"),
                    "rules_primary": market.get("rules_primary"),
                    "rules_secondary": market.get("rules_secondary"),
                    "expiration_time": market.get("expiration_time"),
                    "close_time": market.get("close_time")
                }
                quote = make_market(
                    "kalshi", mid, str(event.get("event_ticker") or ""),
                    str(event.get("title") or ""), str(market.get("title") or ""),
                    str(market.get("status") or "open"), market, contract,
                    at, digest, url, run_id,
                    market.get("yes_bid_dollars"), market.get("yes_ask_dollars"),
                    market.get("last_price_dollars")
                )
                if quote is not None:
                    result.append(quote)
                    if len(result) >= MAX_QUOTES:
                        return result
        cursor = payload.get("cursor")
        if not cursor:
            break
    return result


def ensure_schema(con):
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_live_market_captures_v1 (
        run_id VARCHAR NOT NULL,
        venue VARCHAR NOT NULL,
        market_id VARCHAR NOT NULL,
        event_id VARCHAR,
        event_title VARCHAR,
        question VARCHAR,
        status VARCHAR,
        capture_received_at TIMESTAMPTZ NOT NULL,
        provider_quote_at TIMESTAMPTZ,
        yes_bid DOUBLE,
        yes_ask DOUBLE,
        last_price DOUBLE,
        yes_probability DOUBLE NOT NULL,
        quote_basis VARCHAR NOT NULL,
        contract_sha256 VARCHAR NOT NULL,
        source_record_sha256 VARCHAR NOT NULL,
        source_response_sha256 VARCHAR NOT NULL,
        source_url VARCHAR NOT NULL,
        capture_time_verified BOOLEAN NOT NULL,
        provider_quote_freshness_verified BOOLEAN NOT NULL,
        historical_point_in_time_released BOOLEAN NOT NULL,
        data_use_class VARCHAR NOT NULL,
        contract_json JSON
      )""")
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_live_market_contract_versions_v1 (
        venue VARCHAR NOT NULL,
        market_id VARCHAR NOT NULL,
        contract_sha256 VARCHAR NOT NULL,
        first_captured_at TIMESTAMPTZ NOT NULL,
        first_run_id VARCHAR NOT NULL,
        contract_json JSON NOT NULL
      )""")
    con.execute(f"""
      CREATE TABLE IF NOT EXISTS {P}lab_live_capture_runs_v1 (
        run_id VARCHAR NOT NULL,
        source_version VARCHAR NOT NULL,
        source_commit VARCHAR NOT NULL,
        source_script_sha256 VARCHAR NOT NULL,
        started_at TIMESTAMPTZ NOT NULL,
        finished_at TIMESTAMPTZ NOT NULL,
        venue_results JSON NOT NULL,
        captured_markets BIGINT NOT NULL,
        status VARCHAR NOT NULL,
        data_use_class VARCHAR NOT NULL
      )""")


def upload_captures(con, records, run_id, start, completed, stats, commit, script_sha):
    with tempfile.TemporaryDirectory(prefix="eventrisk_capture_") as directory:
        path = str(Path(directory)/"captures.ndjson")
        with open(path, "w", encoding="utf-8") as output:
            for r in records:
                output.write(json.dumps(r, separators=(",", ":")) + "\n")
        # Data written via a temp file and a single vectorized SQL load,
        # not thousands of cross-network INSERT calls.
        con.execute("BEGIN TRANSACTION")
        try:
            if records:
                con.execute(f"""
                CREATE OR REPLACE TEMP TABLE new_captures AS
                  SELECT
                    run_id::VARCHAR AS run_id,
                    venue::VARCHAR AS venue,
                    market_id::VARCHAR AS market_id,
                    event_id::VARCHAR AS event_id,
                    event_title::VARCHAR AS event_title,
                    question::VARCHAR AS question,
                    status::VARCHAR AS status,
                    capture_received_at::TIMESTAMPTZ AS capture_received_at,
                    CAST(NULL AS TIMESTAMPTZ) AS provider_quote_at,
                    yes_bid::DOUBLE AS yes_bid,
                    yes_ask::DOUBLE AS yes_ask,
                    last_price::DOUBLE AS last_price,
                    yes_probability::DOUBLE AS yes_probability,
                    quote_basis::VARCHAR AS quote_basis,
                    contract_sha256::VARCHAR AS contract_sha256,
                    source_record_sha256::VARCHAR AS source_record_sha256,
                    source_response_sha256::VARCHAR AS source_response_sha256,
                    source_url::VARCHAR AS source_url,
                    TRUE AS capture_time_verified,
                    FALSE AS provider_quote_freshness_verified,
                    FALSE AS historical_point_in_time_released,
                    data_use_class::VARCHAR AS data_use_class,
                    contract_json::JSON AS contract_json
                  FROM read_json_auto('{path}', format='newline_delimited',
                                      maximum_object_size=1048576)
                """)
                con.execute(f"""
                  INSERT INTO {P}lab_live_market_captures_v1
                  SELECT * FROM new_captures
                """)
                con.execute(f"""
                  INSERT INTO {P}lab_live_market_contract_versions_v1
                  SELECT c.venue,c.market_id,c.contract_sha256,
                         min(c.capture_received_at),arg_min(c.run_id,c.capture_received_at),
                         arg_min(c.contract_json,c.capture_received_at)
                  FROM new_captures c
                  WHERE NOT EXISTS (
                    SELECT 1 FROM {P}lab_live_market_contract_versions_v1 v
                    WHERE v.venue=c.venue AND v.market_id=c.market_id
                      AND v.contract_sha256=c.contract_sha256
                  )
                  GROUP BY c.venue,c.market_id,c.contract_sha256
                """)
            state="OK" if all(x["state"]=="ok" for x in stats.values()) else "PARTIAL"
            con.execute(f"""
               INSERT INTO {P}lab_live_capture_runs_v1
               VALUES (?, ?, ?, ?, ?, ?, ?::JSON, ?, ?, 'internal_research_only')
            """, (run_id, VERSION,commit,script_sha,start,completed,
                  json.dumps(stats,sort_keys=True),len(records),state))
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise


def main():
    if os.getenv("LAB_RESEARCH_SCOPE") != "internal-only":
        raise RuntimeError("Internal research scope is mandatory")
    commit = os.getenv("LAB_PIPELINE_COMMIT","")
    if len(commit)!=40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("Immutable full source commit is mandatory")
    started=timestamp()
    run_id=uuid.uuid4().hex
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    session=make_session()
    stats, records={},[]
    for name,fn in (("polymarket",collect_polymarket),("kalshi",collect_kalshi)):
        try:
            captured=fn(session,run_id)
            records.extend(captured)
            stats[name]={"state":"ok","captured":len(captured)}
        except Exception as exc:
            stats[name]={"state":"error","captured":0,"error_class":type(exc).__name__}
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                stats[name]["http_status"] = int(exc.response.status_code)
                from urllib.parse import urlparse
                stats[name]["failed_path"] = urlparse(exc.response.url).path
            print(f"SOURCE_ERROR={name}:{type(exc).__name__}:HTTP_{stats[name].get('http_status', 'unknown')}")
    completed=timestamp()
    if not records:
        # Do not fabricate a successful run or insert empty market data.
        raise RuntimeError("No valid public event-market quotes; aborting write")
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        ensure_schema(con)
        upload_captures(con,records,run_id,started,completed,stats,commit,script_sha)
    print(f"CAPTURE_RUN={run_id}")
    print(f"CAPTURED_ROWS={len(records)}")
    print("SOURCE_STATUS="+json.dumps(stats,sort_keys=True))
    print("PIT_CLAIM=CAPTURE_TIMESTAMP_ONLY; QUOTE_FRESHNESS_UNVERIFIED")
    print("HISTORICAL_POINT_IN_TIME_RELEASED=FALSE")


if __name__=="__main__":
    main()
