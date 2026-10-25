"""Adversarial source-linked v3.1 correction preflight; no remote data calls."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"lab"/"phase1_v31_factor_source_repair.py"
spec=importlib.util.spec_from_file_location("v31",SOURCE)
repair=importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)

def good():
    return (233442,233442,233442,233442,18,0,0,0,0,0,76662,76662,2806,1)

class SourceRepairAcceptance(unittest.TestCase):
    def test_exact_source_coverage_and_repair_stats(self):
        result=repair.review(good())
        self.assertEqual(result["rows"],233442)
        self.assertEqual(result["factors"],18)
        self.assertEqual(result["source_date_repaired"],76662)
        self.assertEqual(result["carry_flag_repaired"],76662)
        self.assertEqual(result["material_daily_change_repaired"],2806)

    def test_no_source_row_duplication_or_loss(self):
        for index,new in [(0,233441),(1,233441),(2,233441),(3,233441)]:
            a=list(good());a[index]=new
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"duplicated"):
                repair.review(a)

    def test_invalid_factor_universe_or_multiple_builds(self):
        for index,new in [(4,17),(13,2)]:
            a=list(good());a[index]=new
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"universe"):
                repair.review(a)

    def test_incorrect_original_source_rows_refused(self):
        for index in range(5,10):
            a=list(good());a[index]=1
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"Source hashes"):
                repair.review(a)

    def test_changed_data_repair_counts_bounded(self):
        for index in (10,11,12):
            a=list(good());a[index]=233443
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"Impossible"):
                repair.review(a)

    def test_originally_correct_version_may_have_no_changes(self):
        a=list(good());a[10]=a[11]=a[12]=0
        r=repair.review(a)
        self.assertEqual(r["source_date_repaired"],0)

    def test_refuse_bad_tuple_length(self):
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            repair.review(good()[:-1])

if __name__=="__main__":
    unittest.main()
