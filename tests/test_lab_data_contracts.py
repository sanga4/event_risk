"""Offline validation of institutional source schema, clock semantics and factor units."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"lab"
spec=importlib.util.spec_from_file_location(
    "institutional_contracts",ROOT/"institutional_data_contracts.py")
m=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class InstitutionalSchemaTests(unittest.TestCase):
    def test_all_expected_datasets_and_duplicate_field_definitions(self):
        m.validate_contracts()
        self.assertEqual(len(m.CONTRACTS),16)
        self.assertEqual(len({c.dataset for c in m.CONTRACTS}),16)
        self.assertGreaterEqual(sum(len(c.required_technical)+len(c.required_institutional)
                                    for c in m.CONTRACTS),250)

    def test_all_important_disconnected_model_domains_are_present(self):
        d={c.dataset:c for c in m.CONTRACTS}
        for name in ("event_innovation","asset_factor_model","position_exposure",
                     "factor_scenario","source_release_calendar",
                     "risk_factor_portfolio"):
            self.assertEqual(d[name].tier,"not_loaded")

    def test_quote_receipt_is_not_publication_time(self):
        d={c.dataset:c for c in m.CONTRACTS}
        self.assertIn("capture_received_at",d["event_quote_receipt"].required_technical)
        self.assertIn("provider_quote_at",d["event_quote_receipt"].required_institutional)
        self.assertIn("source_published_at",d["factor_observation"].required_institutional)
        self.assertIn("original_source_payload_sha256",
                      d["factor_observation"].required_institutional)

    def test_security_price_is_not_validated_total_return(self):
        d={c.dataset:c for c in m.CONTRACTS}
        self.assertIn("corporate_action_vintage",d["security_price"].required_institutional)
        self.assertIn("permanent_security_id",d["security_price"].required_institutional)
        self.assertIn("price_license_approved",d["security_price"].required_institutional)

    def test_beta_not_same_as_event_surprise(self):
        d={c.dataset:c for c in m.CONTRACTS}
        self.assertIn("expected_probability_change",
                      d["event_innovation"].required_technical)
        self.assertIn("factor_covariance_version",
                      d["asset_factor_model"].required_technical)
        self.assertIn("model_risk_approval_id",
                      d["security_rate_beta"].required_institutional)

    def test_field_coverage_audit_defaults_all_certification_to_false(self):
        src=(ROOT/"phase1_field_coverage.py").read_text()
        self.assertIn("False,commit",src)
        self.assertIn("INDEPENDENT_DATA_CERTIFICATION=NONE",src)
        self.assertIn("RELEASE_BLOCKED_SOURCE_CERTIFICATIONS_INCOMPLETE",src)

    def test_factor_diagnostics_do_not_self_approve(self):
        src=(ROOT/"phase1_factor_risk_diagnostics.py").read_text()
        self.assertIn("FALSE AS independently_verified_source_vintage",src)
        self.assertIn("PRODUCTION_FACTOR_MODEL=BLOCKED",src)
        self.assertIn("abs(corr(a_shock,b_shock))>=.95",src)


if __name__=="__main__":
    unittest.main()
