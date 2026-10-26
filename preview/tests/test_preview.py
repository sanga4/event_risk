"""Offline functional and security smoke tests for self-contained public preview."""
import csv
from io import StringIO
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from urllib.error import HTTPError
from xml.etree import ElementTree as ET
import unittest
import threading

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Handler, ThreadingHTTPServer, read_snapshot, response_for, csv_export, ROOT


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.httpd.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def request(self,path):
        with urlopen(self.base+path,timeout=5) as r:
            return r.status,dict(r.headers),r.read()

    def test_snapshot_reconciles_and_rejects_fake_approvals(self):
        data=read_snapshot()
        self.assertEqual(data["mode"],"FROZEN_RESEARCH_AGGREGATES")
        self.assertFalse(data["release"]["institutional_release_approved"])
        self.assertEqual(data["release"]["automatic_passed"],25)
        self.assertEqual(data["release"]["automatic_total"],54)
        self.assertEqual(data["evidence"]["holm_surviving_models"],0)
        self.assertTrue(data["release"]["gate_predates_bea_ingestion"])

    def test_api_is_live_http_but_reports_frozen_data(self):
        status,headers,body=self.request("/api/v1/meta")
        self.assertEqual(status,200)
        obj=json.loads(body)
        self.assertFalse(obj["live_data_refresh_enabled"])
        self.assertIn("2026-10-26",obj["as_of_utc"])
        self.assertEqual(headers["Cache-Control"],"no-store")
        self.assertEqual(headers["X-Content-Type-Options"],"nosniff")

    def test_overview_is_aggregate_only(self):
        data=json.loads(self.request("/api/v1/overview")[2])
        self.assertEqual(len(data["metrics"]),9)
        self.assertTrue(all(m["source_kind"]=="audited_aggregate" for m in data["metrics"]))
        self.assertNotIn("original_html",str(data))
        self.assertNotIn("MOTHERDUCK_TOKEN",str(data))

    def test_all_documented_routes(self):
        for path in ("/","/report","/assets/app.js","/assets/styles.css","/assets/report.js","/assets/report.css",
          "/api/v1/overview","/api/v1/graph","/api/v1/capabilities","/api/v1/release-gates","/api/v1/factors",
          "/api/v1/evidence","/api/v1/blockers","/api/v1/meta",
          "/api/v1/metrics.csv","/excel/taskpane.html","/excel/taskpane.js","/excel/taskpane.css",
          "/excel/manifest.xml","/assets/icon-80.png","/health/live"):
            with self.subTest(path=path):
                status,_,body=self.request(path)
                self.assertEqual(status,200)
                self.assertGreater(len(body),0)

    def test_office_taskpane_allows_intended_embedding(self):
        _,headers,_=self.request("/excel/taskpane.html")
        self.assertNotIn("X-Frame-Options",headers)
        self.assertIn("officeapps.live.com",headers["Content-Security-Policy"])
        _,api_headers,_=self.request("/api/v1/overview")
        self.assertEqual(api_headers["X-Frame-Options"],"SAMEORIGIN")

    def test_original_visual_design_is_preserved(self):
        markup=self.request("/")[2].decode("utf-8")
        style=self.request("/assets/styles.css")[2].decode("utf-8")
        self.assertIn("<h1>Event Risk Graph</h1>",markup)
        self.assertIn("How it works",markup)
        self.assertIn("Excel &amp; API",markup)
        self.assertIn("href=\"/report\"",markup)
        self.assertIn("--question: #2a78d6",style)
        self.assertIn("--entity: #eb6834",style)
        self.assertIn("--security: #1baf7a",style)
        self.assertIn("--left:300px",style)
        self.assertIn("--right:360px",style)

    def test_capability_report_is_request_time_from_frozen_sources(self):
        from app import capabilities_report
        g=capabilities_report(read_snapshot())
        self.assertEqual(g["report_type"],"ENGINEERING_CAPABILITY_REPORT")
        self.assertEqual(g["source_mode"],"REQUEST_TIME_READ_OF_FROZEN_AUDITED_SNAPSHOTS")
        self.assertEqual(g["graph"]["nodes"],84)
        self.assertEqual(g["graph"]["edges"],102)
        self.assertEqual(g["graph"]["node_types"]["security"],52)
        self.assertEqual(g["graph"]["edge_types"]["research_exposure_prior"],60)
        self.assertFalse(g["institutional_release_approved"])
        self.assertFalse(g["continuous_market_refresh_enabled"])
        self.assertGreaterEqual(len(g["capabilities"]),6)
        got=json.loads(self.request("/api/v1/capabilities")[2])
        self.assertEqual(got["graph"]["nodes"],84)
        self.assertIn("generated_at_utc",got)
        self.assertIn("BEA",str(got))
        html=self.request("/report")[2].decode()
        self.assertIn("/assets/report.js",html)
        self.assertIn("RESEARCH",html.upper())
        self.assertNotIn("<style>",html)

    def test_excel_import_contains_graph_and_real_formulas(self):
        js=self.request("/excel/taskpane.js")[2].decode()
        html=self.request("/excel/taskpane.html")[2].decode()
        self.assertIn('id="import-graph"',html)
        for token in ("ER_Nodes","ER_Edges","ER_Metrics","ER_Explorer",
                      "COUNTIFS(","SUMIFS(","institutional_release_approved"):
            self.assertIn(token,js)
        self.assertIn("graph.edges",js)
        self.assertNotIn("ER.BETA",js)

    def test_graph_api_and_source_types(self):
        from app import read_graph
        graph=read_graph()
        self.assertEqual(graph["mode"], "FROZEN_PUBLIC_SEED_PRIORS_AND_ILLUSTRATIVE_EVENT_SCENARIOS")
        self.assertGreaterEqual(len(graph["nodes"]), 70)
        self.assertGreaterEqual(len(graph["edges"]), 90)
        self.assertEqual({n["type"] for n in graph["nodes"]},
                         {"event","entity","security","channel","factor"})
        api=json.loads(self.request("/api/v1/graph")[2])
        self.assertEqual(api["version"],graph["version"])
        self.assertTrue(all(e["review_status"]=="RESEARCH_ONLY_NOT_APPROVED" for e in api["edges"]))

    def test_graph_original_seed_weights_and_no_fake_model_approval(self):
        from app import read_graph
        graph=read_graph()
        exposed=[e for e in graph["edges"] if e["type"]=="research_exposure_prior"]
        self.assertGreaterEqual(len(exposed), 40)
        self.assertTrue(all("seeds/exposures.csv"==e["source"] for e in exposed))
        self.assertTrue(all(0 < e["weight"] <= 1 for e in exposed))
        self.assertTrue(all(n["review_status"]!="INSTITUTIONAL_APPROVED" for n in graph["nodes"]))
        self.assertTrue(all(n["source"]=="seeds/factors.json" for n in graph["nodes"] if n["type"]=="factor"))

    def test_official_bea_values_are_not_surprises(self):
        from app import read_graph
        graph=read_graph()
        bea=[n for n in graph["nodes"] if n.get("source_received_at")]
        self.assertEqual(len(bea),2)
        self.assertEqual({n["reported_value"] for n in bea},{0.2,105.6})
        self.assertTrue(all(n["review_status"]=="ORIGINAL_OFFICIAL_VALUE_RECEIPT_RESEARCH_ONLY" for n in bea))
        self.assertTrue(all(n["source_received_at"].startswith("2026-10-26") for n in bea))

    def test_graph_rejects_false_institutional_approval(self):
        from app import read_graph
        import tempfile
        good=read_graph()
        good["edges"][0]["review_status"]="INSTITUTIONAL_APPROVED"
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"graph.json"
            file.write_text(json.dumps(good))
            with self.assertRaises(ValueError):
                read_graph(file)

    def test_graph_rejects_forged_analyst_weights(self):
        from app import read_graph
        import tempfile
        good=read_graph()
        edge=next(e for e in good["edges"] if e["type"]=="research_exposure_prior")
        edge["weight"]=1.5
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"graph.json"
            file.write_text(json.dumps(good))
            with self.assertRaises(ValueError):
                read_graph(file)

    def test_graph_ui_has_three_panes_and_interactions(self):
        html=self.request("/")[2].decode("utf-8")
        for s in ("left-panel", "canvas-panel", "detail-panel",
                  "id=\"network\"", "data-depth=\"3\"", "id=\"search\"",
                  "id=\"full-network\"", "id=\"back-focus\"",
                  "id=\"hide-analyst\""):
            self.assertIn(s,html)
        js=self.request("/assets/app.js")[2].decode("utf-8")
        for fn in ("function selectNode", "function updateVisible", "function drawDetail",
                   "function fitGraph", "function screenToWorld"):
            self.assertIn(fn,js)
        self.assertNotIn("unpkg.com",html)

    def test_private_paths_fail_closed(self):
        for path in ("/api/v1/raw-prices","/api/v1/security-positions",
          "/../../.env","/preview/data/snapshot.json","/.git/config","/lab/api.py"):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as cm:
                    self.request(path)
                self.assertEqual(cm.exception.code,404)

    def test_no_credentials_or_write_api(self):
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/v1/refresh?token=secret")
        self.assertEqual(cm.exception.code,404)
        self.assertNotIn("Access-Control-Allow-Origin",self.request("/api/v1/meta")[1])

    def test_csv_escaping_and_excel_openable(self):
        data=read_snapshot()
        output=csv_export(data).decode("utf-8")
        parsed=list(csv.reader(StringIO(output)))
        self.assertEqual(len(parsed),10)
        self.assertEqual(parsed[0],["Metric","Value","Unit","Verified as of UTC","Evidence source","Status"])
        data["metrics"][0]["label"]="=HYPERLINK(\"malicious\")"
        poison=csv_export(data).decode("utf-8")
        self.assertTrue(list(csv.reader(StringIO(poison)))[1][0].startswith("'="))

    def test_manifest_is_real_https_excel_taskpane(self):
        root=ET.fromstring((ROOT/"excel"/"manifest.xml").read_text())
        ns={"m":"http://schemas.microsoft.com/office/appforoffice/1.1"}
        src=root.find("m:DefaultSettings/m:SourceLocation",ns)
        self.assertIsNotNone(src)
        self.assertTrue(src.attrib["DefaultValue"].startswith("https://eventrisk-preview-web-production.up.railway.app/"))
        self.assertTrue((ROOT/"assets"/"icon-80.png").is_file())

    def test_blockers_preserved(self):
        data=json.loads(self.request("/api/v1/blockers")[2])
        self.assertGreaterEqual(len(data["blockers"]),9)
        self.assertTrue(all(b["status"]=="blocked" for b in data["blockers"]))

    def test_static_uses_no_dependency_cdn_except_office_taskpane(self):
        page=(ROOT/"index.html").read_text()
        self.assertNotIn("cdn.jsdelivr",page)
        self.assertIn("/assets/app.js",page)


if __name__=="__main__":
    unittest.main()
