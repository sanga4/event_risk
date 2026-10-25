"""Offline adversarial validation of institutional contract typing and field-gap ledger.

No network, MotherDuck Flight, provider credentials, warehouse writes or
institutional authorization. Exercises pure reconciliation and type rules.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import importlib.util
import sys
import unittest

LAB = Path(__file__).resolve().parents[1] / "lab"
sys.path.insert(0, str(LAB))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, LAB / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gap = load("field_gap_snapshot", "phase1_source_field_gap_preflight.py")
types = load("institutional_field_types", "phase1_field_coverage.py")


def fixture():
    build_id = "fixed-contract-audit"
    build = dict(
        build_id=build_id, built_at="2026-10-25T00:00:00Z",
        source_git_commit="a" * 40, contracts_defined=2,
        field_rules_defined=5, required_fields_missing=1,
        required_fields_unpopulated=1, uncertified_required_fields=4,
        institutional_release_approved=False,
    )
    def field(dataset, source, name, level, status, exists=True, rows=10,
              expected="STRING_OR_DEFINED"):
        return dict(
            build_id=build_id, dataset_id=dataset, source_table=source,
            field_name=name, requirement_level=level,
            source_table_exists=exists, source_table_rows=rows,
            expected_type_class=expected,
            type_class_pass=None if status == "MISSING_FIELD" else True,
            inventory_status=status, independently_certified_for_production=False,
        )

    fields = [
        field("event_quote_receipt", "receipts", "run_id", "technical",
              "POPULATED_NOT_CERTIFIED"),
        field("event_quote_receipt", "receipts", "provider_quote_at", "institutional",
              "EMPTY", expected="TIMESTAMPTZ"),
        field("event_quote_receipt", "receipts", "yes_bid", "optional",
              "PARTIALLY_POPULATED", expected="NUMERIC_OR_DEFINED"),
        field("security_price", "prices", "close", "technical",
              "POPULATED_NOT_CERTIFIED", expected="NUMERIC_OR_DEFINED"),
        field("security_price", "prices", "permanent_security_id", "institutional",
              "MISSING_FIELD", expected="STRING"),
    ]
    datasets = [
        dict(build_id=build_id, dataset_id="event_quote_receipt",
             source_table="receipts", table_exists=True, source_row_count=10,
             total_fields_required=2, required_fields_missing=0,
             required_fields_unpopulated=1, populated_required_fields=1,
             source_certification_complete=False,
             status="REQUIRED_SOURCE_FIELDS_UNPOPULATED"),
        dict(build_id=build_id, dataset_id="security_price",
             source_table="prices", table_exists=True, source_row_count=10,
             total_fields_required=2, required_fields_missing=1,
             required_fields_unpopulated=0, populated_required_fields=1,
             source_certification_complete=False,
             status="REQUIRED_SOURCE_FIELDS_MISSING"),
    ]
    return build, fields, datasets


class InstitutionalFieldTypeSafety(unittest.TestCase):
    def test_license_permission_and_approval_flags_are_boolean(self):
        for key in ("price_license_approved", "licensed_redistribution",
                    "source_use_approved", "vendor_rights_approved",
                    "provider_quote_freshness_verified",
                    "independent_data_rights_verified"):
            with self.subTest(key=key):
                self.assertEqual(types.expected_type_class(key), "BOOLEAN")
                self.assertFalse(types.satisfies_type("BOOLEAN", "STRING"))
                self.assertTrue(types.satisfies_type("BOOLEAN", "BOOLEAN"))

    def test_beta_uncertainty_and_effective_sample_are_numeric(self):
        for key in ("calendar_cluster_robust_se", "n_effective",
                    "standard_error", "beta"):
            with self.subTest(key=key):
                self.assertEqual(types.expected_type_class(key), "NUMERIC_OR_DEFINED")
                self.assertFalse(types.satisfies_type("NUMERIC_OR_DEFINED", "STRING"))

    def test_checksum_and_identity_types_reject_numeric_substitutes(self):
        for key in ("source_payload_sha256", "record_sha256",
                    "source_record_sha256", "evidence_sha256",
                    "source_digest", "permanent_security_id"):
            with self.subTest(key=key):
                self.assertEqual(types.expected_type_class(key), "STRING")
                self.assertFalse(types.satisfies_type("STRING", "NUMERIC"))
                self.assertTrue(types.satisfies_type("STRING", "STRING"))

    def test_original_source_date_requires_temporal_not_text(self):
        self.assertEqual(types.expected_type_class("source_published_at"), "TIMESTAMPTZ")
        self.assertFalse(types.satisfies_type("TIMESTAMPTZ", "STRING"))
        self.assertTrue(types.satisfies_type("TIMESTAMPTZ", "TIMESTAMPTZ"))


class SourceFieldEvidenceTests(unittest.TestCase):
    def test_reconciles_missing_and_empty_without_claiming_source_certification(self):
        build, fields, datasets = fixture()
        report = gap.analyze(build, fields, datasets, earlier_missing=3)
        self.assertEqual((report["dataset_count"], report["field_rules"],
                          report["required_total"]), (2, 5, 4))
        self.assertEqual(report["required_missing"], 1)
        self.assertEqual(report["required_empty"], 1)
        self.assertEqual(report["required_populated_but_uncertified"], 2)
        self.assertEqual(report["required_independently_uncertified"], 4)
        self.assertEqual(report["missing_change_from_previous_build"], -2)
        self.assertEqual(report["disposition"], "BLOCKED_NOT_INSTITUTIONALLY_APPROVED")
        self.assertFalse(report["institutional_release_approved"])
        self.assertFalse(report["provider_publication_time_certified_by_this_report"])
        self.assertEqual(report["datasets"][0]["dataset_id"], "event_quote_receipt")
        self.assertEqual(report["datasets"][0]["empty_required"][0]["field"],
                         "provider_quote_at")

    def assert_invalid(self, mutate, reason):
        b, f, d = fixture()
        mutate(b, f, d)
        with self.assertRaisesRegex(ValueError, reason):
            gap.analyze(b, f, d)

    def test_missing_field_rows_fail_closed(self):
        self.assert_invalid(lambda b, f, d: f.pop(), "Incomplete audit rows")

    def test_build_mixing_is_not_silently_combined(self):
        self.assert_invalid(lambda b, f, d: f[0].update(build_id="prior"),
                            "Mixed audit builds")

    def test_duplicate_field_is_rejected_even_with_rebalanced_count(self):
        def mutate(b, f, d):
            f.append(deepcopy(f[0]))
            b["field_rules_defined"] += 1
        self.assert_invalid(mutate, "Duplicate institutional contract field")

    def test_false_approval_cannot_count_as_coverage(self):
        self.assert_invalid(lambda b, f, d:
                            f[0].update(independently_certified_for_production=True),
                            "Unsubstantiated independent field approval")
        self.assert_invalid(lambda b, f, d:
                            b.update(institutional_release_approved=True),
                            "cannot authorize production")

    def test_data_set_field_totals_must_reconcile(self):
        self.assert_invalid(lambda b, f, d:
                            d[0].update(required_fields_unpopulated=0),
                            "Per-dataset audit totals")

    def test_inconsistent_stored_source_counts_are_rejected(self):
        self.assert_invalid(lambda b, f, d:
                            f[0].update(source_table_rows=99),
                            "Source row count changed")

    def test_mismatch_not_trivially_marked_type_valid(self):
        def mutate(b, f, d):
            f[4]["inventory_status"] = "TYPE_MISMATCH"
            f[4]["type_class_pass"] = True
        self.assert_invalid(mutate, "Type mismatch cannot be marked type-valid")

    def test_missing_data_wont_be_mislabelled_as_present(self):
        def mutate(b, f, d):
            f[4]["inventory_status"] = "MISSING_DATASET"
            f[4]["type_class_pass"] = None
        self.assert_invalid(mutate, "Missing dataset contradicted")

    def test_script_is_select_only_and_version_scoped(self):
        source = (LAB / "phase1_source_field_gap_preflight.py").read_text()
        self.assertIn("WHERE build_id = ?", source)
        self.assertIn("ORDER BY built_at DESC", source)
        self.assertIn("LAST_COMPLETED_AUDIT_SNAPSHOT_NOT_LIVE_SOURCE_RESCAN", source)
        self.assertNotIn('con.execute("INSERT', source)
        self.assertNotIn('con.execute("UPDATE', source)


if __name__ == "__main__":
    unittest.main()
