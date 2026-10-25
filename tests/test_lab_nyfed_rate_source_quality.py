"""NYFed revision/source integrity, stress outliers and PIT-release safeguards."""
import importlib.util
from datetime import date
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"lab"/"phase1_nyfed_rate_source_quality.py"
spec=importlib.util.spec_from_file_location("rate_qa",SOURCE)
qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

def fixture():
    summaries=[
        ("EFFR",2150,date(2018,4,2),date(2026,10,22),2,250,0,4,85.0,0),
        ("SOFR",2138,date(2018,4,2),date(2026,10,22),2,250,0,10,282.0,0)]
    totals=(4788,4288,0,0,0)
    return summaries,totals

class HistoricalNYFedRateQuality(unittest.TestCase):
    def test_real_source_counts_overlap_and_outlier_classification(self):
        a=qa.validate(*fixture())
        self.assertEqual(len(a),2)
        self.assertEqual(sum(x[1] for x in a),4288)
        self.assertEqual(sum(x[5] for x in a),500)
        self.assertTrue(all("UNVERIFIED" in x[-1] for x in a))
        self.assertEqual(next(x for x in a if x[0]=="SOFR")[8],282.0)

    def test_record_count_and_vintage_identity_drift_fails_closed(self):
        for pos,val in ((0,100),(1,0),(2,1),(3,1),(4,1)):
            s,t=fixture();t=list(t);t[pos]=val
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"source identity"):
                qa.validate(s,tuple(t))

    def test_duplicate_or_missing_rate_series(self):
        s,t=fixture()
        with self.assertRaisesRegex(ValueError,"Missing or duplicate"):
            qa.validate(s[:-1],t)
        s,t=fixture();s[1]=s[0]
        with self.assertRaisesRegex(ValueError,"Missing or duplicate"):
            qa.validate(s,t)

    def test_incomplete_history_and_false_approval(self):
        for index,value in ((1,200),(2,date(2021,1,1)),
                            (3,date(2021,1,1)),(5,-1),(6,251),
                            (7,-1),(8,-3.0),(9,1)):
            s,t=fixture();r=list(s[0]);r[index]=value;s[0]=tuple(r)
            with self.subTest(field=index),self.assertRaisesRegex(ValueError,"Incomplete"):
                qa.validate(s,t)

    def test_revision_candidates_are_not_automatically_approved_or_hidden(self):
        s,t=fixture();x=list(s[0]);x[6]=3;s[0]=tuple(x)
        out=qa.validate(s,t)
        self.assertEqual(out[0][6],3)
        self.assertIn("REQUIRES_SOURCE_REVIEW",out[0][-1])

    def test_identical_prior_downloads_not_independent_source_dates(self):
        source=SOURCE.read_text()
        self.assertIn("PARTITION BY series_id,effective_date",source)
        self.assertIn("source_response_received_at DESC",source)
        self.assertIn("count(DISTINCT annual_rate_percent)",source)
        self.assertIn("original_provider_published_at IS NOT NULL",source)
        self.assertIn("lab_nyfed_rate_levels_latest_retro_v1",source)

    def test_sofr_funding_stress_not_assumed_policy_surprise(self):
        source=SOURCE.read_text()
        self.assertIn("STRESS_JUMP_BPS=50.0",source)
        self.assertIn("FALSE,FALSE",source)
        self.assertIn("CAUSAL_BETA_RELEASE=FALSE",source)

if __name__=="__main__":
    unittest.main()
