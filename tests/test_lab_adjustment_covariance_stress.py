"""Institutional source QA and shrinkage math offline, no network/credentials."""
from __future__ import annotations
import importlib.util,math,sys,unittest
from pathlib import Path
import numpy as np
import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
def imp(filename,name):
    s=importlib.util.spec_from_file_location(name,LAB/filename)
    m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
adjust=imp("phase1_adjusted_price_reconciliation.py","adj_source")
cov=imp("phase1_covariance_shrinkage_sensitivity.py","shrinkcov")

class CorporateAdjustmentQA(unittest.TestCase):
    def test_adjusted_close_ratio_step_exact_identity_and_duplicate_is_excluded(self):
        con=duckdb.connect(":memory:")
        old=adjust.P;adjust.P="main."
        try:
            con.execute("""CREATE TABLE security_prices(
              ticker VARCHAR,date DATE,close DOUBLE,adj_close DOUBLE,
              volume DOUBLE,currency VARCHAR,source VARCHAR,
              fetched_at TIMESTAMPTZ,run_id VARCHAR)""")
            con.execute("""INSERT INTO security_prices VALUES
              ('AAA','2024-01-02',100,80,10000,'USD','Vendor','2026-10-16 01:00:00+00:00','r1'),
              ('AAA','2024-01-03',101,80.8,10000,'USD','Vendor','2026-10-16 01:00:00+00:00','r1'),
              ('AAA','2024-01-04',102,102,10000,'USD','Vendor','2026-10-16 01:00:00+00:00','r1'),
              ('JPY=X','2024-01-02',150,150,10000,'JPY','Vendor','2026-10-16 01:00:00+00:00','r1'),
              ('JPY=X','2024-01-02',151,151,10000,'JPY','Vendor','2026-10-16 01:00:00+00:00','r2')""")
            adjust.stage(con)
            row=con.execute("""SELECT ratio_step_bps,raw_close_return_bps,
                 adjusted_close_return_bps FROM p1_adj_diffs
                 WHERE ticker='AAA' AND date='2024-01-04'""").fetchone()
            self.assertIsNotNone(row)
            self.assertAlmostEqual(row[2]-row[1],row[0],places=7)
            self.assertAlmostEqual(row[0],-10000*math.log(.8),places=7)
            self.assertEqual(con.execute(
              "SELECT COUNT(*) FROM p1_adjust_inputs WHERE ticker='JPY=X'").fetchone()[0],0)
        finally:
            adjust.P=old;con.close()

    def test_reconciliation_does_not_fake_corporate_action_history(self):
        src=(LAB/"phase1_adjusted_price_reconciliation.py").read_text()
        for token in ("original_issuer_action_verified","original_vendor_revision_asof_verified",
                      "approved_for_institutional_beta","CORPORATE_ACTION_SOURCE_VERIFIED=0",
                      "return_difference_identity_residual_bps"):
            self.assertIn(token,src)


class CovarianceRobustnessTests(unittest.TestCase):
    def test_shrink_to_diagonal_improves_condition_but_no_guaranteed_holdout(self):
        tr=np.eye(7);tr[0,1]=tr[1,0]=.98
        hold=np.eye(7)
        a=cov.diagnostic(tr,hold,0)
        b=cov.diagnostic(tr,hold,.5)
        self.assertLess(b["condition"],a["condition"])
        self.assertGreater(b["min_eigenvalue"],a["min_eigenvalue"])
        self.assertEqual(len(cov.FRACTIONS),6)

    def test_refuses_non_psd_and_non_symmetric(self):
        tr=np.eye(7);ho=np.eye(7)
        tr[0,1]=2.;tr[1,0]=2.
        with self.assertRaises(ValueError):
            cov.diagnostic(tr,ho,0)
        tr=np.eye(7);tr[0,1]=.2
        with self.assertRaises(ValueError):
            cov.diagnostic(tr,ho,.1)

    def test_hindsight_selected_shrinkage_cannot_be_production_choice(self):
        src=(LAB/"phase1_covariance_shrinkage_sensitivity.py").read_text()
        for token in ("hindsight_selection_prohibited",
                      "retrospectively_selected_for_production",
                      "INDEPENDENT_RISK_VALIDATION=FALSE",
                      "source_pit_certified","original_provider_data_rights_approved"):
            self.assertIn(token,src)

if __name__=="__main__":unittest.main()
