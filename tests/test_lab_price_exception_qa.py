"""Offline regression checks for market source exceptions. No network/DB secrets."""
from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path

import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location("sourceqa",LAB/"phase1_price_exception_audit.py")
qa=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=qa
spec.loader.exec_module(qa)


class SecurityPriceQAContractTests(unittest.TestCase):
    def test_identifies_raw_duplicates_and_original_large_move(self):
        con=duckdb.connect(":memory:")
        old=qa.P
        qa.P="main."
        try:
            con.execute("""
              CREATE TABLE security_prices(
                ticker VARCHAR,date DATE,close DOUBLE,adj_close DOUBLE,
                volume DOUBLE,currency VARCHAR,source VARCHAR,
                fetched_at TIMESTAMPTZ,run_id VARCHAR)
            """)
            con.execute("""
              CREATE TABLE lab_security_returns_retro_v1(
                ticker VARCHAR,observed_date DATE,previous_observed_date DATE,
                previous_close DOUBLE,adjusted_close DOUBLE,return_bps DOUBLE,
                large_absolute_log_return BOOLEAN)
            """)
            con.execute("""
              CREATE TABLE lab_rate_shocks_retro_v1(
                factor_id VARCHAR,observed_date DATE,shock_bps DOUBLE)
            """)
            con.execute("""
              CREATE TABLE lab_security_rate_betas_retro_v1(
                ticker VARCHAR,factor_id VARCHAR,beta_rate DOUBLE,
                rate_bh_fdr_q DOUBLE,test_r2_vs_spy_only DOUBLE,
                large_return_observations BIGINT)
            """)
            con.execute("""
              INSERT INTO security_prices VALUES
                ('T','2025-02-04',135,135,10000,'USD','yahoo',
                 '2026-10-17 00:34:40+00','r1'),
                ('JPY=X','2026-10-16',158,158,1,'JPY','yahoo',
                 '2026-10-17 00:34:40+00','r1'),
                ('JPY=X','2026-10-16',157,157,1,'JPY','yahoo',
                 '2026-10-17 00:34:40+00','r1')
            """)
            con.execute("""
              INSERT INTO lab_security_returns_retro_v1 VALUES
                ('T','2025-02-04','2025-02-03',100,135,3001,TRUE),
                ('SPY','2025-02-04','2025-02-03',500,505,99.5,FALSE)
            """)
            con.execute("""
              INSERT INTO lab_rate_shocks_retro_v1 VALUES
                ('DGS10','2025-02-04',2)
            """)
            con.execute("""
              INSERT INTO lab_security_rate_betas_retro_v1 VALUES
                ('T','DGS10',-5.0,.03,.1,1)
            """)
            qa.stage(con)
            self.assertEqual(con.execute(
              "SELECT COUNT(*) FROM tmp_price_exceptions").fetchone()[0],1)
            self.assertEqual(con.execute(
              "SELECT COUNT(*) FROM tmp_duplicate_prices").fetchone()[0],1)
            self.assertEqual(con.execute(
              "SELECT COUNT(*) FROM tmp_beta_audit_inputs").fetchone()[0],1)
            self.assertEqual(con.execute(
              "SELECT eligible_for_production_release "
              "FROM tmp_price_exceptions").fetchone()[0],False)
        finally:
            qa.P=old
            con.close()

    def test_does_not_overwrite_source_or_approve_models(self):
        source=(LAB/"phase1_price_exception_audit.py").read_text()
        self.assertNotIn("DELETE FROM",source)
        self.assertIn("FALSE AS eligible_for_production_release",source)
        self.assertIn("VERIFIED_CORPORATE_ACTIONS=0",source)
        self.assertIn("PRODUCTION_BETAS_APPROVED=FALSE",source)

if __name__=="__main__":
    unittest.main()
