"""Synthetic mathematical checks for retrospective US 6-factor research model."""
from __future__ import annotations
from datetime import date,timedelta
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np

PATH=Path(__file__).resolve().parents[1]/"lab"/"phase1_ff6_security_research.py"
spec=importlib.util.spec_from_file_location("sixfactor",PATH)
six=importlib.util.module_from_spec(spec)
spec.loader.exec_module(six)


class US6FactorModelTests(unittest.TestCase):
    def test_recovers_six_simple_return_exposures(self):
        rows=[]
        true=[5.,1.1,-.6,.7,.35,-.45,.85]
        d0=date(2024,1,1)
        for i in range(440):
            factors=[
                80*math.sin(.23*i),
                25*math.sin(.18*i+.1),
                18*math.cos(.11*i),
                13*math.sin(.37*i),
                11*math.cos(.49*i),
                23*math.cos(.28*i),
            ]
            y=sum(b*x for b,x in zip(true,[1,*factors]))+.03*math.sin(.71*i)
            rows.append((d0+timedelta(days=i),y,*factors,False))
        o=six.fit_ff6(rows)
        self.assertIsNotNone(o)
        np.testing.assert_allclose(o["b"],true,atol=.03)
        self.assertEqual(o["train"],308)
        self.assertEqual(o["test"],132)
        self.assertGreater(o["holdout_r2"],.99)
        self.assertLess(o["condition"],1000)
        self.assertTrue(all(v>=0 for v in o["se"]))

    def test_rejects_singular_and_short_training(self):
        start=date(2024,1,1)
        rows=[]
        for i in range(340):
            x=math.sin(.11*i)
            rows.append((start+timedelta(days=i),x,x,x,x,x,x,x,False))
        self.assertIsNone(six.fit_ff6(rows))
        self.assertIsNone(six.fit_ff6(rows[:120]))

    def test_fdr_includes_entire_coefficient_family(self):
        q=six.bh_adjust([.01,.2,.001,None,.8])
        self.assertAlmostEqual(q[2],.004)
        self.assertAlmostEqual(q[0],.02)
        self.assertIsNone(q[3])

    def test_distinguish_security_simple_excess_and_factor_return_units(self):
        src=PATH.read_text()
        self.assertIn("EXP(a.return_bps/10000.0)-1.0-f.rf",src)
        self.assertIn("10000.0*f.mkt",src)
        self.assertIn("FF_US_RF",src)
        self.assertIn("LAB_RESEARCH_SCOPE",src)
        self.assertIn("LICENSED_PRODUCTION_SECURITY_BETAS=0",src)
        self.assertIn("RETROSPECTIVE_FF6_EXPLANATORY_NOT_PIT_OR_LICENSED",src)


if __name__=="__main__":
    unittest.main()
