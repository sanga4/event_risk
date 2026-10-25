"""Offline regression tests for read-only Phase I grid preflight.

These use in-memory DuckDB only: no remote Flight, token or provider request.
"""
from pathlib import Path
import importlib.util
import unittest

import duckdb

SCRIPT = Path(__file__).resolve().parents[1] / "lab" / "phase1_grid_preflight.py"
spec = importlib.util.spec_from_file_location("grid_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

GRID_COLUMNS = """(
 event_run_id VARCHAR, venue VARCHAR, market_id VARCHAR, factor_id VARCHAR,
 factor_ingested_at TIMESTAMP, factor_available_at TIMESTAMP,
 event_capture_at TIMESTAMP, event_receipt_time_verified BOOLEAN,
 factor_warehouse_asof_verified BOOLEAN,
 exchange_quote_time_independently_verified BOOLEAN,
 factor_publication_time_independently_verified BOOLEAN,
 event_to_factor_mapping_approved BOOLEAN,
 historical_backtest_released BOOLEAN
)"""
GRID_ROW = (
    "'prior','kalshi','same-market','DGS2',"
    "'2026-10-25 10:00:00','2026-10-25 10:00:00',"
    "'2026-10-25 11:00:00',true,true,false,false,false,false"
)


class GridPreflightTest(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(":memory:")
        self.con.execute(
            "CREATE TABLE main.lab_live_event_features_v1("
            "run_id VARCHAR, venue VARCHAR, market_id VARCHAR)"
        )
        self.con.execute(
            "INSERT INTO main.lab_live_event_features_v1 VALUES "
            "('prior','kalshi','same-market'),"
            "('new','kalshi','same-market')"
        )
        self.con.execute(
            "CREATE TABLE main.lab_prospective_event_factor_grid_v1 "
            + GRID_COLUMNS
        )
        self.con.execute(
            "INSERT INTO main.lab_prospective_event_factor_grid_v1 VALUES "
            "(" + GRID_ROW + ")"
        )

    def tearDown(self):
        self.con.close()

    def report(self):
        return preflight.inspect(self.con, "main.")

    def test_new_run_same_market_requires_incremental_processing(self):
        r = self.report()
        self.assertEqual(r["status"], "INCREMENTAL_CAPTURE_SCOPE_NONEMPTY")
        self.assertEqual(r["incremental_candidate_capture_rows"], 1)
        self.assertEqual(r["stored_capture_runs"], 2)
        self.assertEqual(r["persisted_grid_rows"], 1)
        self.assertFalse(r["institutional_historical_pit_release"])
        self.assertFalse(r["flight_run_proven"])

    def test_existing_source_identity_requires_explicit_replay_for_new_factors(self):
        # An already represented identity is NOT selected just because a
        # newly eligible factor could be added later.
        self.con.execute(
            "DELETE FROM main.lab_live_event_features_v1 WHERE run_id='new'"
        )
        r = self.report()
        self.assertEqual(r["incremental_candidate_capture_rows"], 0)
        self.assertEqual(r["status"], "INCREMENTAL_CAPTURE_SCOPE_EMPTY")
        self.assertIn("full replay", r["full_replay_note"])

    def test_duplicate_factor_keys_block(self):
        self.con.execute(
            "INSERT INTO main.lab_prospective_event_factor_grid_v1 VALUES "
            "(" + GRID_ROW + ")"
        )
        r = self.report()
        self.assertEqual(r["duplicate_event_factor_keys"], 1)
        self.assertEqual(r["status"], "BLOCKED_GRID_INTEGRITY")

    def test_future_factor_warehouse_ingestion_blocks(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_ingested_at='2026-10-25 12:00:00'"
        )
        r = self.report()
        self.assertEqual(r["future_warehouse_factor_rows"], 1)
        self.assertEqual(r["status"], "BLOCKED_GRID_INTEGRITY")

    def test_unverified_warehouse_receipt_flags_block(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET event_receipt_time_verified=false"
        )
        self.assertEqual(self.report()["invalid_warehouse_receipt_flags"], 1)
        self.assertEqual(self.report()["status"], "BLOCKED_GRID_INTEGRITY")

    def test_unsupported_institutional_flag_blocks(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET historical_backtest_released=true"
        )
        self.assertEqual(self.report()["unexpected_research_approval_rows"], 1)
        self.assertEqual(self.report()["status"], "BLOCKED_GRID_INTEGRITY")

    def test_missing_source_blocks_even_if_grid_has_rows(self):
        self.con.execute("DELETE FROM main.lab_live_event_features_v1")
        self.assertEqual(self.report()["status"], "BLOCKED_MISSING_RESEARCH_DATA")

    def test_read_only_sql_has_no_write_statements(self):
        source = SCRIPT.read_text()
        self.assertIn("WHERE NOT EXISTS", source)
        self.assertIn("factor_available_at > event_capture_at", source)
        self.assertIn("original_provider_publication_time_certified", source)
        self.assertNotIn("con.execute(\"INSERT ", source)
        self.assertNotIn("con.execute(\"UPDATE ", source)


if __name__ == "__main__":
    unittest.main()
