"""Offline institutional walk-forward covariance and outlier counterfactual controls."""
from __future__ import annotations
from datetime import date,timedelta
import importlib.util,math,sys,unittest
from pathlib import Path
import numpy as np

LAB=Path(__file__).resolve().parents[1]/"lab"
def loader(path,name):
    s=importlib.util.spec_from_file_location(name,LAB/path)
    m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m)
    return m

cov=loader("phase1_regime_cov_walkforward.py","walk_regime_cov")
ex=loader("phase1_ff6_extreme_return_sensitivity.py","ff6_outlier_review")

class RegimeWalkForwardTests(unittest.TestCase):
    def test_all_predeclared_models_are_psd_and_scale_training_only(self):
        rng=np.random.default_rng(21)
        sample=rng.standard_normal((cov.TRAIN,7))*np.array([20,4,7,35,70,55,25])
        for name,typ,lam,shrink in cov.METHODS:
            mu,sd,C,cond=cov.fit_covariance(sample,typ,lam,shrink)
            self.assertEqual(mu.shape,(7,))
            self.assertTrue(np.all(np.linalg.eigvalsh(C)>0))
            self.assertGreater(cond,0)
            score,maxz,q=cov.score_one(sample[-1],mu,sd,C)
            self.assertTrue(math.isfinite(score))
            self.assertGreaterEqual(q,0)
            self.assertTrue(math.isfinite(maxz))
        self.assertEqual(len(cov.METHODS),4)
        self.assertEqual(cov.TRAIN,252)

    def test_bootstrap_paired_loss_no_hindsight_and_valid_bounds(self):
        v=np.full(150,.28)
        lo,hi=cov.paired_block_ci(v)
        self.assertAlmostEqual(lo,.28,places=9)
        self.assertAlmostEqual(hi,.28,places=9)
        neg=np.full(150,-.40)
        lo,hi=cov.paired_block_ci(neg)
        self.assertLess(hi,0)
        self.assertIn("source_historic_publication_asof_verified",
                      (LAB/"phase1_regime_cov_walkforward.py").read_text())

    def test_reject_nonfinite_and_zero_variance_covariances(self):
        with self.assertRaises(ValueError):
            cov.fit_covariance(np.ones((252,7)),"equal",0,.1)
        with self.assertRaises(ValueError):
            cov.fit_covariance(np.full((252,7),np.nan),"equal",0,.1)


class OutlierBetaCounterfactualTests(unittest.TestCase):
    def prepare(self,inject=False):
        rows=[]
        for k in range(500):
            fs=[60*math.sin(.17*k),22*math.cos(.29*k),
                20*math.sin(.23*k),15*math.cos(.37*k),
                13*math.sin(.47*k),11*math.cos(.53*k)]
            y=6+sum(t*x for t,x in zip([1.2,.4,-.3,.7,-.15,.8],fs))
            y+=.3*math.sin(.61*k)
            flagged=inject and k==100
            if flagged:y+=2800
            rows.append((date(2024,1,1)+timedelta(days=k),y,*fs,flagged))
        return rows

    def test_no_flagged_training_days_identical_fit(self):
        m=ex.compare(self.prepare())
        self.assertIsNotNone(m)
        self.assertEqual(m["flagged_train"],0)
        self.assertEqual(m["flagged_holdout"],0)
        self.assertAlmostEqual(m["relative_beta_shift"],0,places=10)
        self.assertAlmostEqual(m["holdout_sse_change_ratio"],1,places=8)

    def test_training_outlier_can_move_betas_but_is_never_changed(self):
        rows=self.prepare(True)
        orig=rows[100]
        m=ex.compare(rows)
        self.assertIsNotNone(m)
        self.assertEqual(m["flagged_train"],1)
        self.assertGreater(m["relative_beta_shift"],.01)
        self.assertEqual(rows[100],orig)
        self.assertEqual(m["holdout"],150)
        self.assertIn("SOURCE_PRICES_DELETED=0",
                      (LAB/"phase1_ff6_extreme_return_sensitivity.py").read_text())

    def test_invalid_or_unmodeled_data_fails_closed(self):
        self.assertIsNone(ex.compare(self.prepare()[:200]))
        self.assertIn("licensed_institutional_beta_approved",
                      (LAB/"phase1_ff6_extreme_return_sensitivity.py").read_text())

if __name__=="__main__":unittest.main()
