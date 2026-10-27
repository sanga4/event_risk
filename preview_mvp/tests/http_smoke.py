"""Loopback HTTP acceptance for the actual standalone Preview MVP process."""
import json,os,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
port=18739
env={**os.environ,"HOST":"127.0.0.1","PORT":str(port)}
env.pop("MOTHERDUCK_TOKEN",None)
env.pop("PREVIEW_MVP_ANALYST_KEY",None)
env.pop("PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED",None)
env.pop("PREVIEW_MVP_DERIVED_RESEARCH_APPROVED",None)
root=Path(__file__).resolve().parents[1]
proc=subprocess.Popen([sys.executable,"app.py"],cwd=root,env=env,
                     stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def call(route):
    with urllib.request.urlopen("http://127.0.0.1:"+str(port)+route,timeout=15) as r:
        return r, r.read(3000000)
try:
    for i in range(60):
        try: r,_=call("/health/live");break
        except (urllib.error.URLError,ConnectionError):
            if proc.poll() is not None:raise RuntimeError("server exited")
            time.sleep(.2)
    else:raise RuntimeError("server failed readiness")
    for route in ("/","/previous-explorer","/lab","/api","/data","/assets/viewer.css","/assets/viewer.js","/assets/data.css","/assets/data.js","/assets/marco.css","/assets/marco.js","/assets/attribution-core.js","/assets/styles.css","/assets/mvp.css","/assets/app.js","/assets/lab.css","/assets/lab.js","/excel/taskpane.html","/excel/taskpane.css","/excel/taskpane.js","/excel/manifest.xml"):
        r,data=call(route)
        assert r.status==200 and data,(route,r.status)
        assert r.headers.get("Access-Control-Allow-Origin") is None,route
    response,home=call("/")
    assert b"Event Risk Graph" in home and b"data-tab=\"entities\"" in home and b"Event Attribution" not in home
    assert b"data-side=\"left\"" in home
    assert b"data-side=\"right\"" in home
    _,lab=call("/lab")
    assert b"id=\"factor-chart\"" in lab and b"id=\"run-regression\"" in lab
    _,api_doc=call("/api")
    assert b"/api/v1/research/funding-diagnostics" in api_doc
    csp=response.headers.get("Content-Security-Policy","")
    assert "https://unpkg.com" in csp
    assert "frame-ancestors 'none'" in csp
    response,admin=call("/data")
    assert b"id=\"analyst-key\"" in admin
    assert b"id=\"admin-key\"" in admin
    assert b"id=\"dataset-list\"" in admin
    assert b"MotherDuck" in admin
    _,raw=call("/api/v1/catalog")
    c=json.loads(raw)
    assert c["securities_count"]>=500 and c["factors_count"]==108
    assert len(c["channels"])==22
    _,raw=call("/api/v1/graph")
    graph=json.loads(raw); ids={n["id"] for n in graph["nodes"]}
    _,directional=call("/api/v1/graph-paths")
    paths=json.loads(directional)
    assert paths["mode"]=="PUBLIC_REFERENCE_PLUS_EXPLICIT_SYNTHETIC_PATH_EXAMPLE"
    assert paths["contract_count_verified"]==0
    path_ids={n["id"] for n in paths["nodes"]}
    assert "contract:illustrative:data_center_power" in path_ids
    assert "event:data_center_demand" in path_ids
    assert "security:EQIX" in path_ids
    assert "factor:PROPOSED.REAL_ESTATE.DC_REIT" in path_ids

    assert len(graph["nodes"])==len(ids) and len(ids)>680
    assert all(e["src"] in ids and e["dst"] in ids for e in graph["edges"])
    assert all(e["review_status"]=="RESEARCH_ONLY_NOT_APPROVED" for e in graph["edges"])
    response,html=call("/excel/taskpane.html")
    assert response.headers.get("X-Frame-Options") is None
    assert "appsforoffice.microsoft.com" in response.headers.get("Content-Security-Policy","")
    assert b"office.js" in html
    _,inv=call("/api/v1/inventory")
    evidence=json.loads(inv)
    assert evidence["counts"]["distinct_question_nodes"]==4907
    assert evidence["counts"]["independent_familywise_Holm_survivors"]==0
    assert evidence["refresh_mode"]=="DATED_READ_ONLY_AGGREGATE_AUDIT_NOT_LIVE_DATABASE_CONNECTION"
    _,raw=call("/api/v1/runtime")
    status=json.loads(raw)
    assert status["direct_database_queries_enabled"] is False
    assert status["institutional_model_approved"] is False
    try:
        call("/api/v1/research/datasets")
        raise AssertionError("Admin database schema should require configured credentials")
    except urllib.error.HTTPError as e:
        assert e.code==503,e.code
    try:
        call("/api/v1/research/coverage")
        raise AssertionError("Live DB query illegally succeeded with no credential")
    except urllib.error.HTTPError as e:
        assert e.code==503,e.code
        assert json.loads(e.read())["error"]=="ANALYST_DATABASE_CONNECTION_NOT_CONFIGURED"
    for p in ("/.env","/data/securities.csv","/app.py","/api/v1/research/models?ticker=NVDA"):
        try:
            call(p)
            raise AssertionError("Private content illegally served: "+p)
        except urllib.error.HTTPError as e:
            assert e.code in (404,503),p
    print("PREVIEW_MVP_LOCAL_HTTP_AND_AUTH_FAIL_CLOSED_ACCEPTANCE=PASS")
    print("rows",c["securities_count"],"factors",c["factors_count"],
          "channels",len(c["channels"]),"nodes",len(ids),"edges",len(graph["edges"]))
finally:
    proc.terminate()
    try:proc.wait(timeout=4)
    except subprocess.TimeoutExpired:proc.kill()
