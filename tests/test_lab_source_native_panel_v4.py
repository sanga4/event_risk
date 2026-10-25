"""Adversarial source-native event-factor alignment and PIT contract tests."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"lab"/"phase1_source_native_panel_v4.py"
spec=importlib.util.spec_from_file_location("source_native_v4",SCRIPT)
v4=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)

def valid():
    # records,factors,duplicate_keys,bad_values,false_approvals,
    # future_source_dates,unflagged_late,carried,paired,late
    coverage=(233442,18,0,0,0,0,0,76662,192294,233442)
    oracle=(233442,233442,0,0)
    return coverage,oracle

class NativeAlignmentTests(unittest.TestCase):
    def test_full_reconciliation_still_never_certifies_historical_pit(self):
        result=v4.accept(*valid())
        self.assertEqual(result["rows"],233442)
        self.assertEqual(result["matched_oracle"],233442)
        self.assertEqual(result["carried"],76662)
        self.assertEqual(result["retrospective_late"],233442)

    def test_missing_source_contract_or_duplicate_keys_fails(self):
        for i,val in ((0,0),(1,17),(2,1),(3,1),(4,1),(5,1),(6,1)):
            args=list(valid())
            coverage=list(args[0]);coverage[i]=val;args[0]=tuple(coverage)
            with self.subTest(index=i),self.assertRaisesRegex(ValueError,"integrity"):
                v4.accept(*args)

    def test_oracle_missing_or_semantically_inconsistent_fails(self):
        for i,val in ((0,0),(1,233441),(2,1),(3,1)):
            args=list(valid())
            o=list(args[1]);o[i]=val;args[1]=tuple(o)
            with self.subTest(index=i),self.assertRaisesRegex(ValueError,"reconciliation"):
                v4.accept(*args)

    def test_can_support_additional_later_research_days(self):
        coverage,oracle=valid()
        coverage=list(coverage)
        coverage[0]+=18
        coverage[8]+=18
        coverage[9]+=18
        x=v4.accept(tuple(coverage),oracle)
        self.assertEqual(x["rows"],233460)

    def test_impossible_counts_not_silently_accepted(self):
        for i in (7,8,9):
            args=list(valid());c=list(args[0]);c[i]=233443;args[0]=tuple(c)
            with self.subTest(index=i),self.assertRaisesRegex(ValueError,"counts"):
                v4.accept(*args)

    def test_reject_wrong_tuple_contract(self):
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            v4.accept(valid()[0][:-1],valid()[1])

    def test_sql_uses_source_factor_day_and_proposition_partition(self):
        # Static source regression tests complement live source-hash join.
        source=SCRIPT.read_text()
        self.assertIn("f.observed_date AS source_factor_day",source)
        self.assertIn("PARTITION BY e.proposition_id,f.factor_id",source)
        self.assertIn("source_factor_day AS factor_observed_date",source)
        self.assertIn("source_factor_day<event_day",source)
        self.assertNotIn("SELECT d.observed_date, d.cutoff_at, f.*",source)
        self.assertIn("lab_event_factor_panel_v3_1_latest",source)

    def test_retro_stays_unapproved_even_if_new_source_available(self):
        source=SCRIPT.read_text()
        self.assertIn("FALSE::BOOLEAN AS original_source_pit_verified",source)
        self.assertIn("FALSE::BOOLEAN AS independently_approved_causal_mapping",source)
        self.assertIn("FALSE::BOOLEAN AS institutional_risk_release",source)
        self.assertIn("'retrospective'::VARCHAR AS observed_mode",source)

if __name__=="__main__":
    unittest.main()
