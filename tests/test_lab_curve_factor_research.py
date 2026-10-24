"""Deterministic synthetic tests for curve-maturity factor research methodology."""
import importlib.util
import math
from pathlib import Path
import unittest
from datetime import date, timedelta

import numpy as np

PATH = Path(__file__).resolve().parents[1] / "lab" / "phase1_curve_factor_research.py"
spec = importlib.util.spec_from_file_location("curve_factor_research", PATH)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class CurveResearchTests(unittest.TestCase):
    def test_known_exposures_recovered_under_correlated_yields(self):
        data = []
        for n in range(500):
            dt = date(2024,1,1) + timedelta(days=n)
            spy=90*math.sin(n*.29) + 30*math.cos(n*.13)
            lev=4.0*math.sin(n*.12) + 2*math.cos(n*.09)
            slp=2.7*math.cos(n*.21)
            crv=1.3*math.sin(n*.33)
            # Both covariances and level changes have units of basis points.
            noise=0.8*math.sin(n*.63)
            y=5.0+1.3*spy-4.2*lev+2.6*slp-0.8*crv+noise
            data.append((dt,y,spy,lev,slp,crv,False))
        result=model.fit_curve(data)
        self.assertIsNotNone(result)
        self.assertEqual(result["train"],350)
        self.assertEqual(result["test"],150)
        np.testing.assert_allclose(
            result["beta"],[5,1.3,-4.2,2.6,-0.8],
            atol=0.10
        )
        self.assertGreater(result["test_r2_vs_spy"],0.95)
        self.assertLess(result["train_condition"],1000)
        self.assertTrue(all(z >= 0 for z in result["se"]))

    def test_rejects_singular_or_short_training(self):
        short=[]
        bad=[]
        for i in range(360):
            d=date(2024,1,1)+timedelta(days=i)
            x=math.sin(i*.23)
            v=(d,3+2*x,x,x,x,2*x,False)
            bad.append(v)
            if i < 220:
                short.append(v)
        self.assertIsNone(model.fit_curve(short))
        self.assertIsNone(model.fit_curve(bad))

    def test_predeclared_global_bh_family_includes_nonsignificant(self):
        q=model.bh_adjust([.01,.2,.001,None,.8])
        self.assertAlmostEqual(q[2],.004)
        self.assertAlmostEqual(q[0],.02)
        self.assertIsNone(q[3])
        self.assertGreater(q[1],.05)

    def test_source_units_and_no_institutional_release(self):
        code=PATH.read_text()
        self.assertIn("(y2+y5+y10)/3.0", code)
        self.assertIn("(y10-y2)", code)
        self.assertIn("(2*y5-y2-y10)", code)
        self.assertIn("MAX_STANDARDIZED_CONDITION", code)
        self.assertIn("INSTITUTIONAL_BETA_RELEASED=FALSE", code)
        self.assertIn("EX_POST_MULTIFACTOR_CURVE_RESEARCH_NOT_PIT", code)
        self.assertNotIn("DELETE FROM eventrisk_factor_lab",code)


if __name__ == "__main__":
    unittest.main()
