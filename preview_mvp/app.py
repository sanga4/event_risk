#!/usr/bin/env python3
"""EventRisk Preview MVP: an independent, read-only analyst research gateway.

Public: source-repository securities/factor definitions and clearly illustrative
transmission graph. Authenticated+licensed: live, scoped MotherDuck SELECTs.
No direct DB calls from browsers. No institution/PIT/beta approval implied.
"""
from __future__ import annotations
from collections import Counter, defaultdict
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

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MOTHERDUCK_DB = "eventrisk_factor_lab"
REFRESH_TTL_SECONDS = 300
SESSION_LOCK = threading.RLock()
DB_CONNECTION = {"conn": None}
JSON_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY"}
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".png": "image/png"}
FILES = {"/": "index.html", "/assets/styles.css": "assets/styles.css",
         "/assets/app.js": "assets/app.js"}
FACTOR_CATALOG_VERSION = "2026-10-20.1"
SCHEMA = "ANALYST_BETA_V1_RESEARCH_ONLY"
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
}
TICKER_PATTERN = re.compile(r"^[A-Za-z0-9.=_-]{1,25}$")
FACTOR_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
def utc_now():
    return datetime.now(timezone.utc).isoformat()

def bool_flag(name):
    return os.getenv(name, "").strip().lower() == "true"

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

def _db_query(sql,params=()):
    """Fixed allowlisted SELECT statements only. Read-only database grants required."""
    if not os.getenv("MOTHERDUCK_TOKEN"):
        raise RuntimeError("DATABASE_CREDENTIAL_NOT_CONFIGURED")
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
            return [dict(zip(cols,row)) for row in cursor.fetchall()]
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

def research(route,q):
    # Only fixed SELECT and parameterized WHEREs; no arbitrary SQL, no bulk extraction.
    if route not in ALLOW_ROUTES: raise ValueError("UNSUPPORTED_RESOURCE")
    if route=="/api/v1/research/coverage":
        rows=_db_query("""SELECT 'graph_question_nodes' metric,count(DISTINCT node_id) value FROM main.graph_nodes WHERE node_type='question'
 UNION ALL SELECT 'graph_security_nodes',count(DISTINCT node_id) FROM main.graph_nodes WHERE node_type='security'
 UNION ALL SELECT 'factor_catalog_rows',count(*) FROM main.lab_factor_catalog
 UNION ALL SELECT 'graph_edges_versioned_records',count(*) FROM main.graph_edges
 UNION ALL SELECT 'captured_market_latest',count(*) FROM main.lab_live_market_latest_v1
 UNION ALL SELECT 'funding_model_versions',count(*) FROM main.lab_joint_security_funding_models_v1""")
        return {"mode":"LIVE_DATABASE_COUNT_ONLY","generated_at_utc":utc_now(),
                "database":MOTHERDUCK_DB,"coverage":rows,
                "license_notice":"Counts do not confer permission to redistribute underlying contract data."}
    if route=="/api/v1/research/factor-catalog":
        rows=_db_query("""SELECT factor_id,name,family,unit,license_class,active
                         FROM main.lab_factor_catalog ORDER BY factor_id LIMIT 150""")
        return {"mode":"LIVE_DATABASE_FACTOR_METADATA","rows":rows,
                "note":"Warehouse catalog can be smaller than 108 Git-defined factor definitions."}
    if route in ("/api/v1/research/events","/api/v1/research/graph-nodes"):
        if not bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"):
            raise PermissionError("MARKET_SOURCE_REDISPLAY_NOT_APPROVED")
        node_type="question" if route.endswith("/events") else _one(q,"type",20)
        if node_type not in ALLOW_TYPES:raise ValueError("INVALID_NODE_TYPE")
        limit=_int_arg(q,"limit",30,100)
        if limit==0:limit=30
        offset=_int_arg(q,"offset",0,50000)
        search=_one(q,"q",80).strip().lower()
        rows=_db_query("""SELECT node_id, arg_max(name, recorded_at) AS name,
                 strftime(max(recorded_at), '%Y-%m-%dT%H:%M:%SZ') AS last_recorded_at
                 FROM main.graph_nodes
                 WHERE node_type=? AND lower(name) LIKE ?
                 GROUP BY node_id ORDER BY node_id LIMIT ? OFFSET ?""",
                (node_type,"%"+search.replace("%","\\%").replace("_","\\_")+"%",limit,offset))
        return {"mode":"LIVE_RESEARCH_GRAPH_ENTITY_SEARCH","node_type":node_type,
                "rows":rows,"limit":limit,"offset":offset,
                "quote_pit_verified":False,
                "rights_scope":"OWNER_REDISPLAY_ACK_REQUIRED_NOT_A_LEGAL_DETERMINATION"}
    if route=="/api/v1/research/models":
        if not bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"):
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
    if route=="/api/v1/research/factor-series":
        if not bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"):
            raise PermissionError("FACTOR_SERIES_DISTRIBUTION_NOT_APPROVED")
        f=_one(q,"factor_id",100)
        if not FACTOR_PATTERN.fullmatch(f):raise ValueError("INVALID_FACTOR")
        n=_int_arg(q,"limit",120,365)
        if n<1:n=120
        rows=_db_query("""SELECT CAST(observed_date AS VARCHAR) observed_date,
          arg_max(value,availability_at) value, arg_max(unit,availability_at) unit,
          strftime(max(availability_at),'%Y-%m-%dT%H:%M:%SZ') available_at,
          arg_max(availability_basis,availability_at) availability_basis
          FROM main.lab_factor_observations WHERE factor_id=?
          GROUP BY observed_date ORDER BY observed_date DESC LIMIT ?""",(f,n))
        return {"mode":"SOURCE_OBSERVED_DATE_RESEARCH_NOT_PROVIDER_ORIGINAL_PIT",
                "factor_id":f,"rows":list(reversed(rows)), "no_first_publication_claim":True}
    raise ValueError("UNKNOWN_RESOURCE")

