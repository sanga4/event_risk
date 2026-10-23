"""Offline DuckDB fixture for factor availability and warehouse-as-of joins."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from datetime import datetime, timezone

import duckdb

SCRIPT = Path(__file__).resolve().parents[1] / "lab" / "phase1_warehouse_asof_grid.py"
spec = importlib.util.spec_from_file_location("lab_forward_grid", SCRIPT)
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)


class WarehouseAsOfJoinTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(":memory:")
        grid.P = "main."
        self.con.execute("""
           CREATE TABLE lab_factor_catalog
           (factor_id VARCHAR,unit VARCHAR,active BOOLEAN,license_class VARCHAR)
        """)
        self.con.execute("""
           CREATE TABLE lab_factor_observations
           (factor_id VARCHAR,observed_date DATE,value DOUBLE,unit VARCHAR,
            provider VARCHAR,ingested_at TIMESTAMPTZ,availability_at TIMESTAMPTZ,
            availability_basis VARCHAR,source_url VARCHAR,record_sha256 VARCHAR,
            run_id VARCHAR)
        """)
        self.con.execute("""
           CREATE TABLE lab_live_event_features_v1
           (proposition_id VARCHAR,venue VARCHAR,market_id VARCHAR,run_id VARCHAR,
            known_at TIMESTAMPTZ,previous_capture_at TIMESTAMPTZ,
            probability DOUBLE,probability_delta_pp DOUBLE,quote_basis VARCHAR,
            source_record_sha256 VARCHAR,capture_time_verified BOOLEAN)
        """)
        self.con.execute("""
          INSERT INTO lab_factor_catalog VALUES
            ('DGS10','percent',TRUE,'government_source_via_treasury'),
            ('HY_OAS','bps',TRUE,'restricted_ice_bofa')
        """)
        self.con.execute("""
          INSERT INTO lab_factor_observations VALUES
            ('DGS10','2026-10-22',4.75,'percent','US_TREASURY',
             '2026-10-23 16:00:00+00','2026-10-23 16:00:00+00','ingest',
             'https://example.org/factor','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','run0'),
            ('DGS10','2026-10-22',4.80,'percent','US_TREASURY',
             '2026-10-23 18:00:00+00','2026-10-23 18:00:00+00','ingest',
             'https://example.org/factor','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','runfuture'),
            ('HY_OAS','2026-10-22',320,'bps','FRED',
             '2026-10-23 16:00:00+00','2026-10-23 16:00:00+00','ingest',
             'https://example.org/restricted','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','runcredit')
        """)
        self.con.execute("""
           INSERT INTO lab_live_event_features_v1 VALUES
            ('prop:kalshi:K1','kalshi','K1','event-run1',
             '2026-10-23 17:00:00+00',NULL,0.4,NULL,'indicative_bid_ask_midpoint',
             'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',TRUE),
            ('prop:kalshi:K2','kalshi','K2','event-run1',
             '2026-10-23 15:00:00+00',NULL,0.4,NULL,'indicative_bid_ask_midpoint',
             'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',TRUE)
        """)

    def tearDown(self):
        self.con.close()

    def test_join_prevents_future_revisions_and_licensed_credit(self):
        grid.stage(self.con)
        rows=self.con.execute("""
          SELECT market_id,factor_id,factor_value,factor_ingested_at<=event_capture_at,
                 factor_available_at<=event_capture_at,
                 exchange_quote_time_independently_verified,
                 factor_publication_time_independently_verified,
                 event_to_factor_mapping_approved,
                 historical_backtest_released
          FROM p1_candidate_grid ORDER BY market_id,factor_id
        """).fetchall()
        self.assertEqual(len(rows),1)  # K2 too early; restricted HY_OAS excluded
        self.assertEqual(rows[0][0],"K1")
        self.assertEqual(rows[0][1],"DGS10")
        self.assertEqual(rows[0][2],4.75)
        self.assertEqual(rows[0][3:5],(True,True))
        self.assertEqual(rows[0][5:],(False,False,False,False))

    def test_script_marks_warehouse_eligible_not_external_pit(self):
        src=SCRIPT.read_text()
        self.assertIn("unreviewed_factor_coobservation_grid",src)
        self.assertIn("INSTITUTIONAL_HISTORICAL_PIT_RELEASE=BLOCKED",src)
        self.assertIn("f.source_ingested_at <= e.known_at",src)
        self.assertIn("f.source_availability_at <= e.known_at",src)


if __name__ == "__main__":
    unittest.main()
