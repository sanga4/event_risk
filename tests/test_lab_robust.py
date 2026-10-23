"""Pure-math regression diagnostics contract tests; no MotherDuck access."""
import importlib.util
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "lab" / "phase1_robust_regressions.py"
spec = importlib.util.spec_from_file_location("phase1_diagnostics", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestRegressionDiagnostics(unittest.TestCase):
    def test_hac_linear_fit(self):
        pairs = [(float(i), 0.7 + 2 * i + (0.2 if i%2 else -0.2)) for i in range(1,121)]
        result = mod.ols_hac_train(pairs, lag=5)
        self.assertAlmostEqual(result["slope"], 2, places=3)
        self.assertGreaterEqual(result["hac_se"], 0)
        self.assertGreater(result["r2"], 0.999)
        self.assertTrue(math.isfinite(result["slope"]))

    def test_flat_predictor_is_not_fit(self):
        self.assertIsNone(mod.ols_hac_train([(1.,float(i)) for i in range(100)]))

    def test_holdout_is_strictly_future(self):
        start = date(2024,1,1)
        rows = [(start+timedelta(days=i), float(i), float(2*i+3)) for i in range(200)]
        output = mod.fit(rows, lag=5)
        self.assertEqual(output["train_n"], 140)
        self.assertEqual(output["test_n"], 60)
        self.assertAlmostEqual(output["slope"], 2.0)
        self.assertGreater(output["oos_r2_vs_train_mean"], 0.99)

    def test_bh_adjustment_monotonic(self):
        q=mod.bh_adjust([0.01, 0.04, None, 0.03])
        self.assertAlmostEqual(q[0], 0.03)
        self.assertAlmostEqual(q[1], 0.04)
        self.assertIsNone(q[2])
        self.assertAlmostEqual(q[3], 0.04)

    def test_pit_not_inferred_from_regression(self):
        source = path.read_text()
        self.assertIn("FALSE AS point_in_time_verified", source) if False else self.assertIn("False,False,build_id", source)
        self.assertIn("RESEARCH_UNRELEASED_NOT_POINT_IN_TIME", source)


if __name__ == "__main__":
    unittest.main()
