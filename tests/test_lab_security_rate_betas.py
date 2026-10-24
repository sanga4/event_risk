"""Offline research beta estimator tests; no credentials or network calls."""
from __future__ import annotations

import importlib.util
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "lab" / "phase1_security_rate_beta_backfill.py"
spec = importlib.util.spec_from_file_location("security_rate_model", SCRIPT)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class SecurityRateRetrospectiveTests(unittest.TestCase):
    def test_correct_rate_beta_controlled_for_market(self):
        day = date(2024,1,2)
        rows=[]
        for i in range(420):
            m = math.sin(i * 0.43) * 80 + (i % 9) * 2
            x = math.sin(i * 0.27 + .2) * 7 + .15*m
            noise=0.3*math.sin(i*.73)
            y=12+1.15*m-3.25*x+noise
            rows.append(("TEST",day+timedelta(days=i),y,m,x,False))
        result=model.fit_regression(rows)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["slope"],-3.25,places=2)
        self.assertAlmostEqual(result["market_beta"],1.15,places=2)
        self.assertEqual(result["train"],294)
        self.assertEqual(result["test"],126)
        self.assertGreater(result["oos_r2_vs_market_only"],.99)
        self.assertGreaterEqual(result["hac_se"],0)

    def test_singular_factor_or_market_refused(self):
        d=date(2024,1,1)
        flat_market=[("T",d+timedelta(days=i),float(i),0.,float(i),False)
                     for i in range(350)]
        flat_factor=[("T",d+timedelta(days=i),float(i),float(i),float(i),False)
                     for i in range(350)]
        self.assertIsNone(model.fit_regression(flat_market))
        self.assertIsNone(model.fit_regression(flat_factor))

    def test_short_series_refused(self):
        d=date(2024,1,1)
        rows=[("T",d+timedelta(days=i),float(i),float(i%7),float(i%13),False)
              for i in range(180)]
        self.assertIsNone(model.fit_regression(rows))

    def test_fdr_counts_all_hypotheses(self):
        q=model.bh_adjust([.01,.05,.001,None,.5])
        self.assertIsNone(q[3])
        self.assertAlmostEqual(q[2],.004)
        self.assertAlmostEqual(q[0],.02)
        self.assertGreaterEqual(q[1],.05)

    def test_never_approves_research_beta(self):
        c=SCRIPT.read_text()
        self.assertIn("published_vintage_independently_verified",c)
        self.assertIn("corporate_action_vintage_verified",c)
        self.assertIn("EX_POST_MARKET_CONTROLLED_SENSITIVITY_NOT_PIT",c)
        self.assertIn("INSTITUTIONALLY_VALIDATED_BETAS=0",c)
        self.assertIn("SPY",c)


if __name__ == "__main__":
    unittest.main()
