"""Synthetic negative controls for post-materialization joint-beta daily loss QA.

No real issuer prices, MotherDuck credentials or institutional model approval.
The fixed synthetic 48x2x160 daily loss history is ONLY an offline test fixture.
"""
from datetime import date,timedelta
import importlib.util
from pathlib import Path
import sys
import unittest
from copy import deepcopy
import math
import numpy as np

LAB=Path(__file__).resolve().parents[1]/"lab"
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location(
    "phase1_daily_loss_build_acceptance",LAB/"phase1_daily_loss_build_acceptance.py")
a=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=a
spec.loader.exec_module(a)

COMMIT="a"*40
CODE="b"*64
ORIGINAL="c"*64
SOURCE="d"*64
BUILD="synthetic-ci-research-build-not-actual"
PARENT="source-parent-ci-fixture"


def fixed_bundle():
    tickers=[f"SEC{i:02d}" for i in range(48)]
    days=[date(2026,1,1)+timedelta(days=i) for i in range(160)]
    cutoff=date(2025,12,31)
    actual=[]
    summary=[]
    parents=[]
    variants=("full_training","training_tail_exclusion")
    for v in variants:
        baseline=np.empty((160,48),dtype=float)
        joint=np.empty_like(baseline)
        for day_i,day in enumerate(days):
            for asset_i,ticker in enumerate(tickers):
                baseline[day_i,asset_i]=110+8*math.sin(day_i/9)+asset_i*.1
                joint[day_i,asset_i]=(baseline[day_i,asset_i]
                    -6+3*math.cos(day_i/11+asset_i*.004))
                actual.append((BUILD,PARENT,ticker,v,day,cutoff,0.0,
                    -math.sqrt(baseline[day_i,asset_i]),
                    -math.sqrt(joint[day_i,asset_i]),
                    baseline[day_i,asset_i],joint[day_i,asset_i],0))
        report=a.bootstrap.assess(tickers,days,cutoff,baseline,joint)
        summary.append((BUILD,PARENT,v,160,
            report["research_cells_with_simultaneous_lower_bound_above_zero"],
            report["simultaneous_max_t_critical"],
            report["cross_security_mean_loss_improvement"],
            *report["cross_security_mean_block_bootstrap_ci95"],0))
        for k,ticker in enumerate(tickers):
            parents.append((ticker,v,160,cutoff,days[0],days[-1],
                            float(baseline[:,k].mean()),
                            float(joint[:,k].mean()),0))
    manifest=(BUILD,COMMIT,CODE,PARENT,len(actual),2,48,160,
              False,False,False,False,a.DISPOSITION)
    parent_build=(PARENT,ORIGINAL,SOURCE,0)
    return (manifest,parent_build,parents,actual,summary,COMMIT,CODE)


class DailyLossAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good=fixed_bundle()

    def review(self,bundle):
        return a.verify(*bundle)

    def test_happy_synthetic_build_checks_all_daily_losses_and_bootstrap_summaries(self):
        result=self.review(self.good)
        self.assertEqual(result["status"],a.STATE)
        self.assertEqual(result["daily_security_variant_observations"],15360)
        self.assertEqual(result["security_assets"],48)
        self.assertEqual(result["variants"],2)
        self.assertEqual(result["common_holdout_dates"],160)
        self.assertFalse(result["institutional_beta_released"])
        self.assertFalse(result["original_publisher_pit_verified"])
        self.assertEqual(set(result["shared_date_bootstrap_result"]),
                         a.VARIANTS)

    def assert_bad(self,transform,pattern):
        bundle=list(deepcopy(self.good))
        transform(bundle)
        with self.assertRaisesRegex(ValueError,pattern):
            self.review(bundle)

    def test_wrong_git_source_code_or_parent_provenance_rejected(self):
        self.assert_bad(lambda b:b.__setitem__(5,"e"*40),"producer identity")
        self.assert_bad(lambda b:b.__setitem__(6,"0"*64),"producer identity")
        self.assert_bad(lambda b:b.__setitem__(
            1,(PARENT,ORIGINAL,"INVALID",0)),"parent source build")
        self.assert_bad(lambda b:b.__setitem__(
            1,(PARENT,ORIGINAL,SOURCE,1)),"parent source build")

    def test_no_false_vendor_rights_or_historical_pit_approval(self):
        def t(b):
            m=list(b[0]);m[10]=True;b[0]=tuple(m)
        self.assert_bad(t,"release state")
        def u(b):
            row=list(b[3][0]);row[-1]=1;b[3][0]=tuple(row)
        self.assert_bad(u,"falsely released")

    def test_altered_original_model_mse_rejected(self):
        def t(b):
            x=list(b[2][0]);x[6]+=0.01;b[2][0]=tuple(x)
        self.assert_bad(t,"parent baseline MSE")

    def test_replaced_security_day_prediction_or_mse_rejected(self):
        def t(b):
            x=list(b[3][0]);x[7]+=1;b[3][0]=tuple(x)
        self.assert_bad(t,"daily prediction")
        def u(b):
            x=list(b[3][0]);x[9]+=1;b[3][0]=tuple(x)
        self.assert_bad(u,"daily prediction")

    def test_duplicate_or_missing_security_day_and_date_order_rejected(self):
        self.assert_bad(lambda b:b[3].__setitem__(1,b[3][0]),"Duplicate/unbacked")
        self.assert_bad(lambda b:b[3].pop(),"Missing parent, daily")
        def t(b):
            x=list(b[3][0]);x[4]=x[5];b[3][0]=tuple(x)
        self.assert_bad(t,"training cutoff")

    def test_bootstrap_recompute_rejects_changed_critical_or_forged_pass_count(self):
        def t(b):
            x=list(b[4][0]);x[5]+=1.0;b[4][0]=tuple(x)
        self.assert_bad(t,"max_t")
        def u(b):
            x=list(b[4][0]);x[4]+=1;b[4][0]=tuple(x)
        self.assert_bad(u,"simultaneous pass count")

    def test_changed_source_build_or_incomplete_variant_blocks(self):
        def t(b):
            x=list(b[3][0]);x[1]="other-parent";b[3][0]=tuple(x)
        self.assert_bad(t,"Duplicate/unbacked")
        self.assert_bad(lambda b:b[4].pop(),"Missing parent, daily")

    def test_validator_is_select_only_and_has_no_release_approval_logic(self):
        text=(LAB/"phase1_daily_loss_build_acceptance.py").read_text()
        self.assertIn("bootstrap.assess(",text)
        self.assertIn("original_publisher_pit_verified",text)
        self.assertNotIn("INSERT INTO",text)
        self.assertNotIn("UPDATE main.",text)
        self.assertNotIn("institutional_beta_released\":True",text)


if __name__=="__main__":
    unittest.main()
