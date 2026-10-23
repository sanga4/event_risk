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


if __name__ == "__main__":
    unittest.main()