def runtime_status():
    return {"product":"Preview MVP","mode":SCHEMA,
            "generated_at_utc":utc_now(),
            "public_catalog_available":True,
            "database_credentials_present":bool(os.getenv("MOTHERDUCK_TOKEN")),
            "analyst_key_configured":bool(os.getenv("PREVIEW_MVP_ANALYST_KEY")),
            "direct_database_queries_enabled":bool(os.getenv("MOTHERDUCK_TOKEN"))
                and bool(os.getenv("PREVIEW_MVP_ANALYST_KEY")),
            "market_source_redisplay_approved":bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
            "derived_research_distribution_approved":bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"),
            "connection_tested":False,
            "institutional_model_approved":False,
            "note":"A configured token is not a tested connection. Authenticated /research/coverage verifies live SELECT."}

class Server(BaseHTTPRequestHandler):
    server_version="EventRiskPreviewMVP/1.0"
    def log_message(self,fmt,*args):
        # Do not print query strings, passwords, bearer keys, or requested row contents.
        print("%s %s" % (self.address_string(),fmt.split("%")[0]),flush=True)
    def send(self,status,obj,ctype="application/json; charset=utf-8",method="GET"):
        payload=(json.dumps(obj,default=str,ensure_ascii=False,separators=(",",":"))
                 .encode("utf-8") if isinstance(obj,(dict,list)) else obj)
        self.send_response(status)
        self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(len(payload)))
        for k,v in JSON_HEADERS.items():self.send_header(k,v)
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
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
        if route=="/api/v1/runtime":return self.send(200,runtime_status(),method=method)
        if route=="/api/v1/catalog":
            try:return self.send(200,catalog(),method=method)
            except (OSError,ValueError,KeyError) as ex:return self.send(503,{"error":"CATALOG_UNAVAILABLE"},method=method)
        if route=="/api/v1/graph":
            try:return self.send(200,public_graph(),method=method)
            except (OSError,ValueError,KeyError) as ex:return self.send(503,{"error":"GRAPH_UNAVAILABLE"},method=method)
        if route in ALLOW_ROUTES:
            key=os.getenv("PREVIEW_MVP_ANALYST_KEY","")
            if not key or not os.getenv("MOTHERDUCK_TOKEN"):
                return self.send(503,{"error":"ANALYST_DATABASE_CONNECTION_NOT_CONFIGURED"},method=method)
            provided=self.headers.get("X-Analyst-Key","")
            if not provided or not hmac.compare_digest(provided,key):
                return self.send(401,{"error":"ANALYST_AUTHENTICATION_REQUIRED"},method=method)
            try:
                return self.send(200,research(route,parse_qs(path.query,keep_blank_values=True)),method=method)
            except PermissionError as e:
                return self.send(403,{"error":str(e)},method=method)
            except ValueError as e:
                return self.send(400,{"error":str(e)},method=method)
            except Exception as e:
                # No SQL, source content, tokens or connection strings in public errors.
                print("Preview MVP read-only query failed:",type(e).__name__,flush=True)
                return self.send(503,{"error":"LIVE_RESEARCH_SOURCE_UNAVAILABLE"},method=method)
        return self.send(404,{"error":"NOT_FOUND"},method=method)

if __name__=="__main__":
    # Fail closed if an analyst key is configured without database credentials?
    # Public static catalog remains useful, while restricted queries return 503.
    host=os.getenv("HOST","0.0.0.0")
    port=int(os.getenv("PORT","8080"))
    print("Preview MVP server starting. Dynamic DB configured =",bool(os.getenv("MOTHERDUCK_TOKEN")),flush=True)
    ThreadingHTTPServer((host,port),Server).serve_forever()
