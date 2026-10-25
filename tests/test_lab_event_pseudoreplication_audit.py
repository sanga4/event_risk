"""Methodology checks: shared daily market shocks are not 192k iid returns."""
from pathlib import Path
import importlib.util
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"lab"/"phase1_event_pseudoreplication_audit.py"
spec=importlib.util.spec_from_file_location("pseudorep",SOURCE)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def fixture(days=6,paired_dates=5,paired=10000):
    items=[(f"FACTOR_{i}",12969,paired,days,paired_dates,days,2283,
            12969,0,0) for i in range(18)]
    return items,("source-native-build",18*12969,18,False)

class IdentificationTests(unittest.TestCase):
    def test_large_row_count_never_masquerades_as_independent_dates(self):
        results=audit.evaluate(*fixture())
        self.assertEqual(len(results),18)
        self.assertTrue(all(x[4]==5 for x in results))
        self.assertTrue(all(x[6]==2000 for x in results))
        self.assertTrue(all(not x[7] for x in results))
        self.assertTrue(all("INSUFFICIENT" in x[8] for x in results))

    def test_sixty_dates_is_only_history_candidate_not_approval(self):
        out=audit.evaluate(*fixture(days=75,paired_dates=60))
        self.assertTrue(all(x[7] for x in out))
        self.assertTrue(all("UNVERIFIED" in x[8] for x in out))

    def test_no_false_data_or_legal_approval(self):
        for pos,value in ((8,1),(9,1),(5,7),(4,7),(2,12970),(6,0)):
            f,s=fixture()
            row=list(f[0]);row[pos]=value;f[0]=tuple(row)
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"Invalid factor"):
                audit.evaluate(f,s)

    def test_missing_family_and_duplicate_family_rejected(self):
        f,s=fixture()
        with self.assertRaisesRegex(ValueError,"family"):
            audit.evaluate(f[:-1],s)
        f,s=fixture();f[-1]=f[0]
        with self.assertRaisesRegex(ValueError,"family"):
            audit.evaluate(f,s)

    def test_source_released_or_source_rows_modified_fails(self):
        f,s=fixture()
        for source in [(s[0],s[1],s[2],True),
                       (s[0],s[1]+1,s[2],False),
                       (s[0],s[1],17,False)]:
            with self.subTest(source=source),self.assertRaises(ValueError):
                audit.evaluate(f,source)

    def test_wrong_schema_rejected(self):
        f,s=fixture()
        with self.assertRaises(ValueError):
            audit.evaluate([(x[0],*x[1:-1]) for x in f],s)

    def test_factor_day_is_not_independent_proposition_count(self):
        src=SOURCE.read_text()
        self.assertIn("count(DISTINCT observed_date)",src)
        self.assertIn("count(DISTINCT (observed_date,factor_value))",src)
        self.assertIn("FROM {P}lab_event_factor_panel_v4_latest",src)
        self.assertIn("FALSE,FALSE",src)

if __name__=="__main__":
    unittest.main()
