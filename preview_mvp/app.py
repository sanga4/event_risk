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
DATA = ROOT / "data"
MOTHERDUCK_DB = "eventrisk_factor_lab"
REFRESH_TTL_SECONDS = 300
SESSION_LOCK = threading.RLock()
DB_CONNECTION = {"conn": None, "last_success_utc": None}
RATE_LOCK = threading.Lock()
RATE_BY_SESSION = defaultdict(deque)
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS_PER_WINDOW = 90
JSON_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY"}
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".png": "image/png",
                 ".xml":"application/xml; charset=utf-8"}
FILES = {"/": "marco.html", "/previous-explorer": "index.html", "/lab": "lab.html",
         "/assets/styles.css": "assets/styles.css", "/assets/app.js": "assets/app.js",
         "/assets/mvp.css": "assets/mvp.css", "/assets/marco.css": "assets/marco.css",
         "/assets/marco.js": "assets/marco.js",
         "/assets/attribution-core.js":"assets/attribution-core.js",
         "/assets/lab.css": "assets/lab.css",
         "/assets/lab.js": "assets/lab.js",
         "/excel/taskpane.html":"excel/taskpane.html",
         "/excel/taskpane.js":"excel/taskpane.js",
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

def research(route,q):
    # Only fixed SELECT and parameterized WHEREs; no arbitrary SQL, no bulk extraction.
    if route not in ALLOW_ROUTES: raise ValueError("UNSUPPORTED_RESOURCE")
    if route in ADMIN_ROUTES:
        operation=route.rsplit("/",1)[1]
        return warehouse.explore(_db_query,operation,q,
            source_approved=bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
            derived_approved=bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"))
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
        if not bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"):
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
    if route=="/api/v1/research/funding-diagnostics":
        if not bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"):
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
    return {"product":"EventRisk Research","mode":SCHEMA,
            "research_access":"AUTHENTICATED_READ_ONLY",
            "full_database_explorer":"ADMIN_ONLY_WITH_ENTITLEMENTS",
            "admin_key_configured":bool(os.getenv("EVENTRISK_DATA_ADMIN_KEY")),
            "generated_at_utc":utc_now(),
            "public_catalog_available":True,
            "database_credentials_present":bool(os.getenv("MOTHERDUCK_TOKEN")),
            "analyst_key_configured":bool(os.getenv("PREVIEW_MVP_ANALYST_KEY")),
            "direct_database_queries_enabled":bool(os.getenv("MOTHERDUCK_TOKEN"))
                and bool(os.getenv("PREVIEW_MVP_ANALYST_KEY")),
            "market_source_redisplay_approved":bool_flag("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED"),
            "derived_research_distribution_approved":bool_flag("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"),
            "connection_tested":bool(DB_CONNECTION.get("last_success_utc"))
                and bool(os.getenv("MOTHERDUCK_TOKEN"))
                and bool(os.getenv("PREVIEW_MVP_ANALYST_KEY")),
            "last_successful_authenticated_query_at_utc":
                DB_CONNECTION.get("last_success_utc"),
            "institutional_model_approved":False,
            "note":"A configured token is not a tested connection. Authenticated /research/coverage verifies live SELECT."}

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
            if route in ADMIN_ROUTES:
                admin=os.getenv("EVENTRISK_DATA_ADMIN_KEY","")
                supplied=self.headers.get("X-Data-Admin-Key","")
                if not admin or not supplied or not hmac.compare_digest(supplied,admin):
                    return self.send(403,{"error":"DATABASE_ADMIN_AUTHORIZATION_REQUIRED"},method=method)
            # Rate limit the expensive MotherDuck SELECT endpoints. This is
            # intentionally conservative while no per-user SSO exists.
            if not within_analyst_budget(key):
                return self.send(429,{"error":"RESEARCH_QUERY_RATE_LIMITED"},method=method)
            try:
                return self.send(200,research(route,parse_qs(path.query,keep_blank_values=True)),method=method)
            except PermissionError as e:
                return self.send(403,{"error":str(e)},method=method)
            except ValueError as e:
                return self.send(400,{"error":str(e)},method=method)
            except Exception as e:
                # No SQL, source content, tokens or connection strings in public errors.
                print("EventRisk Research read-only query failed:",type(e).__name__,flush=True)
                return self.send(503,{"error":"LIVE_RESEARCH_SOURCE_UNAVAILABLE"},method=method)
        return self.send(404,{"error":"NOT_FOUND"},method=method)

if __name__=="__main__":
    # Fail closed if an analyst key is configured without database credentials?
    # Public static catalog remains useful, while restricted queries return 503.
    host=os.getenv("HOST","0.0.0.0")
    port=int(os.getenv("PORT","8080"))
    print("EventRisk Research server starting. Dynamic DB configured =",bool(os.getenv("MOTHERDUCK_TOKEN")),flush=True)
    ThreadingHTTPServer((host,port),Server).serve_forever()
