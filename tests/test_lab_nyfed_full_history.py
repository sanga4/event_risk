"""Official NYFed historical SOFR/EFFR import range and fail-closed tests.

No external HTTP, credentials or warehouse writes.
"""
from __future__ import annotations
from datetime import date,timedelta
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"lab"/"phase1_nyfed_funding_rates.py"
spec=importlib.util.spec_from_file_location("ny_full_history",PATH)
ny=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ny)


class FakeResponse:
    headers={"Last-Modified":"Tue, 20 Oct 2026 12:00:00 GMT"}
    status_code=200
    def __init__(self,blob):self.content=blob
    def raise_for_status(self):pass


def payload(sid="SOFR",n=2600,start=date(2018,4,2)):
    # The short-history fixture uses a modern date to exercise completeness
    # independently of the separate stale-response guard.
    return json.dumps({"refRates":[
        {"effectiveDate":(start+timedelta(days=i)).isoformat(),
         "type":sid,"percentRate":3.75,
         "volumeInBillions":2500,
         "revisionIndicator":""}
        for i in range(n)]}).encode()


class NYFedFullHistoryTests(unittest.TestCase):
    def test_official_search_url_and_explicit_date_bounds(self):
        u,params=ny.historical_request("SOFR","secured/sofr",date(2026,10,24))
        self.assertEqual(u,"https://markets.newyorkfed.org/api/rates/secured/sofr/search.json")
        self.assertEqual(params,{"startDate":"2018-04-02","endDate":"2026-10-24"})
        e,_=ny.historical_request("EFFR","unsecured/effr",date(2026,10,24))
        self.assertIn("/unsecured/effr/search.json",e)
        self.assertNotIn("last/250",u)

    def test_only_preapproved_rate_series_and_valid_dates(self):
        for sid,path in (("FAKE","secured/sofr"),("SOFR","unsecured/effr")):
            with self.subTest(sid=sid),self.assertRaises(ValueError):
                ny.historical_request(sid,path,date(2026,10,24))
        with self.assertRaises(ValueError):
            ny.historical_request("SOFR","secured/sofr",date(2017,1,1))

    def test_full_official_history_parses_and_pins_hash(self):
        import hashlib
        blob=payload("SOFR")
        with patch.object(ny.requests,"get",return_value=FakeResponse(blob)) as client:
            _,url,sha,size,header,rows=ny.download("SOFR","secured/sofr")
        self.assertEqual(sha,hashlib.sha256(blob).hexdigest())
        self.assertEqual(size,len(blob))
        self.assertEqual(len(rows),2600)
        self.assertEqual(rows[0][0],"2018-04-02")
        self.assertTrue(rows[-1][0]>="2024-01-01")
        self.assertEqual(header,FakeResponse.headers["Last-Modified"])
        self.assertIn("startDate=2018-04-02",url)
        self.assertNotIn("api_key",url)
        self.assertEqual(client.call_args.kwargs["params"]["startDate"],"2018-04-02")

    def test_short_success_response_fails_coverage(self):
        with patch.object(ny.requests,"get",return_value=FakeResponse(payload("SOFR",260,start=date(2025,1,1)))):
            with self.assertRaisesRegex(RuntimeError,"COVERAGE_INCOMPLETE"):
                ny.download("SOFR","secured/sofr")

    def test_wrong_provider_rate_type_fails(self):
        with patch.object(ny.requests,"get",return_value=FakeResponse(payload("EFFR"))):
            with self.assertRaises(ValueError):
                ny.download("SOFR","secured/sofr")

    def test_reject_provider_errors_without_url_leakage(self):
        import requests
        with patch.object(ny.requests,"get",side_effect=requests.Timeout("sensitive_url")):
            with self.assertRaisesRegex(RuntimeError,"NYFED_HISTORICAL_PROVIDER_REQUEST_FAILED:Timeout") as ctx:
                ny.download("EFFR","unsecured/effr")
        self.assertNotIn("sensitive_url",str(ctx.exception))

    def test_original_publication_and_distribution_remain_unapproved(self):
        s=PATH.read_text()
        self.assertIn("source_original_publication_at",s) if "source_original_publication_at" in s else self.assertIn("original_provider_published_at",s)
        self.assertIn("provider_historical_revision_asof_verified",s)
        self.assertIn("source_response_received_at",s)
        self.assertIn("FALSE,FALSE,FALSE,FALSE,TRUE",s)
        self.assertIn("ORIGINAL_PUBLICATION_AT_VERIFIED=FALSE",s)
        self.assertIn("SOURCE_RIGHTS_AND_POLICY_SURPRISE_APPROVAL=BLOCKED",s)


if __name__=="__main__":
    unittest.main()
