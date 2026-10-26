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
        for path in ("/","/assets/app.js","/assets/styles.css",
          "/api/v1/overview","/api/v1/release-gates","/api/v1/factors",
          "/api/v1/evidence","/api/v1/blockers","/api/v1/meta",
          "/api/v1/metrics.csv","/excel/taskpane.html","/excel/taskpane.js",
          "/excel/manifest.xml","/assets/icon-80.png","/health/live"):
            with self.subTest(path=path):
                status,_,body=self.request(path)
                self.assertEqual(status,200)
                self.assertGreater(len(body),0)

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
