"""Synthetic negative controls for as-of event-factor sample pseudoreplication.

NOT source-certified releases, historical venue quotes or financial evidence.
"""
from datetime import date,datetime,timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
spec=importlib.util.spec_from_file_location(
    "phase1_prospective_effective_information",
    LAB/"phase1_prospective_effective_information.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def fixture(captures=3,archived_days=65,independent_factor_dates=1,
            markets_per_capture=3):
    con=duckdb.connect(":memory:")
    con.execute("""
      CREATE TABLE main.lab_prospective_event_factor_grid_v1 (
       event_run_id VARCHAR,event_capture_at TIMESTAMP,
       venue VARCHAR,market_id VARCHAR,proposition_id VARCHAR,
       factor_id VARCHAR,factor_observed_date DATE,
       factor_source_sha256 VARCHAR,factor_value DOUBLE,
       event_delta_pp DOUBLE,previous_event_capture_at TIMESTAMP,
       exchange_quote_time_independently_verified BOOLEAN,
       factor_publication_time_independently_verified BOOLEAN,
       event_to_factor_mapping_approved BOOLEAN,
       historical_backtest_released BOOLEAN,
       data_use_class VARCHAR,relation_status VARCHAR
      )
    """)
    con.execute("""
      CREATE TABLE main.lab_factor_warehouse_vintages_v1 (
        factor_id VARCHAR,factor_observed_date DATE,
        source_record_sha256 VARCHAR
      )
    """)
    start=date(2026,1,1)
    archive=[]
    for factor in ("DGS2","DGS10"):
        for i in range(archived_days):
            archive.append((factor,start+timedelta(days=i),
                           f"{factor}:{i:04d}"))
    con.executemany("INSERT INTO main.lab_factor_warehouse_vintages_v1 VALUES (?,?,?)",
                    archive)
    grid=[]
    for run in range(captures):
        dt=datetime(2026,1,1)+timedelta(days=run)
        for market in range(markets_per_capture):
            for factor in ("DGS2","DGS10"):
                observed_idx=run % independent_factor_dates
                grid.append((
                    f"run-{run}",dt,"kalshi",f"market-{market}",f"prop-{market}",
                    factor,start+timedelta(days=observed_idx),
                    f"{factor}:{observed_idx:04d}",float(observed_idx),
                    0.2 if run else None,dt-timedelta(days=1) if run else None,
                    False,False,False,False,"internal_research_only",
                    "unreviewed_factor_coobservation_grid",
                ))
    con.executemany("""
      INSERT INTO main.lab_prospective_event_factor_grid_v1
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",grid)
    return con


class EffectiveInformationResearchTests(unittest.TestCase):
    def test_large_archive_does_not_create_prospective_factor_time_variation(self):
        con=fixture(captures=3,archived_days=65,independent_factor_dates=1)
        try:
            out=m.inspect(con,"main.")
        finally:
            con.close()
        self.assertEqual(out["stored_event_factor_rows"],18)
        self.assertEqual(out["capture_calendar_days"],3)
        self.assertEqual(out["unique_capture_market_keys"],9)
        self.assertEqual(out["factor_warehouse_archived_observation_dates"],65)
        self.assertEqual(out["prospective_factor_observed_dates"],1)
        self.assertEqual(out["prospective_source_factor_vintages"],2)
        self.assertEqual(out["research_factors_with_estimable_time_series_variation"],0)
        self.assertEqual(out["status"],"BLOCKED_PROSPECTIVE_FACTOR_STATISTICAL_ESTIMATION")
        self.assertTrue(all(f["factor_held_constant_across_all_captures"]
                            for f in out["per_factor"]))
        self.assertFalse(out["institutional_risk_factor_model_approved"])

    def test_many_markets_do_not_substitute_for_independent_factor_dates(self):
        with fixture(captures=3,archived_days=65,independent_factor_dates=1,
                     markets_per_capture=120) as con:
            out=m.inspect(con,"main.")
        self.assertEqual(out["stored_event_factor_rows"],720)
        self.assertEqual(out["research_factors_with_estimable_time_series_variation"],0)
        self.assertEqual(out["prospective_source_factor_vintages"],2)
        self.assertEqual(out["factor_source_records_per_capture_market_row"],2.0)

    def test_many_genuine_prospective_factor_dates_only_allow_research_screen(self):
        with fixture(captures=65,archived_days=65,
                     independent_factor_dates=65) as con:
            out=m.inspect(con,"main.")
        self.assertEqual(out["capture_calendar_days"],65)
        self.assertEqual(out["research_factors_with_estimable_time_series_variation"],2)
        self.assertEqual(out["status"],
                         "PROSPECTIVE_VARIATION_SCREEN_ELIGIBLE_RESEARCH_ONLY")
        self.assertFalse(out["source_first_published_pit_approved"])
        self.assertFalse(out["causal_event_to_factor_beta_approved"])
        self.assertFalse(out["institutional_risk_factor_model_approved"])

    def test_future_rights_or_causal_claims_reject_the_source_ledger(self):
        with fixture() as con:
            con.execute(
                "UPDATE main.lab_prospective_event_factor_grid_v1 "
                "SET historical_backtest_released=TRUE")
            with self.assertRaisesRegex(ValueError,"false release"):
                m.inspect(con,"main.")

    def test_duplicated_factor_grid_rows_reject_as_nonrectangular(self):
        with fixture() as con:
            con.execute(
                "INSERT INTO main.lab_prospective_event_factor_grid_v1 "
                "SELECT * FROM main.lab_prospective_event_factor_grid_v1 LIMIT 1")
            with self.assertRaisesRegex(ValueError,"factor rectangle"):
                m.inspect(con,"main.")

    def test_missing_source_factor_archive_records_reject(self):
        with fixture() as con:
            con.execute(
                "DELETE FROM main.lab_factor_warehouse_vintages_v1 WHERE factor_id='DGS10'")
            with self.assertRaisesRegex(ValueError,"inventory"):
                m.inspect(con,"main.")

    def test_missing_factor_in_one_capture_prevents_false_coverage(self):
        with fixture() as con:
            con.execute(
                "DELETE FROM main.lab_prospective_event_factor_grid_v1 "
                "WHERE event_run_id='run-1' AND market_id='market-2' AND factor_id='DGS2'")
            with self.assertRaisesRegex(ValueError,"factor rectangle"):
                m.inspect(con,"main.")

    def test_negative_or_noninteger_ledger_counts_fail_closed(self):
        good=(18,3,3,3,3,9,2,1,2,2,6,0,
              "2026-01-01","2026-01-03")
        src=(130,2,65)
        factors=[("DGS2",9,3,1,1,1,65),("DGS10",9,3,1,1,1,65)]
        with self.assertRaisesRegex(ValueError,"source counters"):
            m.evaluate((*good[:10],-1,*good[11:]),src,factors)
        with self.assertRaisesRegex(ValueError,"source counters"):
            m.evaluate((18.0,*good[1:]),src,factors)

    def test_inconsistent_per_factor_source_support_fails(self):
        good=(18,3,3,3,3,9,2,1,2,2,6,0,
              "2026-01-01","2026-01-03")
        src=(130,2,65)
        factors=[("DGS2",9,3,1,1,1,65),("DGS10",8,3,1,1,1,65)]
        with self.assertRaisesRegex(ValueError,"factor-date support"):
            m.evaluate(good,src,factors)

    def test_cli_does_not_write_and_does_not_interrupt_collector(self):
        s=(LAB/"phase1_prospective_effective_information.py").read_text()
        self.assertIn("lab_factor_warehouse_vintages_v1",s)
        self.assertIn("BLOCKED_PROSPECTIVE_FACTOR_STATISTICAL_ESTIMATION",s)
        self.assertNotIn("INSERT INTO",s)
        self.assertNotIn("UPDATE main.",s)
        self.assertNotIn("CREATE TABLE",s)
        # Prospective data *collection* must continue if a model readiness
        # gate fails due to too few days of as-received source observations.
        collector=(LAB.parent/".github/workflows/"
                   "phase1_manual_grid_field_acceptance.yml").read_text()
        self.assertNotIn("phase1_prospective_effective_information.py",collector)


if __name__=="__main__":
    unittest.main()
