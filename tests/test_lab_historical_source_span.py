"""Historical source observation-day span, not original provider PIT clocks."""
from datetime import date
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"lab"/"phase1_source_family_evidence.py"
spec=importlib.util.spec_from_file_location("source_inventory_span",SOURCE)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class HistoricalSourceSpanTests(unittest.TestCase):
    def test_source_timestamp_column_is_not_missing(self):
        matches=[s for s in mod.SOURCES if s.domain=="historical_market_snapshots"]
        self.assertEqual(len(matches),1)
        s=matches[0]
        self.assertEqual(s.table,"market_snapshots")
        self.assertEqual(s.date_col,"ts")
        self.assertIsNone(s.received_col)
        self.assertIn("RETROSPECTIVE",s.usage)

    def test_real_observation_span_is_not_claimed_independent_sample(self):
        first=date(2021,7,8);last=date(2026,10,22)
        days=mod.validate_snapshot_span(11101967,first,last,date(2026,10,24))
        self.assertEqual(days,(last-first).days+1)
        # Days in inclusive range differ from actual 1,857 observed dates.
        self.assertGreater(days,1857)

    def test_invalid_missing_or_reversed_source_observation_dates(self):
        for n,first,last in [(0,date(2021,7,8),date(2026,10,22)),
                             (10,None,date(2026,10,22)),
                             (10,date(2021,7,8),None),
                             (10,date(2026,10,22),date(2021,7,8))]:
            with self.subTest(n=n,first=first,last=last),self.assertRaises(ValueError):
                mod.validate_snapshot_span(n,first,last,date(2026,10,24))

    def test_future_source_dates_must_fail_closed(self):
        with self.assertRaises(ValueError):
            mod.validate_snapshot_span(100,date(2026,10,1),date(2026,11,1),date(2026,10,24))

    def test_unsupported_ancient_source_dates_must_fail_closed(self):
        with self.assertRaises(ValueError):
            mod.validate_snapshot_span(100,date(1990,1,1),date(2026,10,22),date(2026,10,24))

    def test_issuer_publication_and_reuse_not_misrepresented(self):
        source=SOURCE.read_text()
        self.assertIn("validate_snapshot_span(count,first,last",source)
        self.assertIn("NEVER label these as provider first-publication clocks",source)
        self.assertIn("s.received_col and s.received_col in cols[s.table]",source)
        self.assertIn("s.next_evidence,False,False,False,True",source)

if __name__=="__main__":
    unittest.main()
