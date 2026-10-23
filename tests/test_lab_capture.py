"""Offline source collection and PIT/provenance contract checks. No HTTP or DB."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "lab" / "phase1_live_capture.py"
spec = importlib.util.spec_from_file_location("phase1_capture", MODULE)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class ProspectiveCaptureTests(unittest.TestCase):
    def test_midpoint_preferred_to_last(self):
        px,b,a,last,basis=capture.safe_yes_quote("0.2","0.4","0.99")
        self.assertAlmostEqual(px, 0.3)
        self.assertEqual(basis,"indicative_bid_ask_midpoint")
        self.assertEqual(last,0.99)

    def test_crossed_quotes_fallback_to_last_without_invented_midpoint(self):
        px,b,a,last,basis=capture.safe_yes_quote(0.85,0.2,0.6)
        self.assertEqual(px,0.6)
        self.assertEqual(basis,"reported_last_trade_price")

    def test_invalid_quotes_fail_closed(self):
        for invalid in ("nan","inf","-1","2",None):
            self.assertIsNone(capture.finite_probability(invalid))
        self.assertEqual(capture.safe_yes_quote("nan","nan",None)[-1],
                         "no_valid_yes_price")

    def test_receipt_time_not_provider_freshness(self):
        record={"title":"Example"}
        result=capture.make_market(
            "kalshi","TICKER","event-1","Example","Will X?",
            "active",record,{"rules":"example"},"2026-10-23T17:00:00+00:00",
            "a"*64,"https://external-api.kalshi.com/trade-api/v2/events",
            "run_test",0.25,0.35,0.31)
        self.assertTrue(result["capture_time_verified"])
        self.assertFalse(result["provider_quote_freshness_verified"])
        self.assertFalse(result["historical_point_in_time_released"])
        self.assertIsNone(result["provider_quote_at"])
        self.assertEqual(len(result["contract_sha256"]),64)
        self.assertEqual(len(result["source_record_sha256"]),64)

    def test_hash_independent_of_json_key_order(self):
        self.assertEqual(capture.stable_hash({"b":1,"a":2}),
                         capture.stable_hash({"a":2,"b":1}))

    def test_documented_gamma_numeric_tag_filters_and_deduplicates(self):
        calls=[]
        sample={"id": "42","title":"Policy question",
                "markets":[{"id":"123","question":"Will X occur?",
                            "bestBid":"0.1","bestAsk":"0.3",
                            "lastTradePrice":"0.2","active":True}]}
        def fake_fetch(session,url,params):
            calls.append((url,params))
            if "/tags/slug/" in url:
                return {"id":17 if url.endswith("geopolitics") else 18},"2026-10-23T17:00:00+00:00","b"*64
            return [sample],"2026-10-23T17:00:00+00:00","c"*64
        with patch.object(capture,"fetch_page",side_effect=fake_fetch):
            quotes=capture.collect_polymarket(object(),"test-run")
        self.assertEqual(len(quotes),1)
        self.assertEqual(quotes[0]["venue"],"polymarket")
        event_calls=[params for url,params in calls if url.endswith("/events")]
        self.assertEqual([x["tag_id"] for x in event_calls],[17,18])
        self.assertTrue(all("tag_slug" not in x for x in event_calls))

    def test_schema_preserves_research_only_flags(self):
        text=MODULE.read_text()
        self.assertIn("historical_point_in_time_released",text)
        self.assertIn("FALSE AS provider_quote_freshness_verified",text)
        self.assertIn("INSERT INTO {P}lab_live_market_captures_v1",text)
        self.assertNotIn("UPDATE eventrisk_factor_lab.main.lab_event_factor_panel_v2",text)


if __name__=="__main__":
    unittest.main()
