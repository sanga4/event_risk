"""Authenticated FRED transport adversarial offline contract, no live network."""
from __future__ import annotations
import importlib.util
import json
import os
from datetime import date,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import requests

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_fred_macro_research.py"
spec=importlib.util.spec_from_file_location("fred_macro",SRC)
fred=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fred)

SECRET="a"*32


def payload(count=300, duplicate=False, bad_realtime=False):
    start=date(2024,1,1)
    items=[]
    for i in range(count):
        day=start+timedelta(days=i if not duplicate or i!=4 else 3)
        items.append({"realtime_start":"2026-10-24" if not bad_realtime else "invalid",
                      "realtime_end":"2026-10-24",
                      "date":day.isoformat(),"value":"1.5"})
    return json.dumps({"observations":items}).encode()


class FredAuthTests(TestCase):
    def test_key_required_before_request(self):
        with patch.dict(os.environ,{"FRED_API_KEY":"","api_secret_FRED_API_KEY":""}):
            with patch.object(fred.requests,"get",side_effect=AssertionError("HTTP must not run")):
                with self.assertRaisesRegex(RuntimeError,"FRED_API_KEY_REQUIRED"):
                    fred.download("DFF","daily","unit","method")

    def test_secret_never_persisted_in_source_url(self):
        blob=payload()
        called=[]
        def fake_get(url,params,timeout,headers):
            called.append((url,params,timeout,headers))
            return SimpleNamespace(status_code=200,content=blob,headers={},
                                   url=url+"?api_key="+SECRET)
        with patch.dict(os.environ,{"FRED_API_KEY":SECRET,"api_secret_FRED_API_KEY":""}):
            with patch.object(fred.requests,"get",side_effect=fake_get):
                result=fred.download("DFF","daily","annualized_percent_rate","rate_level_change_basis_points")
        self.assertEqual(len(result[-1]),300)
        self.assertNotIn(SECRET,result[4])
        self.assertEqual(called[0][1]["api_key"],SECRET)
        self.assertIn("series_id=DFF",result[4])
        self.assertEqual(called[0][2],(10,25))

    def test_request_error_redacts_secret(self):
        with patch.dict(os.environ,{"FRED_API_KEY":SECRET,"api_secret_FRED_API_KEY":""}):
            with patch.object(fred.requests,"get",side_effect=requests.Timeout("api_key="+SECRET)):
                with self.assertRaisesRegex(RuntimeError,"FRED_PROVIDER_REQUEST_FAILED") as ctx:
                    fred.download("DFF","daily","u","method")
        self.assertNotIn(SECRET,str(ctx.exception))

    def test_bad_http_status_no_payload_used(self):
        with patch.dict(os.environ,{"FRED_API_KEY":SECRET,"api_secret_FRED_API_KEY":""}):
            with patch.object(fred.requests,"get",return_value=SimpleNamespace(status_code=401)):
                with self.assertRaisesRegex(RuntimeError,"FRED_PROVIDER_HTTP_401"):
                    fred.download("DFF","daily","u","method")

    def test_malformed_revisions_and_duplicate_observations(self):
        for blob in (payload(duplicate=True),payload(bad_realtime=True),
                     b'{"observations":[null]}',b'{}',b'not-json'):
            with self.subTest(sample=blob[:60]),self.assertRaises(ValueError):
                fred.read_fred_api(blob,"DFF","daily")

    def test_not_inventing_release_vintages(self):
        observations=fred.read_fred_api(payload(),"DFF","daily")
        self.assertEqual(observations[0][0],"2024-01-01")
        self.assertTrue(all(isinstance(v,float) for _,v in observations))

    def test_original_2018_history_only_insufficient_monthly(self):
        # More than 250 monthly rows requires fetching from well before 2018.
        self.assertEqual(fred.VERSION,"phase1-fred-cross-domain-raw-v1.1.0")
        self.assertEqual(fred.BASE,"https://api.stlouisfed.org/fred/series/observations")


if __name__=="__main__":
    import unittest
    unittest.main()
