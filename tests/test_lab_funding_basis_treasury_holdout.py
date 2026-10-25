"""Adversarial original-source and chronological funding/Treasury research tests.

These tests use only a fixed in-memory acceptance fixture; no warehouse reads,
provider URLs, trading outputs or source rights are exercised.
"""
from __future__ import annotations
import importlib.util
from datetime import date,timedelta
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_funding_basis_treasury_holdout.py"
spec=importlib.util.spec_from_file_location("rate_basis_holdout",SRC)
method=importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)

def fixture():
    start=date(2024,1,2)
    models=[]
    for factor in range(18):
        for feature in ("basis_change_bps","sofr_change_bps"):
            n=700
            models.append((f"F{factor}",feature,n,490,210,34,start,
                start+timedelta(days=690),start+timedelta(days=691),
                start+timedelta(days=1000),.02,-.002,-.003,12.0,13.0,4,0))
    return models

class FundingBasisAcceptance(unittest.TestCase):
    def test_two_reference_series_full_history_source_provenance(self):
        self.assertTrue(method.review_source(
            (2138,2138,date(2018,4,2),date(2026,10,22),0),
            (18,0),(4288,500,0,0)))

    def test_missing_history_duplicates_and_causal_claims_block(self):
        r=(2138,2138,date(2018,4,2),date(2026,10,22),0)
        f=(18,0);b=(4288,500,0,0)
        cases=[((2138,2137,*r[2:]),f,b),
               ((1499,1499,*r[2:]),f,b),
               ((2138,2138,date(2021,1,1),r[3],0),f,b),
               ((2138,2138,r[2],r[3],1),f,b),
               (r,(17,0),b),
               (r,(18,1),b),
               (r,f,(4288,499,0,0)),
               (r,f,(4288,500,1,0)),
               (r,f,(4288,500,0,1))]
        for rate,fac,build in cases:
            with self.subTest(rate=rate,fac=fac,build=build),self.assertRaisesRegex(ValueError,"integrity"):
                method.review_source(rate,fac,build)

    def test_model_window_is_chronological_and_independent_daily(self):
        review=method.review_models(fixture(),2138)
        self.assertEqual(review["model_pairs"],36)
        self.assertEqual(review["positive_same_day"],0)
        self.assertEqual(review["positive_future_placebo"],0)
        self.assertEqual(review["min_holdout"],210)

    def test_missing_factor_and_duplicate_feature_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing Treasury"):
            method.review_models(fixture()[:-1],2138)
        rows=fixture();rows[1]=rows[0]
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            method.review_models(rows,2138)

    def test_temporal_overlap_and_window_insufficiency_rejected(self):
        for field,new in ((3,400),(4,100),(5,5),
                          (8,date(2024,5,1)),(15,9)):
            rows=fixture()
            r=list(rows[0]);r[field]=new;rows[0]=tuple(r)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"temporally"):
                method.review_models(rows,2138)

    def test_falsely_approved_or_invalid_model_statistics_fail(self):
        for field,new in ((10,float("nan")),(11,float("inf")),
                          (12,None),(13,0),(14,0),(16,1)):
            rows=fixture()
            r=list(rows[0]);r[field]=new;rows[0]=tuple(r)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"Nonfinite"):
                method.review_models(rows,2138)

    def test_valid_positive_scores_are_still_research_only(self):
        rows=fixture()
        updated=[]
        for row in rows:
            r=list(row);r[11]=.04;r[12]=.05
            updated.append(tuple(r))
        summary=method.review_models(updated,2138)
        self.assertEqual(summary["positive_same_day"],36)
        self.assertEqual(summary["positive_future_placebo"],36)
        src=SRC.read_text()
        self.assertIn("RETROSPECTIVE_FUNDING_RATE_AND_TREASURY_COMOVEMENT_ONLY",src)
        self.assertIn("PIT_CLOCK=UNVERIFIED",src)
        self.assertIn("SECURITY_BETA_RELEASE=FALSE",src)

    def test_no_policy_surprise_and_no_future_feature_live_uses(self):
        s=SRC.read_text()
        self.assertIn("100.0*(sofr_percent-effr_percent)",s)
        self.assertIn("source_response_received_at",s)
        self.assertIn("WHERE t.treasury_change_bps IS NOT NULL",s)
        self.assertIn("PARTITION BY factor_id,feature_name ORDER BY observed_date",s)
        self.assertIn("lead(basis_change_bps)",s)
        self.assertIn("FILTER(WHERE NOT t.train)",s)
        self.assertIn("FALSE,FALSE,FALSE",s)

if __name__=="__main__":
    unittest.main()
