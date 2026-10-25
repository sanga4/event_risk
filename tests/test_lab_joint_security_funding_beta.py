"""Adversarial joint market/rate/funding security beta methodology contracts."""
from datetime import date,timedelta
from pathlib import Path
import importlib.util
import unittest
import numpy as np

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_joint_security_funding_beta.py"
spec=importlib.util.spec_from_file_location("joint_security_funding",SRC)
j=importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)

def factors(seed=4,n=650):
    r=np.random.default_rng(seed)
    market=r.normal(0,80,n)
    rate2=r.normal(0,5,n)
    rate10=.75*rate2+r.normal(0,3,n)
    basis=r.normal(0,2.4,n)
    x=np.column_stack((market,rate2,rate10,basis))
    y=1.0*market-.6*rate2+.2*rate10+4*basis+r.normal(0,15,n)
    return x,y

class JointExposureTests(unittest.TestCase):
    def test_genuine_joint_exposure_and_hac_interval(self):
        x,y=factors()
        a=j.model_fit(x[:455],y[:455],x[455:],y[455:])
        self.assertEqual(a["research_status"],"RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL")
        self.assertGreater(a["funding_beta"],2)
        self.assertLess(a["funding_beta"],6)
        self.assertGreater(a["funding_hac_se"],0)
        self.assertLess(a["condition"],j.MAX_STANDARDIZED_CONDITION)
        self.assertTrue(a["sign_stable"])
        self.assertLess(a["ci_low"],a["funding_beta"])
        self.assertGreater(a["ci_high"],a["funding_beta"])
        self.assertGreater(a["incremental_skill"],0)

    def test_perfect_rate_collinearity_blocks_model(self):
        x,y=factors()
        x[:,2]=x[:,1]*2
        with self.assertRaisesRegex(ValueError,"collinearity"):
            j.model_fit(x[:455],y[:455],x[455:],y[455:])

    def test_nonfinite_or_short_dates_block(self):
        x,y=factors()
        x[2,1]=float("nan")
        with self.assertRaisesRegex(ValueError,"Invalid independent"):
            j.model_fit(x[:455],y[:455],x[455:],y[455:])
        x,y=factors()
        with self.assertRaisesRegex(ValueError,"Invalid independent"):
            j.model_fit(x[:200],y[:200],x[200:],y[200:])

    def test_external_vendor_or_time_approval_fails(self):
        src=(83427,48,1705,1402,2138,0,0)
        matched=(33360,48,695,0,0)
        self.assertTrue(j.check_source(src,matched))
        for pos in (1,3,4,5,6):
            vals=list(src)
            vals[pos]=1 if pos in (5,6) else 0
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"Unapproved"):
                j.check_source(tuple(vals),matched)
        for pos in (1,2,3,4):
            vals=list(matched)
            vals[pos]=1 if pos in (3,4) else 0
            with self.subTest(matched=pos),self.assertRaisesRegex(ValueError,"Unapproved"):
                j.check_source(src,tuple(vals))

    def test_all_48_securities_share_date_sample_but_not_independent_shocks(self):
        x,y=factors(n=650)
        start=date(2024,1,1)
        rows=[]
        for ticker in range(48):
            for k in range(650):
                rows.append((f"ASSET{ticker:02d}",start+timedelta(days=k),
                    float(y[k]+ticker*.01),*(float(v) for v in x[k]),
                    k==10 or k==95,0))
        # User-visible research stats must preserve both prespecified fits.
        fits=j.compute_all(rows)
        self.assertEqual(len(fits),96)
        self.assertEqual(len({q["ticker"] for q in fits}),48)
        self.assertEqual({q["variant"] for q in fits},set(j.VARIANTS))
        self.assertEqual({q["n_holdout"] for q in fits},{195})
        self.assertEqual({q["holdout_first"] for q in fits},
                         {start+timedelta(days=455)})
        self.assertEqual({q["excluded_train"] for q in fits if q["variant"]=="full_training"},{0})
        self.assertTrue(all(q["excluded_train"]>=2 for q in fits
                        if q["variant"]=="training_tail_exclusion"))
        self.assertTrue(all(q["research_status"].startswith(
            ("RESEARCH_SCREEN_PASS","REJECT_")) for q in fits))

    def test_duplicate_return_day_and_hidden_approval_fail(self):
        x,y=factors(n=650)
        start=date(2024,1,1)
        sample=[("TEST",start+timedelta(days=i),float(y[i]),
                *(float(v) for v in x[i]),False,0) for i in range(650)]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            j.compute_all(sample+[sample[0]])
        modified=list(sample[0]);modified[-1]=1
        with self.assertRaisesRegex(ValueError,"false PIT"):
            j.compute_all([tuple(modified)]+sample[1:])

    def test_no_unapproved_institutional_release_and_provenance_mutation(self):
        code=SRC.read_text()
        for phrase in ("RETROSPECTIVE_MULTI_FACTOR_RESEARCH_ONLY",
                       "HAC_LAGS = 5","MAX_STANDARDIZED_CONDITION = 30.0",
                       "source_availability_pit_verified",
                       "corporate_action_vintage_verified",
                       "source_record_sha256",
                       "training_tail_exclusion",
                       "FALSE,FALSE,FALSE,FALSE",
                       "INSTITUTIONAL_BETA=FALSE"):
            self.assertIn(phrase,code)
        self.assertIn("WHERE factor_id IN ('DGS2','DGS10')",code)
        self.assertNotIn("DROP TABLE",code)

if __name__=="__main__":
    unittest.main()
