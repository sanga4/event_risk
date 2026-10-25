"""Incremental as-of grid scope: exact capture keys, replay and immutability.

DuckDB in-memory only; no MotherDuck data/token, external market or rights access.
"""
from pathlib import Path
import importlib.util
import unittest
import duckdb

SCRIPT=Path(__file__).resolve().parents[1]/"lab"/"phase1_warehouse_asof_grid.py"
spec=importlib.util.spec_from_file_location("incremental_grid",SCRIPT)
grid=importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)

class IncrementalWarehouseScope(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect(":memory:")
        self.con.execute("""CREATE TABLE main.lab_live_event_features_v1(
            run_id VARCHAR,venue VARCHAR,market_id VARCHAR,description VARCHAR)""")
        self.con.execute("""CREATE TABLE main.lab_prospective_event_factor_grid_v1(
            event_run_id VARCHAR,venue VARCHAR,market_id VARCHAR,factor_id VARCHAR)""")
        self.con.execute("""INSERT INTO main.lab_live_event_features_v1 VALUES
            ('past','kalshi','m1','prior source'),
            ('past','kalshi','m2','not yet processed'),
            ('latest','kalshi','m1','same market different capture run'),
            ('latest','polymarket','p1','new venue receipt'),
            ('past','polymarket','p2','old but not yet processed')""")
        self.con.execute("""INSERT INTO main.lab_prospective_event_factor_grid_v1
            VALUES ('past','kalshi','m1','DGS2')""")

    def tearDown(self):self.con.close()
    def candidates(self,full=False):
        self.con.execute(grid.capture_scope_sql("main."),[full])
        return self.con.execute("""SELECT run_id,venue,market_id FROM
          p1_capture_scope ORDER BY 1,2,3""").fetchall()

    def test_new_capture_markets_not_full_history_rejoined(self):
        self.assertEqual(self.candidates(),[
            ("latest","kalshi","m1"),("latest","polymarket","p1"),
            ("past","kalshi","m2"),("past","polymarket","p2")])

    def test_captured_market_identity_includes_run_and_venue(self):
        c=self.candidates()
        self.assertIn(("latest","kalshi","m1"),c)
        self.assertNotIn(("past","kalshi","m1"),c)
        self.assertIn(("latest","polymarket","p1"),c)

    def test_explicit_full_replay_requires_operator_flag(self):
        all_rows=self.candidates(True)
        self.assertEqual(len(all_rows),5)
        self.assertIn(("past","kalshi","m1"),all_rows)

    def test_incremental_rerun_with_completed_source_is_empty(self):
        self.con.execute("""INSERT INTO main.lab_prospective_event_factor_grid_v1
             SELECT run_id,venue,market_id,'DGS2' FROM
             main.lab_live_event_features_v1
             WHERE (run_id,venue,market_id) NOT IN (
               SELECT event_run_id,venue,market_id FROM
               main.lab_prospective_event_factor_grid_v1)""")
        self.assertEqual(self.candidates(),[])

    def test_immutable_keys_preserve_partial_source_requires_replay(self):
        # Existing original source event is intentionally not silently revised.
        # A missing new factor can be investigated through FULL_REPLAY.
        self.assertNotIn(("past","kalshi","m1"),self.candidates())
        self.assertIn(("past","kalshi","m1"),self.candidates(True))

    def test_funding_clock_and_no_fake_rights_still_required(self):
        source=SCRIPT.read_text()
        self.assertIn("f.source_ingested_at <= e.known_at",source)
        self.assertIn("f.source_availability_at <= e.known_at",source)
        self.assertIn("p1_missing_grid",source)
        self.assertIn("LAB_GRID_FULL_REPLAY",source)
        self.assertIn("EVENT_FACTOR_RELATIONSHIPS_APPROVED=FALSE",source)
        self.assertIn("INSTITUTIONAL_HISTORICAL_PIT_RELEASE=BLOCKED",source)

if __name__=="__main__":
    unittest.main()
