"""Adversarial synthetic controls for shared-date bootstrap risk methodology.

All arrays are synthetic regression fixtures, not historical issuer returns,
provider market data, PIT-verified beta fits or investable portfolio estimates.
"""
from datetime import date, datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

LAB = Path(__file__).resolve().parents[1] / "lab"
spec=importlib.util.spec_from_file_location(
    "phase1_shared_date_holdout_bootstrap",
    LAB / "phase1_shared_date_holdout_bootstrap.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def sample(n=210, benefit=20.0):
    t=np.arange(n,dtype=float)
    # Identical common-day market shocks across every security.
    daily=np.sin(2*np.pi*t/21.0)*9.0
    cross=np.arange(48,dtype=float)[None,:]*.04
    base=np.tile(100+np.cos(2*np.pi*t/17.0)[:,None]*5,(1,48))
    improvement=benefit + daily[:,None] + cross
    joint=base-improvement
    days=[date(2026,1,2)+timedelta(days=int(x)) for x in t]
    tickers=[f"SEC{i:02d}" for i in range(48)]
    return tickers,days,date(2025,12,31),base,joint


class SharedDateHoldoutResearchTests(unittest.TestCase):
    def test_strong_paired_date_improvement_with_simultaneous_familywise_control(self):
        r=m.assess(*sample())
        self.assertEqual(r["security_count"],48)
        self.assertEqual(r["independent_date_count"],210)
        self.assertEqual(r["asset_date_records_not_independent_shocks"],10080)
        self.assertEqual(r["research_cells_with_simultaneous_lower_bound_above_zero"],48)
        self.assertEqual(r["research_cells_with_positive_heldout_skill"],48)
        self.assertGreater(r["cross_security_mean_block_bootstrap_ci95"][0],0)
        self.assertTrue(all(x["simultaneous_lower_bound"]>0 for x in r["security_diagnostics"]))
        self.assertFalse(r["institutional_risk_model_released"])
        self.assertFalse(r["original_issuer_price_vintages_verified"])
        self.assertFalse(r["funding_first_publication_pit_verified"])

    def test_same_macro_date_shared_by_48_assets_is_not_10080_independent_shocks(self):
        tickers,days,cutoff,base,joint=sample(210, benefit=0)
        # Make each asset's loss difference precisely the same common-day
        # function; preserving its cross-sectional dependence is essential.
        pure_common=9*np.sin(2*np.pi*np.arange(len(days))/21)
        joint=base-pure_common[:,None]
        r=m.assess(tickers,days,cutoff,base,joint)
        self.assertEqual(r["research_cells_with_simultaneous_lower_bound_above_zero"],0)
        self.assertLessEqual(abs(r["cross_security_mean_loss_improvement"]),1e-10)
        self.assertLess(r["cross_security_mean_block_bootstrap_ci95"][0],0)
        self.assertGreater(r["cross_security_mean_block_bootstrap_ci95"][1],0)
        iid_naive_se=float(np.std(pure_common,ddof=1)/np.sqrt(len(days)*48))
        self.assertGreater(r["cross_security_mean_block_bootstrap_se"],4*iid_naive_se)

    def test_common_date_bootstrap_seed_is_deterministic(self):
        a=m.assess(*sample())
        b=m.assess(*sample())
        self.assertEqual(a["simultaneous_max_t_critical"],b["simultaneous_max_t_critical"])
        self.assertEqual(a["cross_security_mean_block_bootstrap_ci95"],
                         b["cross_security_mean_block_bootstrap_ci95"])

    def test_one_worse_joint_security_fails_even_with_good_aggregate(self):
        args=list(sample())
        args[-1]=args[-1].copy()
        args[-1][:,0]=args[-2][:,0] + 15 + 4*np.sin(np.arange(210))
        r=m.assess(*args)
        bad=r["security_diagnostics"][0]
        self.assertLess(bad["incremental_holdout_skill"],0)
        self.assertLess(bad["simultaneous_lower_bound"],0)
        self.assertEqual(bad["statistical_research_screen_only"],
                         "REJECT_SHARED_DATE_FAMILYWISE_HOLDOUT_UNCERTAINTY")
        self.assertLess(r["research_cells_with_simultaneous_lower_bound_above_zero"],48)

    def test_duplicate_out_of_order_and_training_overlap_all_fail(self):
        for corrupt,match in (
            (lambda a: a[1].__setitem__(1,a[1][0]),"strictly ordered"),
            (lambda a: a[1].reverse(),"strictly ordered"),
            (lambda a: a.__setitem__(2,date(2026,1,2)),"strictly after"),
        ):
            args=list(sample())
            corrupt(args)
            with self.subTest(match=match),self.assertRaisesRegex(ValueError,match):
                m.assess(*args)

    def test_holdout_date_timestamps_not_naive_and_calendar_only(self):
        args=list(sample())
        args[1][0]=datetime(2026,1,2,0,0)
        with self.assertRaisesRegex(ValueError,"source|date|ordered"):
            m.assess(*args)

    def test_fewer_than_150_holdout_dates_fail(self):
        with self.assertRaisesRegex(ValueError,"Insufficient strictly ordered"):
            m.assess(*sample(149))

    def test_exact_48_security_stable_universe_and_order_required(self):
        args=list(sample())
        for tickers in (args[0][:-1],
                        args[0][1:]+[args[0][0]],
                        list(reversed(args[0])),
                        ["SPY"]+args[0][1:],
                        ["SEC00"]*48):
            with self.subTest(tickers=tickers[:2]),self.assertRaisesRegex(
                ValueError,"48 unique, sorted"):
                m.assess(tickers,*args[1:])

    def test_missing_nonnumeric_negative_and_future_losses_fail(self):
        for case in ("negative","nonfinite","badshape","nonfinite_base"):
            args=list(sample())
            args[-1]=args[-1].copy()
            if case=="negative":
                args[-1][0,0]=-1
            elif case=="nonfinite":
                args[-1][4,0]=float("nan")
            elif case=="badshape":
                args[-1]=args[-1][:-1]
            else:
                args[-2]=args[-2].copy()
                args[-2][0,0]=float("inf")
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,"Squared loss"):
                m.assess(*args)

    def test_degenerate_zero_baseline_denied(self):
        args=list(sample())
        args[-2]=args[-2].copy()
        args[-2][:,0]=0
        with self.assertRaisesRegex(ValueError,"Degenerate baseline"):
            m.assess(*args)

    def test_no_temporal_bootstrap_result_if_all_days_identical(self):
        args=list(sample())
        args[-2]=np.full((210,48),100.0)
        args[-1]=np.full((210,48),80.0)
        with self.assertRaisesRegex(ValueError,"Degenerate date-block"):
            m.assess(*args)

    def test_locked_prespecified_bootstrap_design_and_nonapproval(self):
        self.assertEqual(m.BLOCK_OBSERVATIONS,10)
        self.assertEqual(m.BOOT_RESAMPLES,500)
        self.assertEqual(m.BOOT_SEED,20261025)
        self.assertEqual(m.ASSETS,48)
        self.assertEqual(m.FAMILYWISE_ALPHA,.05)
        source=(LAB/"phase1_shared_date_holdout_bootstrap.py").read_text()
        self.assertIn("starts[:, None] + offsets[None, :]",source)
        self.assertIn("np.max(np.abs(centered / se[None, :]), axis=1)",source)
        self.assertNotIn("duckdb.connect",source)
        self.assertNotIn("CREATE TABLE",source)
        self.assertNotIn("INSTITUTIONAL_APPROVED",source)


if __name__=="__main__":
    unittest.main()
