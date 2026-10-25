"""Offline FF6 independent reconciliation and false risk-beta approval tests."""
from __future__ import annotations
from datetime import date,timedelta
import importlib.util
import math
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_ff6_metric_integrity_audit.py"
spec=importlib.util.spec_from_file_location("ff6_integrity",SRC)
qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def fixture():
    windows=[]
    coeff=[]
    for ticker_num in range(48):
        ticker=f"TICKER{ticker_num}"
        previous=None
        for ordinal in range(1,6):
            ts=date(2020,1,1)+timedelta(days=63*(ordinal-1))
            te=ts+timedelta(days=400)
            tst=te+timedelta(days=1)
            tend=tst+timedelta(days=62)
            beta=[1.0+(.7 if ordinal>1 and ticker_num==0 else 0.0)]+[.2]*5
            drift=(None if previous is None else
                   math.sqrt(sum((a-b)**2 for a,b in zip(beta,previous)))/
                   max(math.sqrt(sum(a*a for a in previous)),.25))
            bad=(ordinal==3 and ticker_num==1)
            rmse=24.0 if bad else 21.0
            benchmark=20.0
            flags=1 if ticker_num==2 and ordinal==2 else 0
            windows.append((ticker,ordinal,ts,te,tst,tend,378,63,70.0,
                            1-(rmse/benchmark)**2,rmse,benchmark,flags,drift,
                            drift is not None and drift>.5,
                            (rmse/benchmark)**2>1.25,False,False,False))
            for f,b in zip(qa.FACTORS,beta):
                coeff.append((ticker,ordinal,f,b,.015,False,False))
            previous=beta
    return windows,coeff


class FF6AuditTests(unittest.TestCase):
    def test_reconciled_chronology_and_flags(self):
        summaries=qa.evaluate(*fixture())
        self.assertEqual(len(summaries),48)
        self.assertEqual(sum(s[1] for s in summaries),240)
        self.assertEqual(sum(s[2] for s in summaries),1)
        self.assertEqual(sum(s[3] for s in summaries),1)
        self.assertEqual(sum(s[4] for s in summaries),1)
        self.assertTrue(summaries[0][6])

    def test_six_factor_drift_mismatch_rejected(self):
        a,b=fixture();row=list(a[1]);row[13]=.00001;a[1]=tuple(row)
        with self.assertRaisesRegex(ValueError,"shift"):
            qa.evaluate(a,b)

    def test_false_poor_holdout_review_flag_rejected(self):
        a,b=fixture();row=list(a[0]);row[15]=True;a[0]=tuple(row)
        with self.assertRaisesRegex(ValueError,"flag"):
            qa.evaluate(a,b)

    def test_wrong_holdout_rmse_identity_rejected(self):
        a,b=fixture();row=list(a[0]);row[9]=.99;a[0]=tuple(row)
        with self.assertRaisesRegex(ValueError,"R2"):
            qa.evaluate(a,b)

    def test_missing_or_duplicate_six_factor_coefficients_rejected(self):
        a,b=fixture()
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            qa.evaluate(a,b[:-1])
        with self.assertRaisesRegex(ValueError,"duplicate"):
            qa.evaluate(a,b+[b[-1]])

    def test_future_trained_window_fails_closed(self):
        a,b=fixture();row=list(a[0]);row[3]=row[4];a[0]=tuple(row)
        with self.assertRaisesRegex(ValueError,"future"):
            qa.evaluate(a,b)

    def test_unverified_security_and_source_approval_cannot_escape(self):
        for index in (16,17,18):
            a,b=fixture();row=list(a[0]);row[index]=True;a[0]=tuple(row)
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"verified"):
                qa.evaluate(a,b)
        a,b=fixture();row=list(b[0]);row[6]=True;b[0]=tuple(row)
        with self.assertRaisesRegex(ValueError,"authorized"):
            qa.evaluate(a,b)

    def test_invalid_hac_uncertainty_and_beta_rejected(self):
        for pos,value in [(3,float("nan")),(4,0.0),(4,-.2)]:
            a,b=fixture();row=list(b[0]);row[pos]=value;b[0]=tuple(row)
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"HAC"):
                qa.evaluate(a,b)


if __name__=="__main__":
    unittest.main()
