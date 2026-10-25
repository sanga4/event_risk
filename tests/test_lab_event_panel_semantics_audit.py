"""Source-controlled adversarial tests of the event–factor PIT semantic firewall."""
import importlib.util
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_event_panel_semantics_audit.py"
spec=importlib.util.spec_from_file_location("temporal_panel",SRC)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def fixture():
    by={}
    for label in audit.DATASETS:
        rows=[]
        for k in range(18):
            # factor,n,late,warning,carried,paired,contract_error
            if label=="RETROSPECTIVE_V2":
                row=(f"FACTOR_{k}",1,1,1,int(k<6),1,0)
            elif label=="RETROSPECTIVE_V3":
                row=(f"FACTOR_{k}",1,1,1,0,1,0)
            else:
                row=(f"FACTOR_{k}",1,0,0,0,1,0)
            rows.append(row)
        by[label]=rows
    return by,(18,6,6,0,6),{name:0 for name in audit.DATASETS}

class EventPanelSemanticsTests(unittest.TestCase):
    def test_all_three_families_and_structural_discrepancy_report(self):
        r=audit.summarize(*fixture())
        self.assertEqual(len(r["subjects"]),54)
        self.assertEqual(r["totals"]["RETROSPECTIVE_V2"][1],18)
        self.assertEqual(r["totals"]["RETROSPECTIVE_V3"][1],18)
        self.assertEqual(r["totals"]["WAREHOUSE_ASOF"][1],0)
        self.assertEqual(r["pairs"],(18,6,6,0,6))
        self.assertTrue(all(row[-1].endswith("UNAPPROVED") or
                            row[-1].endswith("PIT") for row in r["subjects"]))

    def test_future_warehouse_data_is_rejected(self):
        a=list(fixture())
        factors=a[0]["WAREHOUSE_ASOF"]
        factors[0]=("FACTOR_0",1,1,0,0,1,0)
        with self.assertRaisesRegex(ValueError,"warehouse"):
            audit.summarize(*a)

    def test_unflagged_retrospective_future_lag_is_rejected(self):
        a=list(fixture())
        factors=a[0]["RETROSPECTIVE_V2"]
        factors[0]=("FACTOR_0",1,1,0,0,1,0)
        with self.assertRaisesRegex(ValueError,"lookahead"):
            audit.summarize(*a)

    def test_unsupported_approval_license_hash_and_units_refused(self):
        a=list(fixture())
        factors=a[0]["RETROSPECTIVE_V3"]
        factors[0]=("FACTOR_0",1,1,1,0,1,1)
        with self.assertRaisesRegex(ValueError,"invalid source"):
            audit.summarize(*a)

    def test_no_phantom_factor_family_accepted(self):
        a=list(fixture())
        a[0]["RETROSPECTIVE_V2"]=a[0]["RETROSPECTIVE_V2"][:-1]
        with self.assertRaisesRegex(ValueError,"contract"):
            audit.summarize(*a)

    def test_no_duplicate_panel_keys_accepted(self):
        a=list(fixture())
        a[2]["RETROSPECTIVE_V3"]=1
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            audit.summarize(*a)

    def test_no_false_aligned_source_value_accepted(self):
        a=list(fixture())
        a[1]=(18,6,6,1,6)
        with self.assertRaisesRegex(ValueError,"reconcile"):
            audit.summarize(*a)

    def test_carry_date_disagreement_cannot_exceed_mismatch_sets(self):
        a=list(fixture());a[1]=(18,6,6,0,7)
        with self.assertRaisesRegex(ValueError,"Relabelled"):
            audit.summarize(*a)

    def test_no_missing_dataset_or_missing_join_rows(self):
        a=list(fixture());del a[0]["RETROSPECTIVE_V3"]
        with self.assertRaises(ValueError):
            audit.summarize(*a)
        a=list(fixture());a[1]=(17,6,6,0,6)
        with self.assertRaisesRegex(ValueError,"reconcile"):
            audit.summarize(*a)

if __name__=="__main__":
    unittest.main()
