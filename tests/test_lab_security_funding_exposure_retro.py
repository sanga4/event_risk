"""Fail-closed USD security × funding factor research exposure test contract."""
from datetime import date,timedelta
from pathlib import Path
import importlib.util, unittest
SCRIPT=Path(__file__).resolve().parents[1]/"lab"/"phase1_security_funding_exposure_retro.py"
s=importlib.util.spec_from_file_location("security_funding",SCRIPT)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def rows():
    result=[]
    for i in range(48):
        name=f"ASSET{i:02d}"
        first=date(2024,1,2)
        for variant in ("all_training_days","trimmed_training_stress_and_price"):
            n=695; train=n*7//10; test=n-train
            excluded=0 if variant=="all_training_days" else 13
            mse=10000.0
            enhanced=9995.0 if variant=="all_training_days" else 10030.0
            result.append((name,variant,n,train,test,33,first,
                first+timedelta(days=700),first+timedelta(days=701),
                first+timedelta(days=1100),train-excluded,excluded,
                1.03,-2.5,0.6,mse,enhanced,1-enhanced/mse,0,13,0))
    return result

class USDResearchExposure(unittest.TestCase):
    def test_data_guard_retrospective_unapproved(self):
        self.assertTrue(m.check_sources((83427,48,1705,0,0,12),
                                         (2138,1,date(2026,10,25),0,0)))
    def test_missing_security_source_and_rights_fail(self):
        examples=[((20000,48,1705,0,0,12),(2138,1,date(2026,10,25),0,0)),
                  ((83427,47,1705,0,0,12),(2138,1,date(2026,10,25),0,0)),
                  ((83427,48,1705,1,0,12),(2138,1,date(2026,10,25),0,0)),
                  ((83427,48,1705,0,1,12),(2138,1,date(2026,10,25),0,0)),
                  ((83427,48,1705,0,0,12),(2138,2,date(2026,10,25),0,0)),
                  ((83427,48,1705,0,0,12),(2138,1,date(2026,10,25),1,0)),
                  ((83427,48,1705,0,0,12),(2138,1,date(2026,10,25),0,1))]
        for x,y in examples:
            with self.subTest(x=x,y=y),self.assertRaisesRegex(ValueError,"provenance invalid"):
                m.check_sources(x,y)
    def test_paired_calendar_and_holdout_coverage(self):
        z=m.assess(rows())
        self.assertEqual(z["assets"],48)
        self.assertEqual(z["models"],96)
        self.assertEqual(z["min_holdout"],209)
        self.assertEqual(z["positive_all"],48)
        self.assertEqual(z["positive_trimmed"],0)
        self.assertEqual(z["trimmed_changed"],48)
    def test_duplicate_ticker_or_missing_variant_fails(self):
        r=rows();r[1]=r[0]
        with self.assertRaisesRegex(ValueError,"duplicated"):
            m.assess(r)
        with self.assertRaisesRegex(ValueError,"Missing or duplicated"):
            m.assess(rows()[:-1])
    def test_wrong_train_heldout_boundary_fails(self):
        for field,value in ((2,400),(3,100),(4,100),(5,7),
                            (8,date(2024,6,1)),(10,15),(11,-1),
                            (19,999)):
            z=rows();x=list(z[0]);x[field]=value;z[0]=tuple(x)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"Insufficient"):
                m.assess(z)
    def test_zero_variance_bad_coefficients_and_bad_source_fails(self):
        for field,value in ((12,float("nan")),(13,float("inf")),
                            (14,1e-9),(15,0),(16,-1),(17,None),(20,1)):
            z=rows();x=list(z[0]);x[field]=value;z[0]=tuple(x)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"Invalid OOS"):
                m.assess(z)
    def test_no_hidden_hindsight_trimming_and_same_holdout_dates(self):
        z=rows();x=list(z[1]);x[11]=1;x[10]=z[1][3]-1;z[1]=tuple(x)
        with self.assertRaisesRegex(ValueError,"Tail/price"):
            m.assess(z)
        source=SCRIPT.read_text()
        self.assertIn("WHEN NOT funding_stress_day AND NOT price_outlier_day",source) if "WHEN NOT funding_stress_day AND NOT price_outlier_day" in source else self.assertIn("NOT funding_stress_day AND NOT price_outlier_day",source)
        self.assertIn("WHERE is_train",source)
        self.assertIn("FILTER(WHERE NOT is_train)",source)
        self.assertIn("market_only_heldout_mse",source)
    def test_source_unit_and_governance_pins(self):
        source=SCRIPT.read_text()
        self.assertIn("retrospective_research_only",source)
        self.assertIn("basis_change_bps",source)
        self.assertIn("SPY",source)
        self.assertIn("FALSE,FALSE,FALSE,FALSE",source)
        self.assertIn("PIT=FALSE LICENSES=FALSE",source)
        self.assertIn("train_num",source.lower()) if "train_num" in source.lower() else self.assertIn("TRAIN_NUM",source)

if __name__=="__main__":
    unittest.main()
