"""Synthetic SQL tests for binding prospective sample-support release gates.

No production release, publisher provenance, source license or warehouse
materialization. Does NOT authorize passing merely by multiplying venue
contracts, factor IDs, archive dates or repeated collection rows.
"""
from datetime import date,timedelta
import importlib.util
from pathlib import Path
import sys
import unittest
import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location(
    "phase1_release_gates",LAB/"phase1_release_gates.py")
gates=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=gates
spec.loader.exec_module(gates)


def simulate(days=3,runs=11,variable=False,static_factor=None):
    con=duckdb.connect(":memory:")
    con.execute("""CREATE TABLE main.lab_prospective_event_factor_grid_v1 (
        event_capture_at TIMESTAMP,event_run_id VARCHAR,factor_id VARCHAR,
        factor_observed_date DATE,factor_value DOUBLE
    )""")
    start=date(2026,1,1)
    records=[]
    for run in range(runs):
        day=start+timedelta(days=(run if days==runs else run%days))
        for factor_i in range(18):
            factor=f"RISK_FACTOR_{factor_i:02d}"
            if factor==static_factor:
                observed=start
                value=1.0
            elif variable:
                observed=day
                value=float((run if days==runs else run%days)+factor_i*.1)
            else:
                observed=start
                value=float(factor_i*.1)
            records.append((day.isoformat(),f"capture_{run:04d}",
                            factor,observed.isoformat(),value))
    con.executemany(
        "INSERT INTO main.lab_prospective_event_factor_grid_v1 VALUES (?,?,?,?,?)",
        records)
    return con


def values(con):
    return [con.execute(statement).fetchone()[0] for _,statement,_,_,_
            in gates.prospective_empirical_support_gate_specs("main.")]


class SourceVariationInstitutionalGateTests(unittest.TestCase):
    def test_prespecified_four_release_gate_ids_and_thresholds_are_locked(self):
        specs=gates.prospective_empirical_support_gate_specs("main.")
        self.assertEqual([x[0] for x in specs],[
            "prospective_capture_calendar_diversity",
            "prospective_capture_run_diversity",
            "prospective_per_factor_original_observation_day_depth",
            "prospective_nonconstant_rate_factor_support"])
        self.assertEqual([x[2] for x in specs],[60,60,30,18])
        self.assertTrue(all(x[3]=="MIN_COUNT" for x in specs))
        self.assertIn("phase1-gates-v2.3.0",gates.VERSION)
        self.assertTrue(all("lab_prospective_event_factor_grid_v1" in x[1]
                            for x in specs))

    def test_prospective_three_calendar_days_with_eleven_runs_blocks_all_four(self):
        with simulate() as con:
            counts=values(con)
        self.assertEqual(counts,[3,11,1,0])
        self.assertTrue(all(x<spec[2] for x,spec in zip(
            counts,gates.prospective_empirical_support_gate_specs("main."))))

    def test_65_actual_distinct_dates_and_original_variation_pass_research_depth(self):
        with simulate(days=65,runs=65,variable=True) as con:
            counts=values(con)
        self.assertEqual(counts,[65,65,65,18])
        self.assertTrue(all(x>=spec[2] for x,spec in zip(
            counts,gates.prospective_empirical_support_gate_specs("main."))))

    def test_same_constant_factor_even_with_65_capture_days_cannot_pass(self):
        with simulate(days=65,runs=65,variable=False) as con:
            self.assertEqual(values(con),[65,65,1,0])

    def test_one_factor_without_temporal_support_blocks_full_eighteen_factor_screen(self):
        with simulate(days=65,runs=65,variable=True,
                      static_factor="RISK_FACTOR_05") as con:
            self.assertEqual(values(con),[65,65,1,17])

    def test_many_runs_on_three_days_do_not_create_factor_date_depth(self):
        with simulate(days=3,runs=65,variable=True) as con:
            self.assertEqual(values(con),[3,65,3,0])

    def test_blank_grid_never_passes_minimum_source_diversity(self):
        with simulate(days=3,runs=0,variable=False) as con:
            self.assertEqual(values(con),[0,0,0,0])

    def test_executable_release_script_records_four_new_gates_only_on_rebuild(self):
        source=(LAB/"phase1_release_gates.py").read_text()
        self.assertIn("*prospective_empirical_support_gate_specs(P),",source)
        self.assertIn('VERSION="phase1-gates-v2.3.0"',source)
        self.assertIn("institutional",source.lower())
        self.assertIn("source_script_sha256",source)
        # This code cannot retroactively change existing stored 22/47 gates:
        # a separately authorized versioned producer execution is required.
        self.assertNotIn("UPDATE main.lab_release_gate_summary_v1",source)


if __name__=="__main__":
    unittest.main()
