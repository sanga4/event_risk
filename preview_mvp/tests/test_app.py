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

    def test_credential_presence_does_not_imply_query_verified(self):
        previous=app.DB_CONNECTION.get("last_success_utc")
        try:
            app.DB_CONNECTION["last_success_utc"]=None
            with mock.patch.dict(os.environ,{"MOTHERDUCK_TOKEN":"test-only-token",
                 "PREVIEW_MVP_ANALYST_KEY":"test-only-key"},clear=True):
                state=app.runtime_status()
                self.assertTrue(state["direct_database_queries_enabled"])
                self.assertFalse(state["connection_tested"])
                self.assertIsNone(state["last_successful_authenticated_query_at_utc"])
                app.DB_CONNECTION["last_success_utc"]="2026-10-26T00:00:00Z"
                self.assertTrue(app.runtime_status()["connection_tested"])
        finally:
            app.DB_CONNECTION["last_success_utc"]=previous

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

    def test_analyst_diagnostics_requires_independent_rights(self):
        with mock.patch.dict(os.environ,{"PREVIEW_MVP_DERIVED_RESEARCH_APPROVED":"false"}):
            with self.assertRaisesRegex(PermissionError,"DERIVED_RESEARCH"):
                app.research("/api/v1/research/funding-diagnostics",{"ticker":["TSM"]})

    def test_diagnostics_join_real_model_and_holm_source_versions(self):
        first=[{"ticker":"TSM","variant":"full","funding_basis_beta":0.22,
                "funding_hac_nw5_se":0.08,"issuer_pit_verified":False,
                "institutional_beta_released":False,"build_id":"model-run-A"}]
        second=[{"variant":"full","holm_familywise_p":0.97,"holm_p_below_05":False,
                 "familywise_research_state":"RESEARCH_ONLY","build_id":"holm-run-B"}]
        with mock.patch.dict(os.environ,{"PREVIEW_MVP_DERIVED_RESEARCH_APPROVED":"true"}):
            with mock.patch.object(app,"_db_query",side_effect=[first,second]) as q:
                result=app.research("/api/v1/research/funding-diagnostics",{"ticker":["TSM"]})
        self.assertEqual(result["mode"],"NONCAUSAL_FUNDING_REGRESSION_DIAGNOSTICS")
        self.assertFalse(result["approved_event_impact"])
        self.assertFalse(result["fits"][0]["familywise"]["holm_p_below_05"])
        self.assertEqual(result["fits"][0]["familywise"]["holm_familywise_p"],0.97)
        self.assertEqual(q.call_count,2)
        for call in q.call_args_list:
            self.assertEqual(call.args[1],("TSM",))
        self.assertNotIn("expected_event_return",str(result))

    def test_invalid_model_symbols_fail_before_sql(self):
        with mock.patch.dict(os.environ,{"PREVIEW_MVP_DERIVED_RESEARCH_APPROVED":"true"}):
            with mock.patch.object(app,"_db_query") as q:
                with self.assertRaisesRegex(ValueError,"INVALID_TICKER"):
                    app.research("/api/v1/research/funding-diagnostics",{"ticker":["AAPL';DROP"]})
                q.assert_not_called()

    def test_new_research_desk_static_assets(self):
        lab=(ROOT/"lab.html").read_text()
        js=(ROOT/"assets"/"lab.js").read_text()
        for term in ('id="case"','id="ticker"','id="factor"','id="model-body"',
                     'id="factor-chart"','id="export"'):
            self.assertIn(term,lab)
        for fn in ("function renderModels","function renderSeries",
                   "function renderCase","function exportLoaded"):
            self.assertIn(fn,js)
        self.assertNotIn("Math.random",js)
        self.assertIn("/lab",app.FILES)
        self.assertIn("/assets/lab.js",app.FILES)
        self.assertIn("/assets/lab.css",app.FILES)

    def test_excel_addin_sideload_source_contract(self):
        import xml.etree.ElementTree as ET
        manifest=(ROOT/"excel"/"manifest.xml").read_text()
        ET.fromstring(manifest)
        self.assertIn("https://preview-mvp-analyst-production.up.railway.app/excel/taskpane.html",manifest)
        self.assertNotIn("eventrisk-preview-web-production.up.railway.app/excel/taskpane.html",manifest)
        js=(ROOT/"excel"/"taskpane.js").read_text()
        for term in ('Office.onReady', 'Excel.run(', 'ER_Securities', 'ER_Factors',
                     'ER_Channels', 'ER_Regressions', 'ER_FactorHistory',
                     'ER_Explorer', 'SUMIFS(', 'COUNTIFS(', 'function safeCell'):
            self.assertIn(term,js)
        self.assertIn('function safeCell(x)',js)
        self.assertIn("api(\x22/api/v1/research/funding-diagnostics",js)

    def test_versioned_graph_operations_are_not_promoted(self):
        import inspect
        code=inspect.getsource(app.research)
        self.assertIn("latest_version=1 AND op='assert'",code)
        self.assertIn("PARTITION BY edge_id",code)
        self.assertIn("PARTITION BY node_id",code)

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
