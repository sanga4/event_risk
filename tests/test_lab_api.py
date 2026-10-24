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


    def test_retro_security_beta_coverage_never_grants_approval(self):
        calls=[]
        def source(sql,params):
            calls.append(sql)
            if "lab_security_rate_betas_retro_v1" in sql:
                return [{"fitted_research_models":864,"incorrectly_released_rows":0}]
            return [{"usd_adjusted_return_days":83427}]
        lab.app.state.query_fn=source
        result=lab.retrospective_security_beta_coverage()
        self.assertEqual(result["models"]["fitted_research_models"],864)
        self.assertFalse(result["authorized_security_beta_release"])
        self.assertFalse(result["independent_historical_vintage_verified"])

    def test_security_beta_rows_disabled_without_explicit_retro_flag(self):
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":""}):
            with self.assertRaises(HTTPException) as err:
                lab.retrospective_security_betas(research_use=True)
            self.assertEqual(err.exception.status_code,403)

    def test_security_beta_api_pagination_and_research_label(self):
        args=[]
        lab.app.state.query_fn=lambda sql,params:args.append(params) or [{"ticker":"TLT","factor_id":"DGS10"}]
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":"true"}):
            result=lab.retrospective_security_betas(
                research_use=True,ticker="TLT",factor_id="DGS10",limit=5,offset=2)
        self.assertEqual(args[0],("TLT","TLT","DGS10","DGS10",5,2))
        self.assertFalse(result["released_for_risk_use"])
        self.assertEqual(result["status"],"RETROSPECTIVE_RESEARCH_UNAPPROVED")


    def test_field_gap_summary_keeps_certification_blocked(self):
        def query(sql,params):
            if "lab_institutional_data_contract_builds_v1" in sql and "FROM eventrisk_factor_lab.main.lab_institutional_data_contract_builds_v1" in sql and "SELECT build_id,built_at" in sql:
                return [{"build_id":"contract-build","contracts_defined":16,
                         "field_rules_defined":274,"required_fields_missing":146}]
            return [{"dataset_id":"factor_observation",
                     "source_certification_complete":False}]
        lab.app.state.query_fn=query
        r=lab.institutional_data_contract_summary()
        self.assertEqual(r["audit"]["field_rules_defined"],274)
        self.assertFalse(r["source_certification_complete"])
        self.assertFalse(r["production_beta_authorized"])

    def test_field_details_are_bounded_and_not_certified(self):
        captured=[]
        lab.app.state.query_fn=lambda sql,args: captured.append(args) or [
            {"field_name":"source_published_at","inventory_status":"MISSING_FIELD"}
        ]
        r=lab.institutional_data_contract_fields(
            dataset_id="factor_observation",status="MISSING_FIELD",
            limit=7,offset=9)
        self.assertEqual(captured[0],
            ("factor_observation","factor_observation",
             "MISSING_FIELD","MISSING_FIELD",7,9))
        self.assertFalse(r["certified_for_production"])

    def test_high_correlation_factor_returns_do_not_approve_risk_model(self):
        captured=[]
        lab.app.state.query_fn=lambda sql,args: captured.append(args) or [
            {"factor_a":"DGS20","factor_b":"DGS30",
             "pearson_daily_shock_corr":0.981}]
        r=lab.retrospective_rate_factor_collinearity(
            strong_only=True,limit=5,offset=0)
        self.assertEqual(captured[0],(True,5,0))
        self.assertFalse(r["independent_factor_model_approved"])
        self.assertFalse(r["source_vintage_verified"])



    def test_production_gate_workstreams_are_not_completion_percentage(self):
        lab.app.state.query_fn = lambda sql,params: [
            {"workstream":"Point-in-time provenance","n_gates":6,
             "n_passed":1,"percent_gates_passed":16.7}
        ]
        summary=lab.production_workstream_gates()
        self.assertFalse(summary["is_project_completion_percent"])
        self.assertFalse(summary["institutional_release_approved"])
        self.assertEqual(summary["items"][0]["n_gates"],6)

    def test_blocker_register_is_paginated_and_unapproved(self):
        calls=[]
        lab.app.state.query_fn=lambda sql,params: calls.append(params) or [
            {"gate_id":"genuine_pit_factor_panel",
             "acceptance_evidence":"source vintage verification"}
        ]
        result=lab.production_action_register(limit=3,offset=7)
        self.assertEqual(calls[0],(3,7))
        self.assertEqual(len(result["items"]),1)
        self.assertFalse(result["institutional_release_approved"])



    def test_price_quality_summary_never_marks_beta_approved(self):
        lab.app.state.query_fn=lambda sql,params: [
            {"source_exception_rows":12,"beta_sensitivity_models":72,
             "models_with_beta_shift_ge_20pct":30,"source_reconciled_exceptions":0}
        ]
        result=lab.security_price_quality_summary()
        self.assertEqual(result["quality"]["source_exception_rows"],12)
        self.assertFalse(result["production_betas_approved"])
        self.assertFalse(result["source_quality_independently_approved"])

    def test_price_quality_cases_and_beta_sensitivity_pagination(self):
        query_args=[]
        lab.app.state.query_fn=lambda sql,args: query_args.append(args) or [
            {"ticker":"INTC","observed_date":"2024-08-02"}
        ]
        cases=lab.security_price_exception_cases(ticker="INTC",limit=4,offset=1)
        beta=lab.security_price_beta_sensitivity(
            ticker="INTC",factor_id="DGS10",limit=2,offset=3)
        self.assertEqual(query_args[0],("INTC","INTC",4,1))
        self.assertEqual(query_args[1],("INTC","INTC","DGS10","DGS10",2,3))
        self.assertTrue(cases["unverified_evidence_not_false_data"])
        self.assertFalse(beta["production_beta_release"])
        self.assertTrue(beta["without_flagged_days_is_not_primary_model"])


    def test_curve_model_coverage_is_not_approved(self):
        lab.app.state.query_fn=lambda sql,params:[
            {"security_models":48,"model_coefficients":144,
             "independently_verified_models":0}
        ]
        result=lab.research_curve_factor_coverage()
        self.assertEqual(result["build"]["model_coefficients"],144)
        self.assertFalse(result["risk_model_approved"])
        self.assertFalse(result["deployable_security_beta"])

    def test_curve_coefficients_require_retro_research_permission(self):
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":""}):
            with self.assertRaises(HTTPException) as err:
                lab.research_curve_coefficients(research_use=True)
            self.assertEqual(err.exception.status_code,403)

    def test_curve_coefficients_parameterize_filters_and_do_not_release(self):
        calls=[]
        lab.app.state.query_fn=lambda sql,args: calls.append(args) or [
            {"ticker":"TLT","curve_component":"LEVEL"}
        ]
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":"true"}):
            result=lab.research_curve_coefficients(
                research_use=True,ticker="TLT",component="LEVEL",limit=3,offset=4)
        self.assertEqual(calls[0],("TLT","TLT","LEVEL","LEVEL",3,4))
        self.assertFalse(result["production_risk_beta_approved"])
        self.assertTrue(result["no_tradable_forward_prediction"])

    def test_curve_quality_summary_is_still_unreleased(self):
        vals=[]
        lab.app.state.query_fn=lambda sql,args: vals.append(args) or [
            {"ticker":"TLT","standardized_train_condition":1.76}
        ]
        result=lab.research_curve_model_quality(ticker="TLT",limit=5,offset=1)
        self.assertEqual(vals[0],("TLT","TLT",5,1))
        self.assertFalse(result["risk_model_approved"])


    def test_style_factor_coverage_never_redistributes_source_values(self):
        sqls=[]
        def provider(sql, params):
            sqls.append(sql)
            if "lab_style_factor_ingest_builds_v1" in sql:
                return [{"build_id":"style-build","rows_downloaded":121598,
                         "source_publication_vintages_verified":0,
                         "production_risk_factors_approved":0}]
            return [{"factor_id":"FF_US_HML","research_rows":15897,
                     "prohibited_release_claims":0}]
        lab.app.state.query_fn=provider
        result=lab.style_factor_research_coverage()
        self.assertEqual(result["build"]["rows_downloaded"],121598)
        self.assertFalse(result["source_redistribution_rights_verified"])
        self.assertFalse(result["raw_factor_return_api_enabled"])
        self.assertFalse(result["approved_for_institutional_risk_use"])
        self.assertEqual(result["series"][0]["factor_id"],"FF_US_HML")
        self.assertNotIn("factor_return",result["series"][0])


    def test_ff6_security_coverage_does_not_serve_vendor_coefficients(self):
        lab.app.state.query_fn=lambda sql,params: [
            {"build_id":"ff6-research","included_security_models":48,
             "factor_coefficients":288,"licensed_released_betas":0}
        ]
        r=lab.style_factor_security_model_coverage()
        self.assertEqual(r["build"]["factor_coefficients"],288)
        self.assertFalse(r["raw_source_returns_served"])
        self.assertFalse(r["security_beta_coefficients_served"])
        self.assertFalse(r["rights_for_external_use_verified"])
        self.assertFalse(r["model_risk_approved"])


if __name__ == "__main__":
    unittest.main()
