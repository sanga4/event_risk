"""Public live MotherDuck aggregates must never return source text or factor values."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class LiveCoverageTests(unittest.TestCase):
    def setUp(self):
        app.LIVE_COVERAGE.update({"as_of_utc":None,"checked_monotonic":0.0,
                                  "metrics":None,"error":None})
    def tearDown(self):
        app.LIVE_COVERAGE.update({"as_of_utc":None,"checked_monotonic":0.0,
                                  "metrics":None,"error":None})
    def test_never_uses_source_redisplay_and_caches_query(self):
        rows=[{"question_node_ids":4907,"entity_node_ids":1478,
               "captured_kalshi_market_ids":1889,
               "captured_polymarket_market_ids":3000,
               "observed_factor_series":18,"warehouse_factor_definitions":22,
               "securities_with_funding_models":48,
               "latest_captured_observed_date":"2026-10-26"}]
        with mock.patch.dict(os.environ,{"MOTHERDUCK_TOKEN":"synthetic-token"},clear=True), \
             mock.patch.object(app,"_db_query",return_value=rows) as sql:
            first=app.live_public_coverage()
            second=app.live_public_coverage()
        self.assertEqual(first["mode"],"LIVE_AGGREGATE_MOTHERDUCK_NO_SOURCE_REDISPLAY")
        self.assertEqual(first["metrics"]["captured_kalshi_market_ids"],1889)
        self.assertEqual(second["metrics"],first["metrics"])
        self.assertFalse(first["market_quotes_included"])
        self.assertFalse(first["raw_contracts_included"])
        self.assertFalse(first["source_rights_approved"])
        self.assertFalse(first["factor_history_rights_approved"])
        self.assertEqual(first["coverage_claim"],"CAPTURED_WAREHOUSE_SAMPLE_NOT_ALL_PROVIDER_CONTRACTS")
        self.assertEqual(sql.call_count,1)
        statement=sql.call_args.args[0]
        self.assertTrue(app._assert_read_query(statement))
        self.assertNotIn("SELECT *",statement)
        self.assertNotIn("event_title",statement)
        self.assertNotIn("probability",statement)
        self.assertNotIn("question,",statement)
    def test_missing_database_token_returns_no_stale_results(self):
        with mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"CREDENTIAL_NOT_CONFIGURED"):
                app.live_public_coverage()
    def test_invalid_rows_fail_closed(self):
        with mock.patch.dict(os.environ,{"MOTHERDUCK_TOKEN":"synthetic"},clear=True), \
             mock.patch.object(app,"_db_query",return_value=[{"captured_kalshi_market_ids":-1}]):
            with self.assertRaises(ValueError):
                app.live_public_coverage()
    def test_excel_workbook_import_uses_only_public_aggregates(self):
        root=Path(__file__).resolve().parents[1]
        pane=(root/"excel/taskpane.html").read_text()
        script=(root/"excel/live-coverage.js").read_text()
        self.assertIn('id="live-coverage-import"',pane)
        self.assertIn("/excel/live-coverage.js",pane)
        self.assertEqual(app.FILES["/excel/live-coverage.js"],"excel/live-coverage.js")
        self.assertIn("/api/v1/live-coverage",script)
        self.assertIn('ER_LiveCoverage',script)
        self.assertNotIn("MOTHERDUCK_TOKEN",script)
        self.assertNotIn("X-Analyst-Key",script)
        self.assertNotIn("localStorage",script)

    def test_frontend_is_static_without_any_embedded_token(self):
        html=(Path(__file__).resolve().parents[1]/"viewer.html").read_text()
        script=(Path(__file__).resolve().parents[1]/"assets/live-coverage.js").read_text()
        self.assertIn("id=\"warehouse-summary\"",html)
        self.assertIn("/assets/live-coverage.js",html)
        self.assertIn("/api/v1/live-coverage",script)
        self.assertNotIn("MOTHERDUCK_TOKEN",script)
        self.assertNotIn("X-Analyst-Key",script)
        self.assertEqual(app.FILES["/assets/live-coverage.js"],"assets/live-coverage.js")
