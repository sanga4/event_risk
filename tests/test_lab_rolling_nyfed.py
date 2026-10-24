"""Offline source and risk methodology tests, no external secrets/HTTP required."""
from __future__ import annotations
import importlib.util,json,sys,unittest
from pathlib import Path
from datetime import date,timedelta
import numpy as np
LAB=Path(__file__).resolve().parents[1]/"lab"

def read(relative,name):
    spec=importlib.util.spec_from_file_location(name,LAB/relative)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod

roll=read("phase1_cross_asset_rolling_stability.py","rollrisk")
ny=read("phase1_nyfed_funding_rates.py","nyrates")


class RollingCovarianceTests(unittest.TestCase):
    def test_stable_train_factors_and_forward_regime_break(self):
        r=np.random.default_rng(42)
        x=r.normal(size=(315,7))
        x[:,:3]*=np.array([25.,5.,3.])
        s=roll.validate_and_compute(x)
        self.assertGreater(s["min_eig"],0)
        self.assertTrue(np.isfinite(s["condition"]))
        changed=x.copy()
        changed[252:,:]*=3.5
        q=roll.validate_and_compute(changed)
        self.assertTrue(q["needs_review"])
        self.assertGreater(q["drift"],s["drift"])
        self.assertGreater(q["max_var"],4)
    def test_reject_bad_unit_dimensionality_and_nonfinite_data(self):
        with self.assertRaises(ValueError):
            roll.validate_and_compute(np.ones((315,6)))
        bad=np.ones((315,7))
        bad[0,0]=np.nan
        with self.assertRaises(ValueError):
            roll.validate_and_compute(bad)
    def test_source_and_model_rights_fail_closed(self):
        s=(LAB/"phase1_cross_asset_rolling_stability.py").read_text()
        self.assertIn("source_pit_independently_verified",s)
        self.assertIn("licensed_for_portfolio_risk",s)
        self.assertIn("PRODUCTION_RISK_APPROVED=FALSE",s)
        self.assertEqual(roll.TRAIN,252)
        self.assertEqual(roll.TEST,63)
        self.assertEqual(roll.STEP,21)


class OfficialNYFedRateTests(unittest.TestCase):
    def test_rate_type_and_annual_percent_unit(self):
        start=date(2025,1,1)
        raw=json.dumps({"refRates":[
            {"effectiveDate":(start+timedelta(days=i)).isoformat(),
             "type":"SOFR","percentRate":3.75,
             "volumeInBillions":2500,
             "revisionIndicator":""} for i in range(260)
        ]}).encode()
        x=ny.parse_records(raw,"SOFR")
        self.assertEqual(len(x),260)
        self.assertEqual(x[0][1],"SOFR")
        self.assertEqual(x[0][2],3.75)
        with self.assertRaises(ValueError):
            ny.parse_records(raw,"EFFR")
    def test_duplicate_dates_refused(self):
        original={"effectiveDate":"2026-10-20","type":"SOFR",
                  "percentRate":3.85,"volumeInBillions":2400}
        raw=json.dumps({"refRates":[original]*260}).encode()
        with self.assertRaises(ValueError):
            ny.parse_records(raw,"SOFR")
    def test_release_time_distinct_from_effective_date(self):
        s=(LAB/"phase1_nyfed_funding_rates.py").read_text()
        for token in ("effective_date","original_provider_published_at",
                      "first_published_timestamp_verified",
                      "is_identified_policy_or_funding_surprise",
                      "SOURCE_RIGHTS_AND_POLICY_SURPRISE_APPROVAL=BLOCKED"):
            self.assertIn(token,s)


if __name__=="__main__":
    unittest.main()
