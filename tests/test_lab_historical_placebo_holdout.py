"""Fail-closed offline tests for temporal split and unavailable future-feature placebo."""
import importlib.util
from datetime import date,timedelta
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"lab"/"phase1_historical_placebo_holdout.py"
spec=importlib.util.spec_from_file_location("placebo",SCRIPT)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def fixture():
    models=[]
    for venue in p.EXPECTED_VENUES:
        n=491 if venue=="kalshi" else 639
        train=int(n*.70)
        for k in range(18):
            start=date(2024,1,1)
            models.append((venue,f"FACTOR{k}",n,train,n-train,25,
                start,start+timedelta(days=train),
                start+timedelta(days=train+1),
                start+timedelta(days=n+100),.03,-.02,-.04,2.5,2.3,0))
    return ("history-build",2979,36,0,"RETROSPECTIVE_RESEARCH_NOT_RELEASED"),models

class TemporalPlaceboTests(unittest.TestCase):
    def test_independent_test_split_and_no_model_approval(self):
        models=p.assess(*fixture())
        self.assertEqual(len(models),36)
        self.assertEqual(sum(x[16] for x in models),0)
        self.assertEqual(sum(x[17] for x in models),0)
        self.assertTrue(all("RETROSPECTIVE" in x[18] for x in models))

    def test_negative_r2_valid_and_future_control_not_live_feature(self):
        src=SCRIPT.read_text()
        self.assertIn("lead(mean_absolute_delta_pp)",src)
        self.assertIn("future_x_placebo",src)
        self.assertIn("NOT a point-in-time",src)
        self.assertIn("WHERE is_train",src)
        self.assertIn("FILTER(WHERE NOT t.is_train)",src)
        self.assertIn("FALSE,FALSE",src)

    def test_not_overlapping_train_holdout_dates(self):
        for pos,val in ((7,date(2025,12,31)),(8,date(2023,12,31)),
                        (3,100),(4,10),(5,2)):
            src,rows=fixture();v=list(rows[0]);v[pos]=val;rows[0]=tuple(v)
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"chronological"):
                p.assess(src,rows)

    def test_invalid_source_release_and_manifest(self):
        for source in ((None,2979,36,0,"RETROSPECTIVE_RESEARCH_NOT_RELEASED"),
                       ("id",2979,36,1,"RETROSPECTIVE_RESEARCH_NOT_RELEASED"),
                       ("id",2979,35,0,"RETROSPECTIVE_RESEARCH_NOT_RELEASED"),
                       ("id",2979,36,0,"INSTITUTIONAL_APPROVED")):
            with self.subTest(source=source),self.assertRaisesRegex(ValueError,"source"):
                p.assess(source,fixture()[1])

    def test_bad_metric_and_spurious_approval(self):
        for pos,val in ((10,float("nan")),(11,float("inf")),
                        (12,None),(13,-1.),(14,0.),(15,1),(10,1.5)):
            src,rows=fixture();r=list(rows[0]);r[pos]=val;rows[0]=tuple(r)
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"Nonfinite"):
                p.assess(src,rows)

    def test_duplicate_factor_or_missing_venue_blocks(self):
        src,rows=fixture();rows[1]=rows[0]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            p.assess(src,rows)
        src,rows=fixture();rows=rows[:-1]
        with self.assertRaises(ValueError):
            p.assess(src,rows)

    def test_holdout_signals_are_descriptive_not_certification(self):
        src,rows=fixture()
        updated=[]
        for row in rows:
            x=list(row);x[11]=.02;x[12]=.01
            updated.append(tuple(x))
        res=p.assess(src,updated)
        self.assertEqual(sum(x[16] for x in res),36)
        self.assertEqual(sum(x[17] for x in res),36)
        self.assertTrue(all("NOT_TRADEABLE" not in x[18] or "RETROSPECTIVE" in x[18]
                            for x in res))

if __name__=="__main__":
    unittest.main()
