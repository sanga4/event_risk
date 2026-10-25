"""Source timestamp provenance cannot silently authorize historical PIT."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "lab" / "phase1_source_clock_gap_audit.py"
spec = importlib.util.spec_from_file_location("source_gap", PATH)
gap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gap)


def fixture():
    families = [(f"family_{i}", 10 if i < 7 else 0, False, False, False,
                 "independent original source") for i in range(16)]
    venues = [("kalshi", 15112, 0, 0, None),
              ("polymarket", 15000, 0, 0, None)]
    return ("family-build", families, venues, (107157, 0, 63), (542016, 0, 0))


class ClockGapTests(unittest.TestCase):
    def test_coverage_and_explicit_nonapproval(self):
        report = gap.assess(*fixture())
        self.assertEqual((report["loaded"], report["family_count"]-report["loaded"]), (7, 9))
        self.assertEqual(report["market_receipts"], 30112)
        self.assertEqual(report["grid_rows"], 542016)
        self.assertEqual(len(report["details"]), 20)
        self.assertTrue(all(not d[5] and not d[6] for d in report["details"]))

    def test_vendor_quote_at_null_cannot_be_treated_as_original_pit(self):
        report = gap.assess(*fixture())
        venues = [d for d in report["details"] if d[0] == "VENUE_HTTP_RECEIPT"]
        self.assertEqual(len(venues), 2)
        self.assertTrue(all(not d[3] and not d[5] for d in venues))

    def test_upstream_asserted_rights_are_not_independent_approval(self):
        args = list(fixture())
        args[1][0] = ("family_0", 10, True, True, True, "original source required")
        report = gap.assess(*args)
        self.assertEqual(report["details"][0][7], "UPSTREAM_ASSERTION_REQUIRES_INDEPENDENT_REVIEW")
        self.assertFalse(report["details"][0][5])
        self.assertFalse(report["details"][0][6])

    def test_time_leakage_and_false_risk_release_rejected(self):
        for grid in [(542016, 1, 0), (542016, 0, 1), (0, 0, 0)]:
            args = list(fixture())
            args[4] = grid
            with self.subTest(grid=grid), self.assertRaises(RuntimeError):
                gap.assess(*args)

    def test_bad_venue_timestamp_or_hash_rejected(self):
        args = list(fixture())
        args[2][0] = ("kalshi", 10, 0, 1, None)
        with self.assertRaisesRegex(RuntimeError, "venue"):
            gap.assess(*args)

    def test_missing_or_extra_family_denied(self):
        args = list(fixture())
        args[1] = args[1][:-1]
        with self.assertRaises(RuntimeError):
            gap.assess(*args)
        args = list(fixture())
        args[1][-1] = args[1][0]
        with self.assertRaises(RuntimeError):
            gap.assess(*args)

    def test_unexpected_venue_denied(self):
        args = list(fixture())
        args[2][0] = ("unknown", 100, 0, 0, None)
        with self.assertRaises(RuntimeError):
            gap.assess(*args)

    def test_invalid_historical_prices_denied(self):
        for prices in [(0,0,63),(107157,1,63),(107157,0,1)]:
            args = list(fixture())
            args[3] = prices
            with self.subTest(prices=prices), self.assertRaises(RuntimeError):
                gap.assess(*args)


if __name__ == "__main__":
    unittest.main()
