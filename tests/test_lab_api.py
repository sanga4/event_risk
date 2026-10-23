"""Offline contract tests for the standalone lab research API; no secrets/network."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException

SPEC = importlib.util.spec_from_file_location(
    "lab_api", Path(__file__).resolve().parents[1] / "lab" / "api.py"
)
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class AuthAndResearchGates(unittest.TestCase):
    def tearDown(self):
        if hasattr(lab.app.state, "query_fn"):
            del lab.app.state.query_fn

    def test_public_liveness_is_not_database_readiness(self):
        self.assertEqual(lab.live()["status"], "alive")
        with patch.dict(os.environ, {"LAB_API_KEYS": "", "MOTHERDUCK_TOKEN": ""}):
            with self.assertRaises(HTTPException) as err:
                lab.ready(None)
            self.assertEqual(err.exception.status_code, 503)

    def test_no_keys_rejects_any_caller(self):
        with patch.dict(os.environ, {"LAB_API_KEYS": ""}):
            with self.assertRaises(HTTPException) as err:
                lab.require_api_key("nonempty")
            self.assertEqual(err.exception.status_code, 401)

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {"LAB_API_KEYS": "safe-local-test-key"}):
            with self.assertRaises(HTTPException) as err:
                lab.require_api_key(None)
            self.assertEqual(err.exception.status_code, 401)

    def test_valid_key_still_requires_rights_and_database(self):
        with patch.dict(os.environ, {"LAB_API_KEYS": "safe-local-test-key",
                                     "LAB_DB": "eventrisk_factor_lab",
                                     "MOTHERDUCK_TOKEN": "",
                                     "LAB_DATA_RIGHTS_ACK": "false"}):
            with self.assertRaises(HTTPException) as err:
                lab.require_api_key("safe-local-test-key")
            self.assertEqual(err.exception.status_code, 503)

    def test_scoped_configuration_allows_key(self):
        with patch.dict(os.environ, {"LAB_API_KEYS": "safe-local-test-key",
                                     "LAB_DB": "eventrisk_factor_lab",
                                     "MOTHERDUCK_TOKEN": "local-placeholder",
                                     "LAB_DATA_RIGHTS_ACK": "true"}):
            self.assertIsNone(lab.require_api_key("safe-local-test-key"))

    def test_pit_unreleased_is_rejected(self):
        with self.assertRaises(HTTPException) as err:
            lab.panel_v3(mode="as_known", research_use=True)
        self.assertEqual(err.exception.status_code, 409)

    def test_retro_panel_disabled_by_default(self):
        with patch.dict(os.environ, {"LAB_ENABLE_RETROSPECTIVE_READ": ""}):
            with self.assertRaises(HTTPException) as err:
                lab.panel_v3(mode="retrospective", research_use=True)
            self.assertEqual(err.exception.status_code, 403)

    def test_retro_regressions_require_consent_and_flag(self):
        with patch.dict(os.environ, {"LAB_ENABLE_RETROSPECTIVE_READ": "true"}):
            with self.assertRaises(HTTPException) as err:
                lab.exploratory_regressions(research_use=False)
            self.assertEqual(err.exception.status_code, 403)

    def test_historical_coverage_is_always_disclaimed(self):
        lab.app.state.query_fn = lambda sql, args: [
            {"market_days": 565695, "backfilled_rows": 536699}
        ]
        d = lab.history_coverage()
        self.assertFalse(d["source_availability_verified"])
        self.assertTrue(d["research_only"])
        self.assertEqual(d["metrics"]["market_days"], 565695)

    def test_regressions_are_not_approved(self):
        lab.app.state.query_fn = lambda sql, args: [
            {"factor_id": "DGS10", "r_squared": 0.002}
        ]
        with patch.dict(os.environ, {"LAB_ENABLE_RETROSPECTIVE_READ": "true"}):
            d = lab.exploratory_regressions(research_use=True, factor_id="DGS10",
                                            venue=None, limit=10, offset=0)
        self.assertEqual(len(d["items"]), 1)
        self.assertFalse(d["approved_for_decision_use"])
        self.assertFalse(d["point_in_time_verified"])

    def test_factor_catalog_has_explicit_license_allowlist(self):
        captured = []
        lab.app.state.query_fn = lambda sql, args: captured.append((sql, args)) or []
        lab.factors(family="rates", limit=10, offset=0)
        self.assertIn("license_class IN", captured[0][0])
        self.assertEqual(captured[0][1], ("rates", "rates", 10, 0))


    def test_live_overview_declares_uncertified(self):
        calls = []
        def query(sql, params):
            calls.append(sql)
            return ([{"capture_rows": 10556, "source_quote_verified": 0}]
                    if "lab_live_market_captures_v1" in sql else
                    [{"venue": "kalshi", "collector_operational_recently": True}])
        lab.app.state.query_fn = query
        d = lab.prospective_capture_overview()
        self.assertEqual(d["metrics"]["capture_rows"], 10556)
        self.assertEqual(len(d["sources"]), 1)
        self.assertFalse(d["source_quote_freshness_certified"])
        self.assertFalse(d["released_for_historical_backtesting"])

    def test_prospective_changes_disabled_without_explicit_flag(self):
        with patch.dict(os.environ, {"LAB_ENABLE_PROSPECTIVE_READ": ""}):
            with self.assertRaises(HTTPException) as err:
                lab.prospective_changes(research_use=True)
            self.assertEqual(err.exception.status_code, 403)

    def test_prospective_changes_require_research_use(self):
        with patch.dict(os.environ, {"LAB_ENABLE_PROSPECTIVE_READ": "true"}):
            with self.assertRaises(HTTPException) as err:
                lab.prospective_changes(research_use=False)
            self.assertEqual(err.exception.status_code, 403)

    def test_prospective_changes_paginate_and_remain_unreleased(self):
        args = []
        lab.app.state.query_fn = lambda sql, params: args.append(params) or [{"venue": "kalshi", "market_id": "test"}]
        with patch.dict(os.environ, {"LAB_ENABLE_PROSPECTIVE_READ": "true"}):
            d = lab.prospective_changes(research_use=True, venue="kalshi", limit=5, offset=10)
        self.assertEqual(args[0], ("kalshi", "kalshi", 5, 10))
        self.assertEqual(d["items"][0]["venue"], "kalshi")
        self.assertFalse(d["quote_freshness_certified"])
        self.assertFalse(d["released_for_historical_backtesting"])

    def test_warehouse_asof_coverage_never_certifies_publication_times(self):
        def query(sql, params):
            if "lab_factor_warehouse_vintages_v1" in sql:
                return [{"factor_warehouse_vintages": 12656,
                         "independently_verified_release_records": 0}]
            return [{"event_factor_pairs": 190008, "future_warehouse_factor_pairs": 0}]
        lab.app.state.query_fn = query
        result = lab.warehouse_asof_coverage()
        self.assertEqual(result["co_observations"]["event_factor_pairs"], 190008)
        self.assertFalse(result["provider_publication_times_independently_verified"])
        self.assertFalse(result["historical_backtest_released"])

    def test_warehouse_asof_grid_requires_explicit_research_switch(self):
        with patch.dict(os.environ, {"LAB_ENABLE_PROSPECTIVE_READ": ""}):
            with self.assertRaises(HTTPException) as error:
                lab.warehouse_asof_grid(research_use=True)
            self.assertEqual(error.exception.status_code, 403)

    def test_warehouse_asof_grid_is_always_unreleased(self):
        observed = []
        lab.app.state.query_fn = lambda sql,params: observed.append(params) or [
            {"factor_id": "DGS10", "factor_ingested_at": "2026-10-23T06:00:00Z"}
        ]
        with patch.dict(os.environ, {"LAB_ENABLE_PROSPECTIVE_READ": "true"}):
            result = lab.warehouse_asof_grid(
                research_use=True,venue="kalshi",factor_id="DGS10",
                proposition_id="prop:kalshi:K1",limit=10,offset=0
            )
        self.assertEqual(observed[0],("kalshi","kalshi","DGS10","DGS10",
                                      "prop:kalshi:K1","prop:kalshi:K1",10,0))
        self.assertFalse(result["historical_backtest_released"])
        self.assertFalse(result["approved_mapping"])


    def test_forward_review_summary_never_grants_signal_authorization(self):
        calls = []
        def query(sql, params):
            calls.append(sql)
            if "lab_forward_mapping_hypotheses_v1" in sql:
                return [{"path_hypotheses": 8216, "asof_leakage_rows": 0}]
            return [{"review_items":97,"pending":97,"signals_released":0}]
        lab.app.state.query_fn=query
        result=lab.forward_mapping_summary()
        self.assertEqual(result["hypotheses"]["path_hypotheses"],8216)
        self.assertEqual(result["review_queue"]["pending"],97)
        self.assertFalse(result["mapping_approved"])
        self.assertFalse(result["approved_for_historical_backtests"])

    def test_forward_queue_bounded_filter_and_not_approved(self):
        params=[]
        lab.app.state.query_fn=lambda sql,args: params.append(args) or [
            {"review_id":"forward-review:abc","review_state":"pending_human_review"}
        ]
        result=lab.forward_mapping_queue(
            review_state="pending_human_review",venue="kalshi",
            factor_id="DGS10",event_channel="conflict",limit=3,offset=6
        )
        self.assertEqual(params[0],("pending_human_review","kalshi","kalshi",
                                   "DGS10","DGS10","conflict","conflict",3,6))
        self.assertFalse(result["signals_released"])
        self.assertTrue(result["analyst_approval_required"])



if __name__ == "__main__":
    unittest.main()
