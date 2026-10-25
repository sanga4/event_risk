"""Fail-closed current-run receipt-to-grid operational readiness contract."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from pathlib import Path
import importlib.util,unittest

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_capture_grid_handoff.py"
spec=importlib.util.spec_from_file_location("capture_grid",SRC)
q=importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
NOW=datetime(2026,10,25,18,0,tzinfo=timezone.utc)

def fixture():
    feeds=[
        ("kalshi","ok",1888,5,True,False),
        ("polymarket","ok",3000,6,True,False)]
    captures=[
        ("kalshi","recent-k",1888,NOW,0),
        ("polymarket","recent-p",3000,NOW,0)]
    grid=[
        ("kalshi","recent-k",1888*18,1888,NOW,0,0),
        ("polymarket","recent-p",3000*18,3000,NOW,0,0)]
    return feeds,captures,grid,(0,0,0)

class CaptureToGridContracts(unittest.TestCase):
    def test_valid_receipts_are_operational_not_licensed(self):
        x=q.assess(*fixture())
        self.assertEqual(x["venues"],2)
        self.assertEqual(x["latest_capture_rows"],4888)
        self.assertEqual(x["latest_capture_grid_rows"],4888*18)
        self.assertTrue(x["warehouse_grid_reconciled"])
        self.assertFalse(x["original_quote_clock_verified"])
        self.assertFalse(x["institutional_risk_release"])

    def test_missing_venue_or_bad_freshness_fails(self):
        f,c,g,i=fixture()
        with self.assertRaisesRegex(ValueError,"Both venue"):
            q.assess(f[:1],c,g,i)
        for pos,value in ((1,"failed"),(2,0),(3,721),(3,-1),
                          (4,False),(5,True)):
            f,c,g,i=fixture();row=list(f[0]);row[pos]=value;f[0]=tuple(row)
            with self.subTest(pos=pos,value=value),self.assertRaisesRegex(
                ValueError,"Collector-to-grid"):
                q.assess(f,c,g,i)

    def test_incomplete_factor_join_is_not_a_fresh_asof_grid(self):
        for pos,value in ((1,"previous-run"),(2,4),(3,1887),
                          (4,NOW-timedelta(minutes=4)),
                          (4,NOW+timedelta(seconds=4)),(5,1),(6,1)):
            f,c,g,i=fixture();row=list(g[0]);row[pos]=value;g[0]=tuple(row)
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"Collector-to-grid"):
                q.assess(f,c,g,i)

    def test_missing_original_source_integrity_or_approval_blocks(self):
        for pos,value in ((1,""),(2,0),(3,None),(4,1)):
            f,c,g,i=fixture();row=list(c[0]);row[pos]=value;c[0]=tuple(row)
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"Collector-to-grid"):
                q.assess(f,c,g,i)

    def test_global_duplicate_future_factor_or_unsupported_approval_blocks(self):
        for pos in range(3):
            f,c,g,i=fixture();bad=list(i);bad[pos]=1
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"Future factor"):
                q.assess(f,c,g,tuple(bad))

    def test_venue_completeness_source_identity_and_no_future_claim(self):
        s=SRC.read_text()
        for token in ("arg_max(run_id,capture_received_at)","c.run_id=l.run_id",
                      "g.event_run_id=l.run_id","count(DISTINCT g.market_id)",
                      "institutional_quote_freshness_certified",
                      "exchange_quote_time_independently_verified",
                      "factor_ingested_at>event_capture_at",
                      "count(*) FILTER(WHERE g.factor_ingested_at>",
                      "INSTITUTIONAL_RELEASE=FALSE",
                      "LAB_RESEARCH_SCOPE"):
            self.assertIn(token,s)

if __name__=="__main__":
    unittest.main()
