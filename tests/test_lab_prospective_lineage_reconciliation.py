"""Offline negative controls for full prospective event×factor source lineage.

Only in-memory synthetic rows: no MotherDuck Flight, provider input, source
license or external publication/PIT assertion.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import duckdb

SCRIPT = Path(__file__).resolve().parents[1] / "lab" / "phase1_prospective_lineage_reconciliation.py"
spec = importlib.util.spec_from_file_location("prospective_lineage_reconciliation", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
HEX_A = "a" * 64
HEX_B = "b" * 64
AT = "2026-10-25 11:00:00"
INGESTED = "2026-10-24 09:00:00"
OBSERVED = "2026-10-24"


class ResearchGridLineageTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(":memory:")
        self.con.execute("""
            CREATE TABLE main.lab_live_event_features_v1 (
              run_id VARCHAR,venue VARCHAR,market_id VARCHAR,
              source_record_sha256 VARCHAR, known_at TIMESTAMP,
              proposition_id VARCHAR,probability DOUBLE
            )
        """)
        self.con.execute("""
            CREATE TABLE main.lab_factor_warehouse_vintages_v1 (
              factor_id VARCHAR,factor_observed_date DATE,
              source_record_sha256 VARCHAR,source_ingested_at TIMESTAMP,
              factor_value DOUBLE,factor_unit VARCHAR,
              source_availability_at TIMESTAMP,license_class VARCHAR,
              provider VARCHAR,source_run_id VARCHAR
            )
        """)
        self.con.execute("""
            CREATE TABLE main.lab_prospective_event_factor_grid_v1 (
              event_run_id VARCHAR,venue VARCHAR,market_id VARCHAR,
              event_source_sha256 VARCHAR,event_capture_at TIMESTAMP,
              proposition_id VARCHAR,event_probability DOUBLE,
              factor_id VARCHAR,factor_observed_date DATE,
              factor_source_sha256 VARCHAR,factor_ingested_at TIMESTAMP,
              factor_value DOUBLE,factor_unit VARCHAR,
              factor_available_at TIMESTAMP,factor_license_class VARCHAR,
              factor_provider VARCHAR,factor_source_run_id VARCHAR,
              event_receipt_time_verified BOOLEAN,
              factor_warehouse_asof_verified BOOLEAN,
              exchange_quote_time_independently_verified BOOLEAN,
              factor_publication_time_independently_verified BOOLEAN,
              event_to_factor_mapping_approved BOOLEAN,
              historical_backtest_released BOOLEAN,
              data_use_class VARCHAR,relation_status VARCHAR
            )
        """)
        self.con.execute(
            "INSERT INTO main.lab_live_event_features_v1 VALUES "
            f"('run-1','kalshi','mkt-1','{HEX_A}','{AT}','p-1',0.43)"
        )
        self.con.execute(
            "INSERT INTO main.lab_factor_warehouse_vintages_v1 VALUES "
            f"('DGS2','{OBSERVED}','{HEX_B}','{INGESTED}',4.0,"
            f"'percent','{INGESTED}','government_source_via_treasury',"
            "'treasury','factor-run-1')"
        )
        self.con.execute(
            "INSERT INTO main.lab_prospective_event_factor_grid_v1 VALUES "
            f"('run-1','kalshi','mkt-1','{HEX_A}','{AT}','p-1',0.43,"
            f"'DGS2','{OBSERVED}','{HEX_B}','{INGESTED}',4.0,'percent',"
            f"'{INGESTED}','government_source_via_treasury','treasury',"
            "'factor-run-1',true,true,false,false,false,false,"
            "'internal_research_only','unreviewed_factor_coobservation_grid')"
        )

    def tearDown(self):
        self.con.close()

    def report(self):
        return check.inspect(self.con,"main.")

    def test_research_lineage_is_copy_consistent_but_never_pit_certified(self):
        r = self.report()
        self.assertEqual(r["status"], "PASS_RESEARCH_WAREHOUSE_LINEAGE_ONLY")
        self.assertEqual(r["persisted_grid_rows"], 1)
        self.assertEqual(r["factor_observed_lag_min_calendar_days"], 1)
        self.assertEqual(r["factor_observed_lag_max_calendar_days"], 1)
        self.assertFalse(r["original_publisher_first_available_at_verified"])
        self.assertFalse(r["data_redistribution_approved"])
        self.assertFalse(r["historical_pit_backtest_released"])
        self.assertFalse(r["institutional_risk_beta_released"])

    def test_missing_source_capture_blocks(self):
        self.con.execute("DELETE FROM main.lab_live_event_features_v1")
        r = self.report()
        self.assertEqual(r["event_capture_source_rows_missing"], 1)
        self.assertEqual(r["status"], "BLOCKED_RESEARCH_SOURCE_LINEAGE")

    def test_event_hash_or_probability_source_drift_blocks(self):
        self.con.execute("UPDATE main.lab_live_event_features_v1 SET probability=0.6")
        self.assertEqual(self.report()["event_capture_identity_or_payload_drift"],1)
        self.con.execute("UPDATE main.lab_live_event_features_v1 SET probability=0.43")
        self.con.execute("UPDATE main.lab_live_event_features_v1 SET source_record_sha256='altered'")
        self.assertEqual(self.report()["event_capture_identity_or_payload_drift"],1)

    def test_missing_factor_vintage_blocks(self):
        self.con.execute("DELETE FROM main.lab_factor_warehouse_vintages_v1")
        self.assertEqual(self.report()["factor_vintage_source_rows_missing"],1)

    def test_factor_value_and_factor_license_source_drift_block(self):
        self.con.execute("UPDATE main.lab_factor_warehouse_vintages_v1 SET factor_value=3.9")
        self.assertEqual(self.report()["factor_vintage_value_or_metadata_drift"],1)
        self.con.execute("UPDATE main.lab_factor_warehouse_vintages_v1 SET factor_value=4.0")
        self.con.execute("UPDATE main.lab_factor_warehouse_vintages_v1 SET license_class='restricted'")
        self.assertEqual(self.report()["factor_vintage_value_or_metadata_drift"],1)

    def test_future_factor_availability_blocked(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_available_at='2026-10-25 12:00:00'")
        r=self.report()
        self.assertEqual(r["invalid_warehouse_timing_or_age_rows"],1)
        self.assertEqual(r["status"],"BLOCKED_RESEARCH_SOURCE_LINEAGE")

    def test_old_factor_window_blocked_even_when_historic(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_observed_date='2026-10-01'")
        self.assertEqual(self.report()["invalid_warehouse_timing_or_age_rows"],1)

    def test_future_observation_day_blocks_even_when_ingested_early(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_observed_date='2026-10-26'")
        self.assertEqual(self.report()["invalid_warehouse_timing_or_age_rows"],1)

    def test_explicit_research_only_license_and_relation_status(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_license_class='restricted_ice_bofa'")
        self.assertEqual(self.report()["invalid_factor_source_payload_or_license_rows"],1)
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_license_class='government_source_via_treasury',"
            "relation_status='approved_causal_link'")
        self.assertEqual(self.report()["unsupported_provenance_or_release_claim_rows"],1)

    def test_false_publisher_time_or_risk_release_claims_block(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET factor_publication_time_independently_verified=true,"
            "historical_backtest_released=true")
        self.assertEqual(self.report()["unsupported_provenance_or_release_claim_rows"],1)

    def test_null_counters_and_invalid_source_digests_block(self):
        self.con.execute(
            "UPDATE main.lab_prospective_event_factor_grid_v1 "
            "SET event_receipt_time_verified=null,event_source_sha256='bad'")
        r=self.report()
        self.assertEqual(r["unsupported_provenance_or_release_claim_rows"],1)
        self.assertEqual(r["invalid_factor_source_payload_or_license_rows"],1)

    def test_duplicate_capture_source_identity_rejected(self):
        self.con.execute(
            "INSERT INTO main.lab_live_event_features_v1 "
            "SELECT * FROM main.lab_live_event_features_v1")
        r=self.report()
        self.assertEqual(r["duplicate_event_capture_source_keys"],1)
        self.assertEqual(r["source_join_row_amplification"],1)
        self.assertEqual(r["status"],"BLOCKED_RESEARCH_SOURCE_LINEAGE")

    def test_duplicate_factor_vintage_source_identity_rejected(self):
        self.con.execute(
            "INSERT INTO main.lab_factor_warehouse_vintages_v1 "
            "SELECT * FROM main.lab_factor_warehouse_vintages_v1")
        r=self.report()
        self.assertEqual(r["duplicate_factor_source_vintage_keys"],1)
        self.assertEqual(r["source_join_row_amplification"],1)

    def test_empty_persisted_grid_blocks(self):
        self.con.execute("DELETE FROM main.lab_prospective_event_factor_grid_v1")
        self.assertEqual(self.report()["status"],"BLOCKED_NO_PERSISTED_GRID")

    def test_select_only_and_explicit_nonapproval(self):
        source=SCRIPT.read_text()
        self.assertIn("LEFT JOIN",source)
        self.assertIn("source_join_row_amplification",source)
        self.assertIn("first_available_at_verified",source)
        self.assertNotIn("con.execute('INSERT",source)
        self.assertNotIn('con.execute("CREATE',source)


if __name__ == "__main__":
    unittest.main()
