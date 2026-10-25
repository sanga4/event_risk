"""Mathematical invariants: rolling six-factor beta, source evidence requirements."""
from __future__ import annotations
import importlib.util,math,sys,unittest
from datetime import date,timedelta
from pathlib import Path
import numpy as np
LAB=Path(__file__).resolve().parents[1]/"lab"

def imp(path,name):
    spec=importlib.util.spec_from_file_location(name,LAB/path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m

m=imp("phase1_ff6_beta_rolling_stability.py","rolling_beta")
e=imp("phase1_independent_evidence_requirements.py","source_evidence")


class RollingSixFactorResearchTests(unittest.TestCase):
    def test_recover_multivariate_six_factor_slopes(self):
        data=[]
        for i in range(m.TRAIN+m.TEST):
            fs=[45*math.sin(.13*i),25*math.cos(.21*i),13*math.sin(.32*i),
                19*math.cos(.41*i),14*math.sin(.51*i),9*math.cos(.61*i)]
            target=[1.0,.5,-.3,.8,-.25,.5]
            y=5+sum(b*x for b,x in zip(target,fs))+.25*math.sin(.77*i)
            data.append((date(2024,1,1)+timedelta(days=i),y,*fs,False))
        fit=m.train_window(data)
        self.assertIsNotNone(fit)
        np.testing.assert_allclose(fit["betas"],target,atol=.035)
        self.assertGreater(fit["holdout_r2_vs_market"],.95)
        self.assertLess(fit["condition"],m.MAX_CONDITION)
        self.assertTrue(all(v>=0 for v in fit["se"]))

    def test_training_only_numerical_safeguards(self):
        data=[]
        for i in range(m.TRAIN+m.TEST):
            x=math.sin(i*.17)
            data.append((date(2024,1,1)+timedelta(days=i),x,x,x,x,x,x,x,False))
        self.assertIsNone(m.train_window(data))
        with self.assertRaises(ValueError):
            m.train_window(data[:-1])
        self.assertEqual(m.TRAIN,378);self.assertEqual(m.TEST,63)
        self.assertEqual(m.STEP,63)

    def test_no_source_pit_or_license_certification(self):
        code=(LAB/"phase1_ff6_beta_rolling_stability.py").read_text()
        for word in ("security_original_corporate_actions_verified",
                     "licensed_beta_for_portfolio_risk",
                     "INSTITUTIONAL_BETA_APPROVED=FALSE",
                     "10000.0*(EXP(a.return_bps/10000.0)-1-f.rf)"):
            self.assertIn(word,code)


class EvidenceReviewWorklistTests(unittest.TestCase):
    def test_stable_content_identifiers_and_unapproved_review(self):
        a=e.key("ADJUSTED_PRICE_EXCURSION","INTC:2024-08-02","original_unadjusted_exchange_close")
        b=e.key("ADJUSTED_PRICE_EXCURSION","INTC:2024-08-02","original_unadjusted_exchange_close")
        c=e.key("ADJUSTED_PRICE_EXCURSION","INTC:2024-08-02","split_dividend_adjustment_asof")
        self.assertEqual(a,b);self.assertNotEqual(a,c)
        self.assertEqual(len(a),32)
        self.assertGreater(len(e.REQUIRED_MAPPING),2)
        self.assertGreater(len(e.REQUIRED_PRICE),3)

    def test_no_self_approval_or_fabricated_provider_evidence(self):
        s=(LAB/"phase1_independent_evidence_requirements.py").read_text()
        for word in ("original_source_uri","source_archived_sha256","second_approved_at",
                     "institutional_risk_use_approved","VERIFIED_ORIGINAL_SOURCE_ITEMS=0"):
            self.assertIn(word,s)
        self.assertNotIn("UPDATE eventrisk_factor_lab.main.lab_evidence",s)


if __name__=="__main__":
    unittest.main()
