#!/usr/bin/env python3
"""EventRisk Preview MVP: an independent, read-only analyst research gateway.

Public: source-repository securities/factor definitions and clearly illustrative
transmission graph. Authenticated+licensed: live, scoped MotherDuck SELECTs.
No direct DB calls from browsers. No institution/PIT/beta approval implied.
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import csv
import hmac
import json
import os
import re
import threading
import time
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import warehouse
from pathways import graph_paths
from factor_universe import factor_proposals
DATA = ROOT / "data"
MOTHERDUCK_DB = "eventrisk_factor_lab"
REFRESH_TTL_SECONDS = 300
SESSION_LOCK = threading.RLock()
DB_CONNECTION = {"conn": None, "last_success_utc": None}
LIVE_COVERAGE = {"as_of_utc": None, "checked_monotonic": 0.0, "metrics": None, "error": None}
COVERAGE_LOCK = threading.Lock()
COVERAGE_CACHE_SECONDS = 900
RATE_LOCK = threading.Lock()
RATE_BY_SESSION = defaultdict(deque)
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS_PER_WINDOW = 90
JSON_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY"}
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".png": "image/png",
                 ".xml":"application/xml; charset=utf-8"}
FILES = {"/": "viewer.html", "/previous-explorer": "marco.html",
         "/lab": "lab.html", "/api": "api.html",
         "/legacy-lab": "lab.html", "/data": "data.html",
         "/assets/styles.css": "assets/styles.css", "/assets/app.js": "assets/app.js",
         "/assets/mvp.css": "assets/mvp.css", "/assets/marco.css": "assets/marco.css",
         "/assets/marco.js": "assets/marco.js",
         "/assets/viewer.css": "assets/viewer.css",
         "/assets/viewer.js": "assets/viewer.js",
         "/assets/live-coverage.js": "assets/live-coverage.js",
         "/assets/attribution-core.js":"assets/attribution-core.js",
         "/assets/lab.css": "assets/lab.css",
         "/assets/lab.js": "assets/lab.js",
         "/assets/data.css":"assets/data.css", "/assets/data.js":"assets/data.js",
         "/excel/taskpane.html":"excel/taskpane.html",
         "/excel/taskpane.js":"excel/taskpane.js",
         "/excel/live-coverage.js":"excel/live-coverage.js",
         "/excel/taskpane.css":"excel/taskpane.css",
         "/excel/manifest.xml":"excel/manifest.xml"}
FACTOR_CATALOG_VERSION = "2026-10-20.1"
SCHEMA = "EVENTRISK_RESEARCH_PRODUCT_V1"
CHANNELS = [
    ("inflation", "Inflation and price expectations", ("inflation", "rates", "commodity")),
    ("growth", "Real economic growth", ("country", "equity_style", "industry")),
    ("policy", "Central-bank policy and forward rates", ("rates", "fx")),
    ("treasury", "Treasury term structure and duration", ("rates",)),
    ("credit", "Credit spreads and default expectations", ("credit",)),
    ("funding", "Funding liquidity and money-market basis", ("liquidity", "credit")),
    ("risk_appetite", "Risk appetite and equity discounting", ("equity_style", "volatility")),
    ("supply", "Supply chains and industrial production", ("industry", "commodity")),
    ("trade", "Trade tariffs and border costs", ("country", "fx")),
    ("fx", "Foreign exchange translation and hedging", ("fx",)),
    ("earnings", "Corporate revenues and earnings", ("equity_style", "industry")),
    ("energy", "Energy prices and supply", ("commodity", "inflation")),
    ("agriculture", "Agricultural commodity inputs", ("commodity", "inflation")),
    ("labor", "Employment and wage pressures", ("inflation", "country")),
    ("housing", "Housing credit and financing", ("rates", "credit")),
    ("fiscal", "Government spending and borrowing", ("rates", "country")),
    ("regulation", "Regulatory costs and market access", ("industry", "country")),
    ("volatility", "Market uncertainty and volatility", ("volatility",)),
    ("liquidity", "Market depth and liquidity", ("liquidity",)),
    ("technology", "Technology and semiconductor capacity", ("industry",)),
    ("commodities", "Broad commodity input prices", ("commodity",)),
    ("cross_asset", "Cross-asset exposures and hedging", ("cross_asset_style",)),
]
EVENTS = [
    ("taiwan","Taiwan Strait disruption scenario",("supply","technology","risk_appetite"),"entity:Q865"),
    ("trade","Trade restrictions scenario",("trade","fx","regulation"),"entity:Q148"),
    ("inflation","Inflation release interpretation",("inflation","policy","treasury"),None),
    ("funding","Money-market funding stress",("funding","liquidity","credit"),None),
    ("oil","Global oil supply disruption",("energy","commodities","inflation"),None),
    ("chips","Semiconductor export controls",("technology","trade","supply"),"entity:Q2986369"),
    ("defense","Regional conflict escalation",("risk_appetite","fiscal","energy"),"entity:Q392933"),
    ("rates","Monetary policy repricing",("policy","treasury","housing"),None),
]
ALLOW_TYPES = {"question", "entity", "security", "factor", "proposition", "market"}
ALLOW_ROUTES = {
    "/api/v1/research/coverage", "/api/v1/research/events",
    "/api/v1/research/graph-nodes", "/api/v1/research/models",
    "/api/v1/research/factor-series", "/api/v1/research/factor-catalog",
    "/api/v1/research/graph-neighbors",
    "/api/v1/research/funding-diagnostics",
    "/api/v1/research/markets", "/api/v1/research/market-quote",
    "/api/v1/research/market-history",
    "/api/v1/research/datasets", "/api/v1/research/columns",
    "/api/v1/research/table",
}
ADMIN_ROUTES={"/api/v1/research/datasets",
              "/api/v1/research/columns", "/api/v1/research/table"}
TICKER_PATTERN = re.compile(r"^[A-Za-z0-9.=_-]{1,25}$")
FACTOR_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
def utc_now():
    return datetime.now(timezone.utc).isoformat()

def within_analyst_budget(session_key: str) -> bool:
    """Per-process beta rate budget; not a substitute for distributed rate limits."""
    now=time.monotonic()
    with RATE_LOCK:
        # All beta callers currently use one shared issued key. Replace with
        # per-user SSO subject identity before a multi-user public release.
        timestamps=RATE_BY_SESSION[session_key]
        while timestamps and now-timestamps[0] > RATE_WINDOW_SECONDS:
            timestamps.popleft()
        if len(timestamps) >= RATE_MAX_REQUESTS_PER_WINDOW:
            return False
        timestamps.append(now)
        return True


def analyst_key():
    """Accept the product key name, then the legacy isolated-beta alias."""
    return os.getenv("EVENTRISK_ANALYST_KEY") or os.getenv("PREVIEW_MVP_ANALYST_KEY","")

def bool_flag(name):
    canonical=name.replace("PREVIEW_MVP_","EVENTRISK_")
    return any(os.getenv(key,"").strip().lower()=="true"
               for key in {canonical,name})

def data():
    with (DATA / "factors.json").open(encoding="utf-8") as f:
        factors_doc = json.load(f)
    with (DATA / "securities.csv").open(encoding="utf-8", newline="") as f:
        securities = [{k: v for k, v in r.items() if k is not None} for r in csv.DictReader(f)
                      if (r.get("ticker") or "").strip() and not str(r.get("ticker")).startswith("#")]
    with (DATA / "exposures.csv").open(encoding="utf-8", newline="") as f:
        priors = [r for r in csv.DictReader(f) if (r.get("qid") or "").startswith("Q")
                  and r.get("ticker") and r.get("weight")]
    factors = factors_doc["factors"]
    return securities, factors, priors

def catalog():
    securities, factors, priors = data()
    return {"schema": SCHEMA, "as_of": utc_now(), "mode": "REPO_PUBLISHED_REFERENCE_CATALOG_NOT_LIVE_QUOTES",
            "factor_catalog_version": FACTOR_CATALOG_VERSION, "securities_count": len(securities),
            "factors_count": len(factors), "securities": [
                {"id": "security:"+r["ticker"], "ticker":r["ticker"], "name":r.get("name",""),
                 "country":r.get("country",""),"asset_class":r.get("asset_class",""),
                 "sector":r.get("sector",""), "role":r.get("role","")}
                for r in securities],
            "factors": [
                {"id":"factor:"+f["id"], "factor_id":f["id"], "name":f["name"],
                 "family":f.get("family",""),"definition":f.get("definition",""),
                 "reference":f.get("reference",""),
                 "historical_series_validated":False}
                for f in factors],
            "channels":[{"id":"channel:"+c,"name":name,"related_factor_families":list(fams),
                         "review_status":"ILLUSTRATIVE_NOT_CAUSAL"} for c,name,fams in CHANNELS]}

def public_graph():
    """A *catalog* graph; not a claim these pathways are measured coefficients."""
    securities, factors, priors = data()
    names = {r["ticker"]:r["name"] for r in securities}
    factor_ids = {f["id"] for f in factors}
    nodes, edges = [], []
    for r in securities:
        nodes.append({"id":"security:"+r["ticker"],"type":"security","name":r["name"],
                      "ticker":r["ticker"],"subtitle":r.get("country",""),
                      "description":r.get("sector",""),"review_status":"PUBLIC_REFERENCE_NOT_APPROVED"})
    for f in factors:
        nodes.append({"id":"factor:"+f["id"],"type":"factor","name":f["name"],
                      "subtitle":f.get("family",""),"description":f.get("definition",""),
                      "review_status":"CATALOG_DEFINITION_NOT_MEASURED_EXPOSURE"})
    for ch, name, families in CHANNELS:
        nodes.append({"id":"channel:"+ch, "type":"channel","name":name,
                      "description":"Illustrative economic transmission mechanism",
                      "review_status":"UNREVIEWED_HYPOTHESIS"})
    for event,name,channels,entity in EVENTS:
        nodes.append({"id":"event:"+event,"type":"event","name":name,
                      "description":"Hypothetical research scenario, not a verified observed event",
                      "review_status":"ILLUSTRATIVE_NOT_REAL_EVENT"})
        if entity:
            edges.append({"src":"event:"+event,"dst":entity,"type":"hypothetical_involves",
                          "review_status":"RESEARCH_ONLY_NOT_APPROVED"})
        for ch in channels:
            edges.append({"src":"event:"+event,"dst":"channel:"+ch,"type":"hypothetical_transmission",
                          "review_status":"RESEARCH_ONLY_NOT_APPROVED"})
    entities = {}
    for p in priors:
        try: w=float(p["weight"])
        except (TypeError,ValueError): continue
        ticker=p["ticker"]
        if not (0<w<=1) or ticker not in names:continue
        qid=p["qid"]
        entities[qid]=p.get("entity") or qid
        edges.append({"src":"entity:"+qid, "dst":"security:"+ticker,
                      "type":"research_exposure_prior","weight":w,
                      "summary":p.get("rationale",""),"review_status":"RESEARCH_ONLY_NOT_APPROVED"})
    for q,name in entities.items():
        nodes.append({"id":"entity:"+q,"type":"entity","name":name,
                      "review_status":"SOURCE_SEED_ANALYST_ENTITY"})
    byfamily=defaultdict(list)
    for f in factors:byfamily[f.get("family","")].append(f["id"])
    for ch, _, fams in CHANNELS:
        for f in factors:
            if f.get("family") in fams and f["id"] in factor_ids:
                edges.append({"src":"channel:"+ch,"dst":"factor:"+f["id"],
                              "type":"hypothetical_factor_channel",
                              "review_status":"RESEARCH_ONLY_NOT_APPROVED"})
    ids={n["id"] for n in nodes}
    edges=[e for e in edges if e["src"] in ids and e["dst"] in ids]
    return {"schema":SCHEMA, "mode":"PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE",
            "nodes":nodes,"edges":edges,"as_of":utc_now(),
            "source_reference":"Repo security and factor seed catalog, analyst exposure CSV",
            "disclaimer":"Do not treat connectivity, factor family, or seed prior as price beta, observed event, licensed market quote, causal effect or institutional approval."}

def _assert_read_query(sql):
    """Fail closed even when the installed MotherDuck PAT has write capability.

    DuckDB parses the exact statement; do not attempt to detect SQL structure
    using only a leading SELECT regex or accept browser-provided SQL text.
    SELECT on its own does not mean arbitrary side-effecting table functions
    are safe, so deny external readers, dynamic query helpers and token access.
    """
    import duckdb
    if not isinstance(sql, str) or len(sql)>25000:
        raise ValueError("ONLY_BOUNDED_READ_QUERIES_ALLOWED")
    parsed=duckdb.extract_statements(sql)
    if len(parsed)!=1 or parsed[0].type!=duckdb.StatementType.SELECT:
        raise ValueError("ONLY_SINGLE_SELECT_ALLOWED")
    if not re.match(r"^\s*(?:WITH|SELECT)\b", sql, flags=re.I):
        raise ValueError("ONLY_SINGLE_SELECT_ALLOWED")
    if re.search(
        r"\b(?:read_csv(?:_auto)?|read_parquet|read_json(?:_auto)?|"
        r"read_text|read_blob|sqlite_scan|postgres_scan|"
        r"query|query_table|query_data|getenv|current_setting|"
        r"external_file_cache|http_get|http_post|secret|pragma)\s*\(",
        sql, flags=re.I,
    ):
        raise ValueError("EXTERNAL_OR_DYNAMIC_QUERY_NOT_ALLOWED")
    return True


def _db_query(sql,params=()):
    """Execute only compiled, single SELECTs (app code, never user SQL).

    A standard MotherDuck PAT can authenticate a connection even on Lite;
    this application-layer guard limits API execution, but it does NOT turn
    the underlying write-capable credential into a read-only credential.
    """
    if not os.getenv("MOTHERDUCK_TOKEN"):
        raise RuntimeError("DATABASE_CREDENTIAL_NOT_CONFIGURED")
    _assert_read_query(sql)
    with SESSION_LOCK:
        import duckdb
        conn=DB_CONNECTION["conn"]
        if conn is None:
            conn=duckdb.connect("md:"+MOTHERDUCK_DB)
            conn.execute("SET TimeZone='UTC'")
            DB_CONNECTION["conn"]=conn
        try:
            cursor=conn.execute(sql,params)
            cols=[d[0] for d in cursor.description]
            rows=[dict(zip(cols,row)) for row in cursor.fetchall()]
            DB_CONNECTION["last_success_utc"]=utc_now()
            return rows
        except Exception:
            DB_CONNECTION["conn"]=None
            try:conn.close()
            except Exception:pass
            raise

def _int_arg(q,key,default,max_value):
    try: n=int(q.get(key,[default])[0])
    except (TypeError,ValueError,IndexError):raise ValueError("BAD_"+key.upper())
    if n<0 or n>max_value:raise ValueError("BAD_"+key.upper())
    return n

def _one(q,key,maximum=100):
    value=str(q.get(key,[""])[0])
    if len(value)>maximum:raise ValueError("BAD_"+key.upper())
    return value

def research(route,q,owner_private=False):
    # Owner-only internal inspection is distinct from public/source redistribution.
    # An issued data-admin credential AND analyst key are required in the HTTP layer.
    # This does not certify publisher rights, original PIT, or permission to resell.
    # Only fixed SELECT and parameterized WHEREs; no arbitrary SQL, no bulk extraction.
    if route not in ALLOW_ROUTES: raise ValueError("UNSUPPORTED_RESOURCE")
    if route in ADMIN_ROUTES:
        operation=route.rsplit("/",1)[1]
        return warehouse.explore(_db_query,operation,q,
            source_approved=bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
            derived_approved=bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"))
    if route=="/api/v1/research/coverage":
        rows=_db_query("""SELECT 'graph_question_nodes' AS metric,count(DISTINCT node_id) AS "value" FROM main.graph_nodes WHERE node_type='question'
 UNION ALL SELECT 'graph_security_nodes',count(DISTINCT node_id) FROM main.graph_nodes WHERE node_type='security'
 UNION ALL SELECT 'factor_catalog_rows',count(*) FROM main.lab_factor_catalog
 UNION ALL SELECT 'graph_edges_versioned_records',count(*) FROM main.graph_edges
 UNION ALL SELECT 'captured_market_latest',count(*) FROM main.lab_live_market_latest_v1
 UNION ALL SELECT 'funding_model_versions',count(*) FROM main.lab_joint_security_funding_models_v1""")
        return {"mode":"LIVE_DATABASE_COUNT_ONLY","generated_at_utc":utc_now(),
                "database":MOTHERDUCK_DB,"coverage":rows,
                "license_notice":"Counts do not confer permission to redistribute underlying contract data."}
    if route in ("/api/v1/research/markets","/api/v1/research/market-quote"):
        # The public viewer may use count aggregates, but contract-level
        # prices/questions require source redistribution authorization.
        if not (owner_private or bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED")):
            raise PermissionError("MARKET_SOURCE_REDISPLAY_NOT_APPROVED")
        venue=_one(q,"venue",20).lower().strip()
        if venue not in ("kalshi","polymarket"):
            raise ValueError("INVALID_MARKET_VENUE")
        if route.endswith("/markets"):
            search=_one(q,"q",80).strip().lower()
            limit=_int_arg(q,"limit",25,50) or 25
            offset=_int_arg(q,"offset",0,10000)
            rows=_db_query("""SELECT proposition_id,venue,market_id,event_id,event_title,question,
              probability,previous_probability,probability_delta_pp,quote_basis,
              CAST(known_at AS VARCHAR) AS known_at,
              CAST(observed_at AS VARCHAR) AS observed_at,
              capture_time_verified,provider_quote_freshness_verified,
              historical_point_in_time_released
              FROM main.lab_live_market_latest_v1
              WHERE lower(venue)=? AND
                (lower(question) LIKE ? OR lower(event_title) LIKE ? OR lower(market_id) LIKE ?)
              ORDER BY known_at DESC,market_id LIMIT ? OFFSET ?""",
                (venue,)+("%"+search.replace("%","\\%").replace("_","\\_")+"%",)*3+(limit,offset))
            return {"mode":"LICENSE_GATED_CAPTURED_MARKET_QUOTES","venue":venue,
                "rows":rows,"limit":limit,"offset":offset,
                "market_quote_is_not_an_event_probability":True,
                "freshness_unverified_cannot_assume_current":True,
                "source":"MotherDuck lab_live_market_latest_v1",
                "rights_scope":"OWNER_PRIVATE_RESEARCH_NOT_PUBLIC_REDISPLAY" if owner_private else "APPROVED_SOURCE_REDISPLAY_REQUIRED"}
        market_id=_one(q,"market_id",180).strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,180}",market_id):
            raise ValueError("INVALID_MARKET_ID")
        rows=_db_query("""SELECT proposition_id,venue,market_id,event_id,event_title,question,
          probability,previous_probability,probability_delta_pp,quote_basis,
          CAST(known_at AS VARCHAR) AS known_at,
          CAST(observed_at AS VARCHAR) AS observed_at,
          CAST(previous_capture_at AS VARCHAR) AS previous_capture_at,
          capture_time_verified,provider_quote_freshness_verified,
          historical_point_in_time_released,
          released_for_historical_backtesting
          FROM main.lab_live_market_latest_v1
          WHERE lower(venue)=? AND market_id=? LIMIT 1""",(venue,market_id))
        capture=_db_query("""SELECT status,yes_bid,yes_ask,last_price,
          CAST(provider_quote_at AS VARCHAR) AS provider_quote_at,
          CAST(capture_received_at AS VARCHAR) AS capture_received_at,
          source_url,source_record_sha256,data_use_class
          FROM main.lab_live_market_captures_v1
          WHERE lower(venue)=? AND market_id=?
          ORDER BY capture_received_at DESC LIMIT 1""",(venue,market_id))
        if rows and capture:
            rows[0]["capture_record"]=capture[0]
        return {"mode":"LICENSE_GATED_CAPTURED_MARKET_QUOTE",
            "venue":venue,"market_id":market_id,
            "record":rows[0] if rows else None,
            "quote_not_event_probability":True,
            "current_orderbook_or_freshness_not_guaranteed":True,
            "historical_pit_not_certified":True,
            "source":"MotherDuck lab_live_market_latest_v1",
            "rights_scope":"OWNER_PRIVATE_RESEARCH_NOT_PUBLIC_REDISPLAY" if owner_private else "APPROVED_SOURCE_REDISPLAY_REQUIRED"}
    if route=="/api/v1/research/market-history":
        if not (owner_private or bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED")):
            raise PermissionError("MARKET_SOURCE_REDISPLAY_NOT_APPROVED")
        venue=_one(q,"venue",20).lower().strip()
        market_id=_one(q,"market_id",180).strip()
        if venue not in ("kalshi","polymarket"):
            raise ValueError("INVALID_MARKET_VENUE")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,180}",market_id):
            raise ValueError("INVALID_MARKET_ID")
        limit=_int_arg(q,"limit",60,365) or 60
        rows=_db_query("""SELECT CAST(observed_date AS VARCHAR) AS observed_date,
          probability,probability_delta_pp,
          CAST(previous_observed_date AS VARCHAR) AS previous_observed_date,
          CAST(last_quote_at AS VARCHAR) AS last_quote_at,
          snapshot_count,snapshot_source,observation_provenance,
          point_in_time_verified
          FROM main.lab_market_daily_historical_v1
          WHERE lower(venue)=? AND market_id=?
          ORDER BY observed_date DESC LIMIT ?""",(venue,market_id,limit))
        return {"mode":"LICENSE_GATED_CAPTURED_MARKET_HISTORY",
                "venue":venue,"market_id":market_id,"rows":rows,
                "historical_snapshot_not_original_publication_pit":True,
                "not_calibrated_event_probability":True,
                "rights_scope":"OWNER_PRIVATE_RESEARCH_NOT_PUBLIC_REDISPLAY" if owner_private else "APPROVED_SOURCE_REDISPLAY_REQUIRED",
                "source":"MotherDuck lab_market_daily_historical_v1",
                "owner_private_research":owner_private}
    if route=="/api/v1/research/factor-catalog":
        rows=_db_query("""SELECT factor_id,name,family,unit,license_class,active
                         FROM main.lab_factor_catalog ORDER BY factor_id LIMIT 150""")
        return {"mode":"LIVE_DATABASE_FACTOR_METADATA","rows":rows,
                "note":"Warehouse catalog can be smaller than 108 Git-defined factor definitions."}
    if route in ("/api/v1/research/events","/api/v1/research/graph-nodes"):
        if not (owner_private or bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED")):
            raise PermissionError("MARKET_SOURCE_REDISPLAY_NOT_APPROVED")
        node_type="question" if route.endswith("/events") else _one(q,"type",20)
        if node_type not in ALLOW_TYPES:raise ValueError("INVALID_NODE_TYPE")
        limit=_int_arg(q,"limit",30,100)
        if limit==0:limit=30
        offset=_int_arg(q,"offset",0,50000)
        search=_one(q,"q",80).strip().lower()
        rows=_db_query("""WITH latest AS (
                     SELECT node_id, name, node_type, op, recorded_at,
                       row_number() OVER (
                          PARTITION BY node_id ORDER BY recorded_at DESC,run_id DESC
                       ) latest_version
                     FROM main.graph_nodes
                   )
                   SELECT node_id,name,
                     strftime(recorded_at,'%Y-%m-%dT%H:%M:%SZ') last_recorded_at
                   FROM latest WHERE latest_version=1 AND op='assert'
                     AND node_type=? AND lower(name) LIKE ?
                   ORDER BY node_id LIMIT ? OFFSET ?""",
                (node_type,"%"+search.replace("%","\\%").replace("_","\\_")+"%",limit,offset))
        return {"mode":"LIVE_RESEARCH_GRAPH_ENTITY_SEARCH","node_type":node_type,
                "rows":rows,"limit":limit,"offset":offset,
                "quote_pit_verified":False,
                "rights_scope":"OWNER_REDISPLAY_ACK_REQUIRED_NOT_A_LEGAL_DETERMINATION"}
    if route=="/api/v1/research/graph-neighbors":
        if not (owner_private or bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED")):
            raise PermissionError("SOURCE_GRAPH_REDISPLAY_NOT_APPROVED")
        node_id=_one(q,"node_id",128)
        if not re.fullmatch(r"[A-Za-z0-9:._=/-]{1,128}",node_id):
            raise ValueError("INVALID_NODE_ID")
        rows=_db_query("""WITH latest AS (
                  SELECT src_id,dst_id,edge_type,weight,confidence,sign,
                    provenance,note,op,
                    row_number() OVER (
                       PARTITION BY edge_id ORDER BY recorded_at DESC,run_id DESC
                    ) latest_version
                  FROM main.graph_edges
                  WHERE src_id=? OR dst_id=?
                )
                SELECT src_id,dst_id,edge_type,weight,confidence,sign,provenance,note
                FROM latest WHERE latest_version=1 AND op='assert'
                ORDER BY edge_type,src_id,dst_id LIMIT 100""",(node_id,node_id))
        neighbor_ids=list({v for edge in rows for v in (edge["src_id"],edge["dst_id"])})
        names=(_db_query("""WITH latest AS (
                    SELECT node_id,name,node_type,op,
                    row_number() OVER (
                       PARTITION BY node_id ORDER BY recorded_at DESC,run_id DESC
                    ) latest_version
                    FROM main.graph_nodes
                    WHERE node_id IN (SELECT unnest(?::VARCHAR[]))
                  )
                  SELECT node_id,name,node_type FROM latest
                  WHERE latest_version=1 AND op='assert'""",(neighbor_ids,))
               if neighbor_ids else [])
        return {"mode":"LIVE_RESEARCH_GRAPH_NEIGHBORHOOD",
                "node_id":node_id,"edges":rows,"nodes":names,
                "total_returned":len(rows),
                "review_status":"SOURCE_RELATIONS_UNREVIEWED_NOT_CAUSAL",
                "no_original_pit_or_licensing_claim":True}
    if route=="/api/v1/research/models":
        if not (owner_private or bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED")):
            raise PermissionError("DERIVED_RESEARCH_DISTRIBUTION_NOT_APPROVED")
        ticker=_one(q,"ticker",25).upper()
        if not TICKER_PATTERN.fullmatch(ticker):raise ValueError("INVALID_TICKER")
        rows=_db_query("""SELECT ticker,variant,matched_dates,training_dates,heldout_dates,
          CAST(first_day AS VARCHAR) AS first_day,CAST(last_day AS VARCHAR) AS last_day,
          market_spy_beta,dgs2_yield_change_beta,dgs10_yield_change_beta,funding_basis_beta,
          funding_hac_nw5_se,funding_ci95_low,funding_ci95_high,
          incremental_heldout_skill,research_screen_status,issuer_pit_verified,
          vendor_adjustments_and_rights_approved,institutional_beta_released,build_id
          FROM main.lab_joint_security_funding_models_v1
          WHERE upper(ticker)=?
          QUALIFY row_number() OVER (PARTITION BY variant ORDER BY build_id DESC)=1
          ORDER BY variant LIMIT 4""",(ticker,))
        return {"mode":"NONCAUSAL_EX_POST_RESEARCH","ticker":ticker,"rows":rows,
                "warning":"SPY/Treasury/funding coefficients are exploratory; no institutional issuer PIT, adjustments/rights or event-causality approval. Compare source-built variants and separate Holm correction."}
    if route=="/api/v1/research/funding-diagnostics":
        if not (owner_private or bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED")):
            raise PermissionError("DERIVED_RESEARCH_DISTRIBUTION_NOT_APPROVED")
        ticker=_one(q,"ticker",25).upper()
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError("INVALID_TICKER")
        fitted=_db_query("""SELECT ticker,variant,matched_dates,training_dates,heldout_dates,
          CAST(first_day AS VARCHAR) first_day,
          CAST(train_last_day AS VARCHAR) train_last_day,
          CAST(heldout_first_day AS VARCHAR) heldout_first_day,
          CAST(last_day AS VARCHAR) last_day,
          market_spy_beta,dgs2_yield_change_beta,dgs10_yield_change_beta,
          funding_basis_beta,funding_hac_nw5_se,funding_ci95_low,funding_ci95_high,
          market_and_treasury_heldout_mse,joint_market_treasury_funding_heldout_mse,
          incremental_heldout_skill,training_halves_sign_stable,
          research_screen_status,issuer_pit_verified,
          vendor_adjustments_and_rights_approved,institutional_beta_released,build_id
          FROM main.lab_joint_security_funding_models_v1
          WHERE upper(ticker)=?
          QUALIFY row_number() OVER (PARTITION BY variant ORDER BY build_id DESC)=1
          ORDER BY variant LIMIT 4""",(ticker,))
        adjusted=_db_query("""SELECT variant,funding_hac_se,nominal_hac_p,
          holm_familywise_p,holm_p_below_05,heldout_incremental_skill,
          full_to_trim_funding_sign_flip,relative_full_to_trim_beta_shift,
          training_half_sign_stable,familywise_research_state,
          institutional_beta_released,build_id
          FROM main.lab_joint_funding_familywise_models_v1
          WHERE upper(ticker)=?
          QUALIFY row_number() OVER (PARTITION BY variant ORDER BY build_id DESC)=1
          ORDER BY variant LIMIT 4""",(ticker,))
        family_by_variant={x["variant"]:x for x in adjusted}
        for row in fitted:
            matched=family_by_variant.get(row["variant"],{})
            row["familywise"]={k:v for k,v in matched.items() if k!="variant"}
        return {"mode":"NONCAUSAL_FUNDING_REGRESSION_DIAGNOSTICS",
                "ticker":ticker,"fits":fitted,"familywise_test_scope":
                "96 total fitted variants across 48 securities, latest accepted independent Holm audit",
                "approved_event_impact":False,"holdout_from_actual_source":True,
                "research_warning":
                "Coefficients estimate exploratory market/Treasury/funding associations, not the causal effect of any particular geopolitical or macro event. Original issuer PIT and vendor adjustments/rights remain unapproved."}
    if route=="/api/v1/research/factor-series":
        if not (owner_private or bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED")):
            raise PermissionError("FACTOR_SERIES_DISTRIBUTION_NOT_APPROVED")
        f=_one(q,"factor_id",100)
        if not FACTOR_PATTERN.fullmatch(f):raise ValueError("INVALID_FACTOR")
        n=_int_arg(q,"limit",120,365)
        if n<1:n=120
        rows=_db_query("""SELECT CAST(observed_date AS VARCHAR) AS observed_date,
          arg_max("value",availability_at) AS "value",
          arg_max(unit,availability_at) AS unit,
          strftime(max(availability_at),'%Y-%m-%dT%H:%M:%SZ') available_at,
          arg_max(availability_basis,availability_at) availability_basis
          FROM main.lab_factor_observations WHERE factor_id=?
          GROUP BY observed_date ORDER BY observed_date DESC LIMIT ?""",(f,n))
        return {"mode":"SOURCE_OBSERVED_DATE_RESEARCH_NOT_PROVIDER_ORIGINAL_PIT",
                "factor_id":f,"rows":list(reversed(rows)), "no_first_publication_claim":True}
    raise ValueError("UNKNOWN_RESOURCE")

def live_public_coverage():
    """Aggregate-only live MotherDuck telemetry for the graph website.

    No market names, questions, probabilities, quotes, raw rows, factor values,
    account metadata, or server credentials are made public. Contract totals
    represent only the bounded warehouse snapshot, NEVER provider-wide census.
    A TTL cache prevents every public page load from opening a warehouse query.
    """
    now=time.monotonic()
    with COVERAGE_LOCK:
        if LIVE_COVERAGE["metrics"] is not None and (
            now-LIVE_COVERAGE["checked_monotonic"]<COVERAGE_CACHE_SECONDS
        ):
            metrics=LIVE_COVERAGE["metrics"]
            return {"mode":"LIVE_AGGREGATE_MOTHERDUCK_NO_SOURCE_REDISPLAY",
                    "as_of_utc":LIVE_COVERAGE["as_of_utc"],
                    "cache_ttl_seconds":COVERAGE_CACHE_SECONDS,
                    "database_connected":True,"metrics":metrics,
                    "coverage_claim":"CAPTURED_WAREHOUSE_SAMPLE_NOT_ALL_PROVIDER_CONTRACTS",
                    "market_quotes_included":False,"raw_contracts_included":False,
                    "source_rights_approved":bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
                    "factor_history_rights_approved":bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED")}
        if not os.getenv("MOTHERDUCK_TOKEN"):
            raise RuntimeError("DATABASE_CREDENTIAL_NOT_CONFIGURED")
        try:
            rows=_db_query("""SELECT
             (SELECT COUNT(DISTINCT node_id) FROM main.graph_nodes WHERE node_type='question')
                AS question_node_ids,
             (SELECT COUNT(DISTINCT node_id) FROM main.graph_nodes WHERE node_type='entity')
                AS entity_node_ids,
             (SELECT COUNT(DISTINCT market_id) FROM main.lab_live_market_latest_v1
                WHERE lower(venue)='kalshi') AS captured_kalshi_market_ids,
             (SELECT COUNT(DISTINCT market_id) FROM main.lab_live_market_latest_v1
                WHERE lower(venue)='polymarket') AS captured_polymarket_market_ids,
             (SELECT COUNT(DISTINCT factor_id) FROM main.lab_factor_observations)
                AS observed_factor_series,
             (SELECT COUNT(*) FROM main.lab_factor_catalog) AS warehouse_factor_definitions,
             (SELECT COUNT(DISTINCT ticker) FROM main.lab_joint_security_funding_models_v1)
                AS securities_with_funding_models,
             (SELECT CAST(MAX(observed_date_utc) AS VARCHAR) FROM main.lab_live_market_latest_v1)
                AS latest_captured_observed_date""")
            if len(rows)!=1:raise RuntimeError("AGGREGATE_SHAPE_INVALID")
            metrics={}
            for k,v in rows[0].items():
                if k=="latest_captured_observed_date":
                    metrics[k]=str(v) if v is not None else None
                else:
                    n=int(v)
                    if n<0:raise ValueError("NEGATIVE_AGGREGATE")
                    metrics[k]=n
            LIVE_COVERAGE.update({"as_of_utc":utc_now(),"checked_monotonic":now,
                                  "metrics":metrics,"error":None})
            return {"mode":"LIVE_AGGREGATE_MOTHERDUCK_NO_SOURCE_REDISPLAY",
                    "as_of_utc":LIVE_COVERAGE["as_of_utc"],
                    "cache_ttl_seconds":COVERAGE_CACHE_SECONDS,
                    "database_connected":True,"metrics":metrics,
                    "coverage_claim":"CAPTURED_WAREHOUSE_SAMPLE_NOT_ALL_PROVIDER_CONTRACTS",
                    "market_quotes_included":False,"raw_contracts_included":False,
                    "source_rights_approved":bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
                    "factor_history_rights_approved":bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED")}
        except Exception as exc:
            LIVE_COVERAGE["error"]=type(exc).__name__
            raise


def runtime_status():
    return {"product":"EventRisk Research","mode":SCHEMA,
            "research_access":"AUTHENTICATED_SELECT_ONLY_APPLICATION_LAYER",
            "database_credential_read_only_guaranteed":False,
            "full_database_explorer":"ADMIN_ONLY_WITH_ENTITLEMENTS",
            "admin_key_configured":bool(os.getenv("EVENTRISK_DATA_ADMIN_KEY")),
            "generated_at_utc":utc_now(),
            "public_catalog_available":True,
            "database_credentials_present":bool(os.getenv("MOTHERDUCK_TOKEN")),
            "analyst_key_configured":bool(analyst_key()),
            "direct_database_queries_enabled":bool(os.getenv("MOTHERDUCK_TOKEN"))
                and bool(analyst_key()),
            "market_source_redisplay_approved":bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
            "derived_research_distribution_approved":bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"),
            "connection_tested":bool(DB_CONNECTION.get("last_success_utc"))
                and bool(os.getenv("MOTHERDUCK_TOKEN"))
                and bool(analyst_key()),
            "last_successful_authenticated_query_at_utc":
                DB_CONNECTION.get("last_success_utc"),
            "institutional_model_approved":False,
            "note":"The server restricts calls to app-defined SELECTs. Underlying PAT may be read/write. A startup SELECT verifies connectivity, not publisher rights or institutional model approval."}

class Server(BaseHTTPRequestHandler):
    server_version="EventRiskResearch/1.0"
    def log_message(self,fmt,*args):
        # Do not print query strings, passwords, bearer keys, or requested row contents.
        print("%s %s" % (self.address_string(),fmt.split("%")[0]),flush=True)
    def send(self,status,obj,ctype="application/json; charset=utf-8",method="GET"):
        payload=(json.dumps(obj,default=str,ensure_ascii=False,separators=(",",":"))
                 .encode("utf-8") if isinstance(obj,(dict,list)) else obj)
        self.send_response(status)
        self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(len(payload)))
        office_frame=urlsplit(self.path).path=="/excel/taskpane.html"
        for k,v in JSON_HEADERS.items():
            if office_frame and k=="X-Frame-Options":
                continue
            self.send_header(k,v)
        script_sources=("'self' https://appsforoffice.microsoft.com" if office_frame
                        else "'self' https://unpkg.com" if urlsplit(self.path).path=="/"
                        else "'self'")
        frame_sources="'self' https://*.office.com https://*.office365.com https://*.officeapps.live.com" if office_frame else "'none'"
        # Marco's pinned vis-network library positions a canvas using dynamic
        # inline style attributes; allow them ONLY on the original-style root,
        # never on research API responses, add-in assets, or other pages.
        style_sources="'self' 'unsafe-inline'" if urlsplit(self.path).path=="/" else "'self'"
        self.send_header("Content-Security-Policy",
            "default-src 'self'; script-src "+script_sources+
            "; style-src "+style_sources+"; img-src 'self' data:; connect-src 'self'; "+
            "object-src 'none'; frame-ancestors "+frame_sources+"; base-uri 'none'")
        self.end_headers()
        if method!="HEAD":self.wfile.write(payload)
    def do_HEAD(self):self.respond("HEAD")
    def do_GET(self):self.respond("GET")
    def respond(self,method):
        path=urlsplit(self.path)
        route=path.path
        if route=="/health/live":return self.send(200,{"ok":True,"mode":"process_liveness_only"},method=method)
        if route in FILES:
            file=(ROOT / FILES[route]).resolve()
            if not file.is_file() or ROOT not in file.parents:return self.send(404,{"error":"NOT_FOUND"},method=method)
            return self.send(200,file.read_bytes(),ctype=CONTENT_TYPES.get(file.suffix,"application/octet-stream"),method=method)
        if route=="/api/v1/live-coverage":
            try:return self.send(200,live_public_coverage(),method=method)
            except Exception as exc:
                print("EventRisk aggregate source unavailable:",type(exc).__name__,flush=True)
                return self.send(503,{"error":"LIVE_WAREHOUSE_AGGREGATE_UNAVAILABLE"},method=method)
        if route=="/api/v1/runtime":return self.send(200,runtime_status(),method=method)
        if route=="/api/v1/inventory":
            try:
                evidence=json.loads((DATA / "inventory.json").read_text(encoding="utf-8"))
                if evidence.get("refresh_mode")!="DATED_READ_ONLY_AGGREGATE_AUDIT_NOT_LIVE_DATABASE_CONNECTION":
                    raise ValueError("Unsupported source evidence class")
                return self.send(200,evidence,method=method)
            except (OSError,ValueError,KeyError):
                return self.send(503,{"error":"DATED_SOURCE_INVENTORY_UNAVAILABLE"},method=method)

        if route=="/api/v1/catalog":
            try:return self.send(200,catalog(),method=method)
            except (OSError,ValueError,KeyError) as ex:return self.send(503,{"error":"CATALOG_UNAVAILABLE"},method=method)
        if route=="/api/v1/factor-proposals":
            proposals=factor_proposals()
            return self.send(200,{"mode":"PROPOSED_UNMEASURED_FACTOR_TAXONOMY",
                "validated_series_count":0,"count":len(proposals),
                "factors":proposals,
                "note":"These are candidate research definitions, not validated data series, betas, or independently estimated factor shocks."},method=method)
        if route=="/api/v1/graph-paths":
            try:return self.send(200,graph_paths(public_graph()),method=method)
            except (OSError,ValueError,KeyError) as ex:
                return self.send(503,{"error":"PATHWAYS_UNAVAILABLE"},method=method)
        if route=="/api/v1/graph":
            try:return self.send(200,public_graph(),method=method)
            except (OSError,ValueError,KeyError) as ex:return self.send(503,{"error":"GRAPH_UNAVAILABLE"},method=method)
        if route in ALLOW_ROUTES:
            key=analyst_key()
            if not key or not os.getenv("MOTHERDUCK_TOKEN"):
                return self.send(503,{"error":"ANALYST_DATABASE_CONNECTION_NOT_CONFIGURED"},method=method)
            provided=self.headers.get("X-Analyst-Key","")
            if not provided or not hmac.compare_digest(provided,key):
                return self.send(401,{"error":"ANALYST_AUTHENTICATION_REQUIRED"},method=method)
            # The user may inspect their own warehouse privately without claiming
            # rights to publish provider-sourced records to public-site visitors.
            # Both independently issued keys are needed; never expose either key.
            supplied_owner=self.headers.get("X-Data-Admin-Key","")
            owner_key=os.getenv("EVENTRISK_DATA_ADMIN_KEY","")
            owner_private=bool(owner_key and supplied_owner and
                               hmac.compare_digest(supplied_owner,owner_key))
            if supplied_owner and not owner_private:
                return self.send(403,{"error":"DATABASE_ADMIN_AUTHORIZATION_REQUIRED"},method=method)
            if route in ADMIN_ROUTES and not owner_private:
                return self.send(403,{"error":"DATABASE_ADMIN_AUTHORIZATION_REQUIRED"},method=method)
            # Rate limit the expensive MotherDuck SELECT endpoints. This is
            # intentionally conservative while no per-user SSO exists.
            if not within_analyst_budget(key):
                return self.send(429,{"error":"RESEARCH_QUERY_RATE_LIMITED"},method=method)
            try:
                return self.send(200,research(route,parse_qs(path.query,keep_blank_values=True),owner_private=owner_private),method=method)
            except PermissionError as e:
                return self.send(403,{"error":str(e)},method=method)
            except ValueError as e:
                return self.send(400,{"error":str(e)},method=method)
            except Exception as e:
                # No SQL, source content, tokens or connection strings in public errors.
                print("EventRisk Research read-only query failed:",type(e).__name__,flush=True)
                return self.send(503,{"error":"LIVE_RESEARCH_SOURCE_UNAVAILABLE"},method=method)
        return self.send(404,{"error":"NOT_FOUND"},method=method)

def startup_database_probe():
    """One bounded SELECT on startup, so /api/v1/runtime proves DB connectivity.

    This runs once per app process, not on each public HTTP request. It does not
    reveal database contents, credentials or application authorization keys.
    """
    if not os.getenv("MOTHERDUCK_TOKEN"):
        return False
    try:
        rows=_db_query("SELECT 1 AS connection_ok")
        success=bool(rows and rows[0].get("connection_ok")==1)
        print("MotherDuck startup SELECT verified =",success,flush=True)
        return success
    except Exception as error:
        print("MotherDuck startup SELECT unavailable:",type(error).__name__,flush=True)
        return False


if __name__=="__main__":
    # Fail closed if an analyst key is configured without database credentials?
    # Public static catalog remains useful, while restricted queries return 503.
    host=os.getenv("HOST","0.0.0.0")
    port=int(os.getenv("PORT","8080"))
    print("EventRisk Research server starting. Dynamic DB configured =",bool(os.getenv("MOTHERDUCK_TOKEN")),flush=True)
    startup_database_probe()
    ThreadingHTTPServer((host,port),Server).serve_forever()
