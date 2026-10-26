"""Falsification tests: technical retrospective panel acceptance != viable funding beta.

Fast in-memory DuckDB-only fixtures, no remote markets or institutional approval.
"""
import importlib.util
from pathlib import Path
import sys
import unittest
import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
spec=importlib.util.spec_from_file_location("phase1_release_gates",LAB/"phase1_release_gates.py")
gates=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=gates
spec.loader.exec_module(gates)

def synthetic():
    con=duckdb.connect(":memory:")
    con.execute("""CREATE TABLE main.lab_joint_funding_daily_loss_builds_v1(
        build_id VARCHAR,built_at TIMESTAMP)""")
    con.execute("""INSERT INTO main.lab_joint_funding_daily_loss_builds_v1
        VALUES ('original-retro-2026','2026-10-26')""")
    con.execute("""CREATE TABLE main.lab_joint_funding_daily_paired_losses_v1 AS
        SELECT 'original-retro-2026' AS build_id,
          printf('ASSET%02d',asset) AS ticker,
          CASE WHEN v=0 THEN 'full_training'
               ELSE 'training_tail_exclusion' END AS model_variant,
          DATE '2025-12-15'+CAST(d AS INTEGER) AS heldout_date,
          FALSE AS original_issuer_prices_asof_verified,
          FALSE AS original_factor_publication_asof_verified,
          FALSE AS licensed_risk_use_approved,
          FALSE AS institutional_beta_released
        FROM range(48) assets(asset) CROSS JOIN range(2) variants(v)
             CROSS JOIN range(209) dates(d)""")
    con.execute("""CREATE TABLE main.lab_joint_funding_familywise_builds_v1(
        build_id VARCHAR,built_at TIMESTAMP)""")
    con.execute("""INSERT INTO main.lab_joint_funding_familywise_builds_v1
        VALUES ('holm-96-retro-2026','2026-10-26')""")
    con.execute("""CREATE TABLE main.lab_joint_funding_familywise_models_v1 AS
        SELECT 'holm-96-retro-2026' AS build_id,
          printf('ASSET%02d',asset) AS ticker,
          CASE WHEN v=0 THEN 'full_training'
               ELSE 'training_tail_exclusion' END AS variant,
          0.3::DOUBLE AS nominal_hac_p,
          0.9::DOUBLE AS holm_familywise_p,
          FALSE AS holm_p_below_05,
          'REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING'::VARCHAR
             AS familywise_research_state,
          FALSE AS institutional_beta_released
        FROM range(48) assets(asset) CROSS JOIN range(2) variants(v)""")
    return con

def results(con):
    return [con.execute(sql).fetchone()[0] for _,sql,_,_,_
            in gates.funding_model_evidence_gate_specs("main.")]

class JointFundingReleaseGateTests(unittest.TestCase):
    def test_source_controls_and_51_to_54_definition_are_version_locked(self):
        specifications=gates.funding_model_evidence_gate_specs("main.")
        self.assertEqual([x[0] for x in specifications],[
          "joint_funding_daily_loss_retrospective_rectangular_research",
          "joint_funding_global_holm_audit_rectangular_research",
          "joint_funding_both_training_variants_holm_robust_candidate"])
        self.assertEqual([x[2] for x in specifications],[1,1,1])
        self.assertEqual([x[3] for x in specifications],["MIN_COUNT"]*3)
        self.assertEqual(gates.VERSION,"phase1-gates-v2.4.0")
        s=(LAB/"phase1_release_gates.py").read_text()
        self.assertIn("*funding_model_evidence_gate_specs(P),",s)
        self.assertIn("'BLOCKED_NOT_INSTITUTIONALLY_APPROVED'",s)

    def test_complete_research_tables_pass_technical_but_not_robustness(self):
        with synthetic() as con:
            self.assertEqual(results(con),[1,1,0])

    def test_all_rectangles_missing_one_daily_loss_is_a_block(self):
        with synthetic() as con:
            con.execute("""DELETE FROM main.lab_joint_funding_daily_paired_losses_v1
                WHERE ticker='ASSET00' AND model_variant='full_training'
                      AND heldout_date='2025-12-15'""")
            self.assertEqual(results(con),[0,1,0])

    def test_duplicate_loss_row_fails_even_if_source_coverage_looks_full(self):
        with synthetic() as con:
            con.execute("""INSERT INTO main.lab_joint_funding_daily_paired_losses_v1
                 SELECT * FROM main.lab_joint_funding_daily_paired_losses_v1
                 WHERE ticker='ASSET00' LIMIT 1""")
            self.assertEqual(results(con),[0,1,0])

    def test_false_issuer_or_beta_approval_disallows_research_acceptance(self):
        with synthetic() as con:
            con.execute("""UPDATE main.lab_joint_funding_daily_paired_losses_v1
                 SET licensed_risk_use_approved=TRUE
                 WHERE ticker='ASSET00'""")
            self.assertEqual(results(con),[0,1,0])

    def test_96_audit_duplicate_identity_prevents_falsely_complete_screen(self):
        with synthetic() as con:
            con.execute("""INSERT INTO main.lab_joint_funding_familywise_models_v1
                 SELECT * FROM main.lab_joint_funding_familywise_models_v1
                 WHERE ticker='ASSET00' LIMIT 1""")
            self.assertEqual(results(con),[1,0,0])

    def test_unadjusted_claim_and_positive_approval_fail_holm_audit(self):
        with synthetic() as con:
            con.execute("""UPDATE main.lab_joint_funding_familywise_models_v1
                 SET holm_familywise_p=0.001
                 WHERE ticker='ASSET00'""")
            self.assertEqual(results(con),[1,0,0])
        with synthetic() as con:
            con.execute("""UPDATE main.lab_joint_funding_familywise_models_v1
                 SET institutional_beta_released=TRUE
                 WHERE ticker='ASSET00'""")
            self.assertEqual(results(con),[1,0,0])

    def test_a_single_favorable_variant_cannot_be_promoted(self):
        with synthetic() as con:
            con.execute("""UPDATE main.lab_joint_funding_familywise_models_v1
                 SET holm_familywise_p=.001,
                     nominal_hac_p=.0001,
                     holm_p_below_05=TRUE,
                     familywise_research_state=
                       'RESEARCH_MULTIPLICITY_SCREEN_PASS_NOT_INSTITUTIONAL'
                 WHERE ticker='ASSET00' AND variant='full_training'""")
            self.assertEqual(results(con),[1,1,0])

    def test_both_original_training_variants_can_pass_research_gate_not_rights(self):
        with synthetic() as con:
            con.execute("""UPDATE main.lab_joint_funding_familywise_models_v1
                 SET holm_familywise_p=.001,
                     nominal_hac_p=.0001,
                     holm_p_below_05=TRUE,
                     familywise_research_state=
                       'RESEARCH_MULTIPLICITY_SCREEN_PASS_NOT_INSTITUTIONAL'
                 WHERE ticker='ASSET00'""")
            self.assertEqual(results(con),[1,1,1])
            # The non-approval source basis still remains untouched.
            self.assertEqual(con.execute("""
              SELECT count(*) FROM main.lab_joint_funding_familywise_models_v1
              WHERE institutional_beta_released""").fetchone()[0],0)

    def test_missing_source_tables_never_claim_research_complete(self):
        with synthetic() as con:
            con.execute("DELETE FROM main.lab_joint_funding_daily_loss_builds_v1")
            con.execute("DELETE FROM main.lab_joint_funding_familywise_builds_v1")
            self.assertEqual(results(con),[0,0,0])

if __name__=="__main__":
    unittest.main()
