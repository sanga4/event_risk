"""Offline acceptance tests for retrospective covariance tail diagnostics."""
from __future__ import annotations
from datetime import date,timedelta
import importlib.util
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_covariance_tail_calibration.py"
spec=importlib.util.spec_from_file_location("cov_tail", SRC)
tail=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tail)


def fixture():
    days=[date(2026,1,1)+timedelta(days=i) for i in range(tail.HOLDOUT)]
    out=[]
    for day_index,day in enumerate(days):
        for model_index,model in enumerate(tail.MODELS):
            # Each method has 12 extreme days; multiple consecutive hits test clustering.
            hit=(day_index in set(range(3,7))|set(range(40,44))|set(range(90,94)))
            q=25.0 if hit else 7.0
            out.append((day,model,day-timedelta(days=400),
                day-timedelta(days=1),252,q,5.0 if hit else 1.1,
                True,False,False,False))
    return out


class CovarianceTailTests(unittest.TestCase):
    def test_exact_iid_binomial_probability(self):
        self.assertAlmostEqual(tail.iid_binomial_upper_tail(10,1,.1),1-.9**10,places=12)
        self.assertAlmostEqual(tail.iid_binomial_upper_tail(10,10,.1),.1**10,places=12)
        self.assertLess(tail.iid_binomial_upper_tail(164,12,.01),1e-5)

    def test_block_bootstrap_deterministic_and_non_parametric(self):
        data=[1 if i%11==0 else 0 for i in range(164)]
        lo,hi=tail.circular_block_interval(data)
        self.assertEqual((lo,hi),tail.circular_block_interval(data))
        self.assertLessEqual(lo,sum(data)/164)
        self.assertGreaterEqual(hi,sum(data)/164)

    def test_circular_block_keeps_clusters_possible(self):
        self.assertEqual(tail.longest_run([0,1,1,1,0,1,0]),3)
        self.assertEqual(tail.longest_run([0]*164),0)
        with self.assertRaises(ValueError):
            tail.circular_block_interval([1,2]*82)

    def test_paired_chronological_scores_and_false_approval(self):
        summary,daily=tail.evaluate(fixture())
        self.assertEqual(len(summary),4)
        self.assertEqual(len(daily),4*164)
        self.assertTrue(all(x["hits99"]==12 for x in summary))
        self.assertTrue(all(x["hits95"]==12 for x in summary))
        self.assertTrue(all(x["longest_run"]==4 for x in summary))
        self.assertTrue(all(x["large_shock_hits99"]==12 for x in summary))

    def test_source_approval_flags_fail_closed(self):
        for offset in (8,9,10):
            rows=fixture()
            row=list(rows[0]);row[offset]=True;rows[0]=tuple(row)
            with self.subTest(offset=offset),self.assertRaisesRegex(ValueError,"approved"):
                tail.evaluate(rows)

    def test_future_train_overlap_and_training_integrity(self):
        for offset,value in [(2,date(2027,1,1)),(3,date(2027,1,1)),
                             (4,251),(7,False)]:
            rows=fixture()
            row=list(rows[0]);row[offset]=value;rows[0]=tuple(row)
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                tail.evaluate(rows)

    def test_duplicate_and_misaligned_holdout_rejected(self):
        rows=fixture();rows[0]=rows[4]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            tail.evaluate(rows)
        rows=fixture()
        row=list(rows[0]);row[0]=row[0]-timedelta(days=20);rows[0]=tuple(row)
        with self.assertRaises(ValueError):
            tail.evaluate(rows)

    def test_missing_source_method_and_nan_rejected(self):
        for offset,value in [(1,"arbitrary"),(5,float("nan")),(6,float("inf")),(5,-1)]:
            rows=fixture()
            row=list(rows[0]);row[offset]=value;rows[0]=tuple(row)
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                tail.evaluate(rows)

    def test_exact_threshold_is_not_exceedance(self):
        rows=fixture()
        adjusted=[]
        for r in rows:
            v=list(r);v[5]=tail.Q99
            adjusted.append(tuple(v))
        summaries,_=tail.evaluate(adjusted)
        self.assertTrue(all(x["hits99"]==0 for x in summaries))
        self.assertTrue(all(x["hits95"]==164 for x in summaries))

    def test_missing_single_row_fails_closed(self):
        rows=fixture()[:-1]
        with self.assertRaises(ValueError):
            tail.evaluate(rows)


if __name__=="__main__":
    unittest.main()
