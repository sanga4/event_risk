"""Offline contracts for mixed-unit train-only factor-risk covariance."""
from __future__ import annotations
from pathlib import Path
import sys
import importlib.util
import unittest
import numpy as np

LAB=Path(__file__).resolve().parents[1]/"lab"
sp=importlib.util.spec_from_file_location("crosscov",LAB/"phase1_cross_asset_covariance_research.py")
m=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=m
sp.loader.exec_module(m)

class CrossAssetCovTests(unittest.TestCase):
    def test_train_normalization_and_diagonal_shrinkage_psd(self):
        rng=np.random.default_rng(713)
        n=480
        common=rng.normal(size=(n,3))
        factor=rng.normal(size=(3,7))*0.5
        raw=(common@factor+rng.normal(size=(n,7))*.65)
        raw=raw*np.array([20,7,3,80,100,55,45])
        mean,scale,c,shrink,mineig,cond=m.covariance_estimator(raw)
        self.assertEqual(c.shape,(7,7))
        self.assertTrue(np.allclose(np.diag(c),np.ones(7),atol=1e-9))
        self.assertTrue(np.allclose(shrink,shrink.T))
        self.assertTrue(np.all(np.linalg.eigvalsh(shrink)>0))
        self.assertGreater(mineig,0)
        self.assertLess(cond,1000)
        self.assertGreater(max(scale),1)

    def test_small_or_constant_dataset_refused(self):
        rng=np.random.default_rng(3)
        short=rng.standard_normal((350,7))
        with self.assertRaises(ValueError):
            m.covariance_estimator(short)
        flat=np.ones((400,7))
        with self.assertRaises(ValueError):
            m.covariance_estimator(flat)

    def test_no_portfolio_model_false_approval(self):
        code=(LAB/"phase1_cross_asset_covariance_research.py").read_text()
        for s in ("SOURCE_PIT_AND_LICENSE_GOVERNANCE=BLOCKED",
                  "RELEASED_INSTITUTIONAL_FACTOR_COVARIANCE=FALSE",
                  "train_only_center_a",
                  "approved_portfolio_risk_covariance",
                  "FF_US_MKT_RF_RETURN_BPS","ECB_EUR_USD_QUOTE_BPS"):
            self.assertIn(s,code)

if __name__=="__main__":
    unittest.main()
