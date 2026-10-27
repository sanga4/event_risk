import os
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class MarketProbabilityCompatibilityTests(unittest.TestCase):
    def test_legacy_api_excel_endpoints_remain_intact(self):
        self.assertTrue({"/api/v1/research/models","/api/v1/research/funding-diagnostics",
            "/api/v1/research/factor-series","/api/v1/research/events",
            "/api/v1/research/markets","/api/v1/research/market-quote"}.issubset(app.ALLOW_ROUTES))
        root=Path(__file__).resolve().parents[1]
        excel=(root/"excel/taskpane.js").read_text()
        ui=(root/"viewer.html").read_text()
        js=(root/"assets/viewer.js").read_text()
        for s in ("importReference","importGraph","importModels","importSeries","importExtended","importMarkets","importMarketHistory"):
            self.assertIn(s,excel)
        self.assertIn('id="market-values"',(root/"excel/taskpane.html").read_text())
        self.assertIn('data-tab="markets"',ui)
        for term in ("probability_delta_pp","previous_probability","quote_basis","market-quote","market-venue"):
            self.assertIn(term,js)
    def test_source_rights_gate_is_separate_from_valid_api_auth(self):
        with mock.patch.object(app,"bool_flag",return_value=False):
            with mock.patch.object(app,"_db_query") as db:
                with self.assertRaisesRegex(PermissionError,"MARKET_SOURCE_REDISPLAY_NOT_APPROVED"):
                    app.research("/api/v1/research/markets",{"venue":["kalshi"]})
                with self.assertRaisesRegex(PermissionError,"MARKET_SOURCE_REDISPLAY_NOT_APPROVED"):
                    app.research("/api/v1/research/market-quote",
                        {"venue":["polymarket"],"market_id":["123"]})
                db.assert_not_called()
    def test_owner_private_research_with_two_keys_is_not_public_redistribution(self):
        # HTTP layer verifies the separately configured data-admin key in addition
        # to the analyst key before passing owner_private=True.
        captured=[{"venue":"kalshi","market_id":"EXAMPLE","probability":.43}]
        with mock.patch.object(app,"bool_flag",return_value=False), \
             mock.patch.object(app,"_db_query",return_value=captured) as db:
            with self.assertRaises(PermissionError):
                app.research("/api/v1/research/markets",{"venue":["kalshi"]})
            private=app.research("/api/v1/research/markets",
                                 {"venue":["kalshi"]},owner_private=True)
            self.assertEqual(private["rows"][0]["probability"],.43)
            self.assertEqual(private["rights_scope"],
                             "OWNER_PRIVATE_RESEARCH_NOT_PUBLIC_REDISPLAY")
            self.assertTrue(private["freshness_unverified_cannot_assume_current"])
            self.assertEqual(db.call_count,1)

    def test_auth_market_list_uses_fixed_bound_source_sql(self):
        sample={"venue":"kalshi","market_id":"KTICK","question":"Example","event_title":"Example",
                "probability":.42,"previous_probability":.4,"probability_delta_pp":2.0,
                "known_at":"2026-10-26","observed_at":"2026-10-26","quote_basis":"captured"}
        with mock.patch.object(app,"bool_flag",return_value=True),mock.patch.object(
            app,"_db_query",return_value=[sample]) as db:
            d=app.research("/api/v1/research/markets",
                {"venue":["kalshi"],"q":["data center"],"limit":["25"]})
        self.assertEqual(d["mode"],"LICENSE_GATED_CAPTURED_MARKET_QUOTES")
        self.assertTrue(d["market_quote_is_not_an_event_probability"])
        self.assertEqual(d["rows"][0]["probability_delta_pp"],2.0)
        sql,params=db.call_args.args
        self.assertTrue(app._assert_read_query(sql))
        self.assertEqual(params[0],"kalshi")
        self.assertEqual(params[-2:],(25,0))
        self.assertNotIn("data center",sql)
    def test_market_detail_exposes_captured_source_provenance_only(self):
        with mock.patch.object(app,"bool_flag",return_value=True),mock.patch.object(
          app,"_db_query",return_value=[{"probability":.42,
          "historical_point_in_time_released":False}]) as db:
            d=app.research("/api/v1/research/market-quote",
              {"venue":["polymarket"],"market_id":["123"]})
        self.assertTrue(d["historical_pit_not_certified"])
        self.assertEqual(d["record"]["probability"],.42)
        self.assertEqual(db.call_args.args[1],("polymarket","123"))
    def test_historical_probabilities_are_source_permissioned(self):
        with mock.patch.object(app,"bool_flag",return_value=False):
            with mock.patch.object(app,"_db_query") as db:
                with self.assertRaisesRegex(PermissionError,"MARKET_SOURCE_REDISPLAY_NOT_APPROVED"):
                    app.research("/api/v1/research/market-history",
                        {"venue":["kalshi"],"market_id":["KX-ABC"]})
                db.assert_not_called()
        captured=[{"observed_date":"2026-10-26",
                  "probability":.37,"probability_delta_pp":-2.5,
                  "point_in_time_verified":False}]
        with mock.patch.object(app,"bool_flag",return_value=True),mock.patch.object(
            app,"_db_query",return_value=captured) as db:
            result=app.research("/api/v1/research/market-history",
                {"venue":["polymarket"],"market_id":["123"],"limit":["8"]})
        self.assertEqual(result["mode"],"LICENSE_GATED_CAPTURED_MARKET_HISTORY")
        self.assertTrue(result["historical_snapshot_not_original_publication_pit"])
        self.assertEqual(result["rows"][0]["probability_delta_pp"],-2.5)
        sql,params=db.call_args.args
        self.assertTrue(app._assert_read_query(sql))
        self.assertEqual(params,("polymarket","123",8))

    def test_market_id_and_venue_validation(self):
        with mock.patch.object(app,"bool_flag",return_value=True):
            for venue in ("","invalid","ALL"):
                with self.assertRaises(ValueError):
                    app.research("/api/v1/research/market-quote",
                        {"venue":[venue],"market_id":["123"]})
            for identifier in ("a' OR 1=1 --","a;DROP TABLE x","x"*181):
                with self.assertRaises(ValueError):
                    app.research("/api/v1/research/market-quote",
                        {"venue":["kalshi"],"market_id":[identifier]})
if __name__=="__main__":unittest.main()
