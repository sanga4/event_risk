"""Adversarial checks for source gaps and stale exception provenance."""
import importlib.util
import unittest
from pathlib import Path
import duckdb

spec = importlib.util.spec_from_file_location('lineage_adjust', Path(__file__).resolve().parents[1] / 'lab/phase1_adjusted_price_reconciliation.py')
adjust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adjust)

class SourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(':memory:')
        self.old = adjust.P
        adjust.P = 'main.'
        self.con.execute('''CREATE TABLE security_prices(
            ticker VARCHAR,date DATE,close DOUBLE,adj_close DOUBLE,
            volume DOUBLE,currency VARCHAR,source VARCHAR,
            fetched_at TIMESTAMPTZ,run_id VARCHAR)''')
        for day, price in [('2024-01-02', 100), ('2024-01-03', 110), ('2024-01-04', 150)]:
            self.con.execute("INSERT INTO security_prices VALUES ('T',?,?,?,1,'USD','vendor','2026-10-16 00:00:00+00','r1')", [day, price, price])

    def tearDown(self):
        adjust.P = self.old
        self.con.close()

    def test_duplicate_day_is_not_bridged(self):
        self.con.execute("INSERT INTO security_prices SELECT * FROM security_prices WHERE date='2024-01-03'")
        adjust.stage(self.con)
        self.assertEqual(self.con.execute('SELECT count(*) FROM p1_adj_diffs').fetchone()[0], 0)

    def test_invalid_day_is_not_bridged(self):
        for value in ['0', "'NaN'::DOUBLE", 'NULL', "'Infinity'::DOUBLE"]:
            with self.subTest(value=value):
                self.con.execute(f"UPDATE security_prices SET adj_close={value} WHERE date='2024-01-03'")
                adjust.stage(self.con)
                self.assertEqual(self.con.execute('SELECT count(*) FROM p1_adj_diffs').fetchone()[0], 0)

    def test_missing_calendar_days_are_not_invented(self):
        self.con.execute("UPDATE security_prices SET date='2024-01-08' WHERE date='2024-01-04'")
        adjust.stage(self.con)
        self.assertEqual(self.con.execute('SELECT count(*) FROM p1_adj_diffs').fetchone()[0], 2)

    def make_exception(self):
        adjust.stage(self.con)
        self.con.execute("CREATE TABLE lab_security_price_exception_builds_v1 AS SELECT 'b1' build_id, current_timestamp built_at")
        self.con.execute('''CREATE TABLE lab_security_price_exception_cases_v1 AS
            SELECT 'b1' build_id,ticker,date observed_date,prev_date previous_observed_date,
                prev_adj_close previous_adjusted_close,adj_close adjusted_close,
                adjusted_close_return_bps log_return_bps,close source_unadjusted_close,
                adj_close source_adjusted_close,source source_vendor,currency source_currency,
                run_id source_run_id,fetched_at source_retrieved_at
            FROM p1_adj_diffs WHERE date='2024-01-04' ''')

    def matched(self):
        adjust.link_cases(self.con,'new')
        return self.con.execute('SELECT mathematically_adjustment_step_explains_return_difference FROM p1_cases_linked').fetchone()[0]

    def test_exact_interval_and_source_match(self):
        self.make_exception()
        self.assertTrue(self.matched())
        self.assertFalse(self.con.execute('SELECT problem_cause_unambiguously_identified FROM p1_cases_linked').fetchone()[0])

    def test_identity_alone_cannot_reconcile_stale_exception(self):
        self.make_exception()
        changes = {
            'previous_observed_date': "DATE '2024-01-02'",
            'previous_adjusted_close': '100',
            'adjusted_close': '151',
            'source_adjusted_close': '151',
            'source_unadjusted_close': '151',
            'log_return_bps': '1',
            'source_vendor': "'other'",
            'source_currency': "'EUR'",
            'source_run_id': "'other'",
            'source_retrieved_at': "TIMESTAMPTZ '2026-10-17 00:00:00+00'",
        }
        for column, value in changes.items():
            with self.subTest(column=column):
                self.con.execute('BEGIN')
                self.con.execute(f'UPDATE lab_security_price_exception_cases_v1 SET {column}={value}')
                self.assertFalse(self.matched())
                self.con.execute('ROLLBACK')

if __name__ == '__main__':
    unittest.main()
