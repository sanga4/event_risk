import importlib.util
import io
import json
from pathlib import Path
import os
from unittest import TestCase, mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("preview_mvp_app",ROOT/"app.py")
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class PreviewMVPAcceptance(TestCase):
    def test_reference_catalog_full(self):
        c=app.catalog()
        self.assertEqual(c["factors_count"],108)
        self.assertGreaterEqual(c["securities_count"],500)
        self.assertEqual(len(c["channels"]),22)
        self.assertTrue(all(f["historical_series_validated"] is False for f in c["factors"]))
        self.assertEqual(c["mode"],"REPO_PUBLISHED_REFERENCE_CATALOG_NOT_LIVE_QUOTES")

    def test_graph_integrity_and_unapproved_links(self):
        g=app.public_graph()
        ids={n["id"] for n in g["nodes"]}
        self.assertGreater(len(ids),680)
        self.assertEqual(len(g["nodes"]),len(ids))
        self.assertTrue(any(n["id"]=="security:TSM" for n in g["nodes"]))
        self.assertTrue(any(n["id"]=="factor:RATES.US_10Y" for n in g["nodes"]))
        self.assertTrue(any(e.get("weight")==.9 and e["src"]=="entity:Q865" and
                            e["dst"]=="security:TSM" for e in g["edges"]))
        for e in g["edges"]:
            self.assertIn(e["src"],ids);self.assertIn(e["dst"],ids)
            self.assertEqual(e["review_status"],"RESEARCH_ONLY_NOT_APPROVED")
        self.assertEqual(g["mode"],"PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE")

    def test_server_has_no_naked_db_query(self):
        with mock.patch.dict(os.environ,{},clear=True):
            self.assertFalse(app.runtime_status()["direct_database_queries_enabled"])
            with self.assertRaisesRegex(RuntimeError,"DATABASE_CREDENTIAL_NOT_CONFIGURED"):
                app._db_query("SELECT 1")

    def test_derived_results_fail_closed(self):
        with mock.patch.dict(os.environ,{"PREVIEW_MVP_DERIVED_RESEARCH_APPROVED":"false"}):
            with self.assertRaisesRegex(PermissionError,"DERIVED_RESEARCH"):
                app.research("/api/v1/research/models",{"ticker":["NVDA"]})

    def test_venue_question_contents_fail_closed(self):
        with mock.patch.dict(os.environ,{"PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED":"false"}):
            with self.assertRaisesRegex(PermissionError,"SOURCE_REDISPLAY"):
                app.research("/api/v1/research/events",{"limit":["20"]})

    def test_query_parameter_validation(self):
        with self.assertRaises(ValueError):app._int_arg({"offset":["-1"]},"offset",0,50000)
        with self.assertRaises(ValueError):app._int_arg({"limit":["10000"]},"limit",30,100)
        self.assertNotRegex("DROP TABLE","^[A-Za-z0-9.=_-]{1,25}$")

    def test_live_coverage_is_explicitly_distinct_from_catalog(self):
        with mock.patch.object(app,"_db_query",return_value=[{"metric":"graph_question_nodes","value":4907}]):
            out=app.research("/api/v1/research/coverage",{})
            self.assertEqual(out["mode"],"LIVE_DATABASE_COUNT_ONLY")
            self.assertEqual(out["coverage"][0]["value"],4907)

    def test_original_style_assets_present(self):
        text=(ROOT/"index.html").read_text()
        self.assertIn('id="network"',text)
        self.assertIn('id="analyst-key"',text)
        self.assertIn('id="live-tab"',text)
        self.assertIn('id="detail-panel"',text)
        self.assertTrue((ROOT/"assets"/"styles.css").exists())
        self.assertTrue((ROOT/"assets"/"app.js").exists())

if __name__=="__main__":
    import unittest
    unittest.main()
