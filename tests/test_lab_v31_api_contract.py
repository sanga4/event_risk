"""Offline public contract for source-corrected, unapproved v3.1 API."""
import importlib.util
from datetime import date
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi import HTTPException

SCRIPT=Path(__file__).resolve().parents[1]/"lab"/"api.py"
spec=importlib.util.spec_from_file_location("source_linked_lab_api",SCRIPT)
lab=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class ProtectedV31Tests(unittest.TestCase):
    def tearDown(self):
        if hasattr(lab.app.state,"query_fn"):
            del lab.app.state.query_fn

    def test_public_routes_are_protected_by_api_key_dependency(self):
        routes={r.path:r for r in lab.app.routes}
        for url in ("/v1/research/v3_1/summary","/v1/research/v3_1/panel"):
            self.assertIn(url,routes)
            self.assertTrue(any(dep.call is lab.require_api_key
                      for dep in routes[url].dependant.dependencies))

    def test_uncertified_as_known_request_fails(self):
        with self.assertRaises(HTTPException) as ctx:
            lab.panel_v31(mode="as_known",research_use=True)
        self.assertEqual(ctx.exception.status_code,409)

    def test_retrospective_optin_required(self):
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":""}):
            with self.assertRaises(HTTPException) as ctx:
                lab.panel_v31(mode="retrospective",research_use=True)
            self.assertEqual(ctx.exception.status_code,403)
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":"true"}):
            with self.assertRaises(HTTPException) as ctx:
                lab.panel_v31(mode="retrospective",research_use=False)
            self.assertEqual(ctx.exception.status_code,403)

    def test_unavailable_or_false_release_manifest_fails_closed(self):
        lab.app.state.query_fn=lambda sql,params:[]
        with self.assertRaises(HTTPException) as err:
            lab.summary_v31()
        self.assertEqual(err.exception.status_code,503)
        for field in ("original_source_pit_verified",
                      "independently_approved_event_factor_model",
                      "institutional_release_approved"):
            lab.app.state.query_fn=lambda sql,params,field=field:[
                {"original_source_pit_verified":False,
                 "independently_approved_event_factor_model":False,
                 "institutional_release_approved":False,field:True}]
            with self.subTest(field=field),self.assertRaises(HTTPException) as err:
                lab.summary_v31()
            self.assertEqual(err.exception.status_code,503)

    def test_summary_is_explicitly_internal_research_only(self):
        lab.app.state.query_fn=lambda sql,params:[{
            "build_id":"sample","original_v3_rows":233442,
            "corrected_factor_observed_dates":76662,
            "original_source_pit_verified":False,
            "independently_approved_event_factor_model":False,
            "institutional_release_approved":False}]
        obj=lab.summary_v31()
        self.assertEqual(obj["manifest"]["corrected_factor_observed_dates"],76662)
        self.assertTrue(obj["source_date_consistency_reconciled"])
        self.assertFalse(obj["original_provider_publication_time_certified"])
        self.assertFalse(obj["released_for_historical_backtesting"])

    def test_panel_pagination_and_db_authorization_filters(self):
        calls=[]
        def query(sql,params):
            calls.append((sql,params))
            return [{"factor_id":"DGS10","factor_observed_date":"2026-10-19",
                     "factor_carried_forward":True}]
        lab.app.state.query_fn=query
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":"true"}):
            obj=lab.panel_v31(mode="retrospective",research_use=True,
                proposition_id="P100",factor_id="DGS10",
                date_from=date(2026,10,17),date_to=date(2026,10,22),
                limit=5,offset=10)
        self.assertEqual(calls[0][1],("P100","P100","DGS10","DGS10",
            date(2026,10,17),date(2026,10,17),
            date(2026,10,22),date(2026,10,22),5,10))
        self.assertIn("lab_event_factor_panel_v3_1_latest",calls[0][0])
        self.assertIn("original_publication_pit_independently_certified=FALSE",calls[0][0])
        self.assertIn("institutional_event_factor_approved=FALSE",calls[0][0])
        self.assertEqual(obj["items"][0]["factor_id"],"DGS10")
        self.assertFalse(obj["approved_event_factor_causality"])
        self.assertFalse(obj["released_for_historical_backtesting"])

    def test_bad_date_range_blocks_before_db_query(self):
        lab.app.state.query_fn=lambda sql,params: (_ for _ in ()).throw(AssertionError("query should not run"))
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":"true"}):
            with self.assertRaises(HTTPException) as ctx:
                lab.panel_v31(mode="retrospective",research_use=True,
                    date_from=date(2026,10,22),date_to=date(2026,10,17))
        self.assertEqual(ctx.exception.status_code,422)

    def test_legacy_v3_warns_about_wrong_original_factor_dates(self):
        lab.app.state.query_fn=lambda sql,params:[{
            "factor_id":"DGS10","factor_observed_date":"2026-10-19"}]
        with patch.dict(os.environ,{"LAB_ENABLE_RETROSPECTIVE_READ":"true"}):
            obj=lab.panel_v3(mode="retrospective",research_use=True,
                proposition_id=None,factor_id=None,date_from=None,date_to=None,
                limit=10,offset=0)
        self.assertTrue(obj["legacy_factor_source_date_defect"])
        self.assertEqual(obj["recommended_research_panel"],"v3_1")
        self.assertFalse(obj["released_for_backtesting"])


if __name__=="__main__":
    unittest.main()
