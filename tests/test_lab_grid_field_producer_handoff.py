"""Offline verification of manual research producer handoff and safety controls."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import re
import sys
import tempfile
import unittest

LAB = Path(__file__).resolve().parents[1] / "lab"
spec = importlib.util.spec_from_file_location(
    "phase1_grid_field_producer_handoff", LAB / "phase1_grid_field_producer_handoff.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
COMMIT = "a" * 40
DIGEST = "b" * 64
GOOD_GRID = (COMMIT, DIGEST, "immutable-grid-build", 0, 0, 0, 0,
             "MATERIALIZED_RESEARCH_ONLY")
GOOD_FIELDS = (COMMIT, DIGEST, "immutable-field-build", 16, 274, 135, 1, 255,
               False, "RELEASE_BLOCKED_SOURCE_CERTIFICATIONS_INCOMPLETE")


class ProducerManifestChecks(unittest.TestCase):
    def test_zero_new_capture_noop_is_legitimate_research_run(self):
        report = v.verify_grid(GOOD_GRID, COMMIT, DIGEST)
        self.assertEqual(report["new_grid_rows"], 0)
        self.assertFalse(report["institutional_release_approved"])
        self.assertEqual(report["status"], "RESEARCH_PRODUCER_MANIFEST_VERIFIED")

    def test_grid_mismatched_source_falsely_certified_or_temporally_leaking_fails(self):
        for idx, wrong in ((0, "c" * 40), (1, "0" * 64),
                           (2, ""), (3, -1), (4, -4),
                           (5, 1), (6, 1), (7, "INSTITUTIONAL_APPROVED")):
            with self.subTest(index=idx):
                row = list(GOOD_GRID)
                row[idx] = wrong
                with self.assertRaisesRegex(ValueError, "incompatible or approved"):
                    v.verify_grid(tuple(row), COMMIT, DIGEST)
        with self.assertRaisesRegex(ValueError, "Missing or incompatible"):
            v.verify_grid(None, COMMIT, DIGEST)

    def test_field_contract_requires_all_255_uncertified(self):
        report = v.verify_fields(GOOD_FIELDS, COMMIT, DIGEST)
        self.assertEqual((report["source_domains"], report["field_rules"]), (16, 274))
        self.assertEqual(report["required_fields_missing"], 135)
        self.assertEqual(report["required_fields_empty"], 1)
        self.assertEqual(report["required_fields_uncertified"], 255)
        self.assertFalse(report["institutional_release_approved"])

    def test_wrong_counts_source_provenance_and_approvals_fail_closed(self):
        for idx, wrong in ((0, "0" * 40), (1, "0" * 64), (2, ""),
                           (3, 15), (4, 273), (5, -1),
                           (6, 256), (7, 254), (8, True),
                           (9, "PRODUCTION_READY")):
            with self.subTest(index=idx):
                row = list(GOOD_FIELDS)
                row[idx] = wrong
                with self.assertRaisesRegex(ValueError, "incompatible or falsely released"):
                    v.verify_fields(tuple(row), COMMIT, DIGEST)

    def test_offline_mock_reads_only_the_relevant_latest_manifest(self):
        class FakeResult:
            def __init__(self, row):
                self.row = row
            def fetchone(self):
                return self.row
        class FakeConnection:
            def __init__(self):
                self.queries = []
            def execute(self, statement):
                self.queries.append(statement)
                if "lab_prospective_grid_runs_v1" in statement:
                    return FakeResult(GOOD_GRID)
                if "lab_institutional_data_contract_builds_v1" in statement:
                    return FakeResult(GOOD_FIELDS)
                raise AssertionError("Unexpected query")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "phase1_warehouse_asof_grid.py").write_text("research grid script")
            (p / "phase1_field_coverage.py").write_text("research field script")
            # Real SHA digests belong to the actual source files; mocks replace
            # verify_grid/verify_fields inputs with exactly those mock file digests.
            grid = list(GOOD_GRID)
            fields = list(GOOD_FIELDS)
            grid[1] = v.local_sha(p / "phase1_warehouse_asof_grid.py")
            fields[1] = v.local_sha(p / "phase1_field_coverage.py")
            class SourceConnection(FakeConnection):
                def execute(self, statement):
                    self.queries.append(statement)
                    return FakeResult(tuple(grid) if "lab_prospective_grid_runs_v1" in statement
                                      else tuple(fields))
            con = SourceConnection()
            result = v.verify(con, commit=COMMIT,
                              mode="incremental_grid_and_field_contracts", lab=p)
            self.assertEqual(len(result["producers"]), 2)
            self.assertEqual(len(con.queries), 2)
            self.assertTrue(all("SELECT " in s for s in con.queries))
            self.assertFalse(result["publisher_first_publication_verified"])
            self.assertFalse(result["institutional_release_approved"])

    def test_nonpinned_or_nonallowlisted_operation_fails(self):
        for sha, mode in ((COMMIT[:10], "incremental_grid_only"),
                          (COMMIT, "full_historical_replay"),
                          (COMMIT, "approve_production"),
                          (COMMIT, "preflight_only")):
            with self.subTest(sha=sha, mode=mode), self.assertRaises(ValueError):
                v.verify(object(), commit=sha, mode=mode, lab=LAB)

    def test_manual_actions_default_readonly_and_explicitly_safeguarded(self):
        workflow = (LAB.parent / ".github" / "workflows" /
                    "phase1_manual_grid_field_acceptance.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("default: preflight_only", workflow)
        self.assertIn("confirm_research_writes:", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("RESEARCH_WRITE_ACK", workflow)
        self.assertIn("LAB_GRID_FULL_REPLAY: \"false\"", workflow)
        self.assertIn("group: factor-lab-prospective-capture", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("secrets.MOTHERDUCK_TOKEN", workflow)
        self.assertIn("python lab/phase1_grid_field_producer_handoff.py", workflow)
        self.assertIn("RESEARCH_ONLY_VALIDATION=TRUE INSTITUTIONAL_RELEASE=FALSE",
                      workflow)
        self.assertNotIn("cron:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("MotherDuck Flight v2 execution: **NOT CLAIMED", workflow)


if __name__ == "__main__":
    unittest.main()
