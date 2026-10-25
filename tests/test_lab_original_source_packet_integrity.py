"""Adversarial original-source intake contracts, offline only.

Synthetic payload fixtures are for tests and must NEVER be presented as
actual original-source evidence, signed reviews or licensed source releases.
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

LAB = Path(__file__).resolve().parents[1] / "lab"
sys.path.insert(0, str(LAB))
spec = importlib.util.spec_from_file_location(
    "original_source_packet_integrity", LAB / "phase1_original_source_packet_integrity.py"
)
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)

FIXED_NOW = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
PAYLOAD = b"synthetic-fixture-not-real-original-provider-evidence\n"


class OriginalSourcePacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "sample.bin").write_bytes(PAYLOAD)
        self.packet = dict(
            source_family="treasury_par_yields",
            source_record_id="DGS2:2026-10-23:rev1",
            source_uri="https://example.test/official/yields.csv?series=DGS2",
            payload_path="sample.bin",
            payload_sha256=hashlib.sha256(PAYLOAD).hexdigest(),
            capture_received_at="2026-10-25T10:00:00-07:00",
            warehouse_registered_at="2026-10-25T17:10:00Z",
            provider_published_at="2026-10-24T18:00:00Z",
            source_observation_date="2026-10-23",
            source_version="provider-unverified-rev1",
        )

    def tearDown(self):
        self.temp.cleanup()

    def evaluate(self, packet=None):
        return intake.validate(self.packet if packet is None else packet,
                               self.root, now=FIXED_NOW)

    def reject(self, attribute, value, match):
        obj = dict(self.packet)
        obj[attribute] = value
        with self.assertRaisesRegex(intake.PacketRejected, match):
            self.evaluate(obj)

    def test_actual_bytes_equal_claim_but_provider_and_rights_remain_unverified(self):
        report = self.evaluate()
        self.assertTrue(report["local_payload_sha256_integrity_pass"])
        self.assertEqual(report["payload_byte_count"], len(PAYLOAD))
        self.assertEqual(report["source_sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(report["http_or_local_capture_received_at"],
                         "2026-10-25T17:00:00+00:00")
        self.assertEqual(report["source_uri_redacted"],
                         "https://example.test/official/yields.csv")
        self.assertEqual(report["provider_publication_clock_claimed_at"],
                         "2026-10-24T18:00:00+00:00")
        for flag in (
            "provider_publication_independently_verified",
            "original_provider_payload_authenticity_independently_verified",
            "first_available_to_market_independently_verified",
            "commercial_data_rights_approved",
            "independent_second_reviewer_approved",
            "event_factor_mapping_approved",
            "historical_pit_backtest_released",
            "institutional_risk_use_approved",
        ):
            with self.subTest(flag=flag):
                self.assertIs(report[flag], False)

    def test_byte_mutation_or_wrong_hash_is_rejected(self):
        (self.root / "sample.bin").write_bytes(PAYLOAD + b"changed")
        with self.assertRaisesRegex(intake.PacketRejected, "SHA256 mismatch"):
            self.evaluate()
        self.reject("payload_sha256", "0" * 64, "SHA256 mismatch")
        self.reject("payload_sha256", "INVALID", "64 lowercase hex")

    def test_no_fake_publication_from_http_receipt_or_forecast_timestamps(self):
        self.reject("provider_published_at", "2026-10-25T17:05:01Z",
                    "later than receipt")
        self.reject("capture_received_at", "2026-10-25T21:00:00Z",
                    "future time")
        self.reject("warehouse_registered_at", "2026-10-25T16:59:59Z",
                    "cannot precede")
        self.reject("capture_received_at", "2026-10-25T17:00:00",
                    "naive clock")
        self.reject("capture_received_at", "2026-15-20T17:00:00Z",
                    "invalid ISO")

    def test_revised_after_capture_or_prior_to_original_claim_fails(self):
        self.reject("provider_revision_at", "2026-10-25T17:01:00Z",
                    "revision/publication order")
        self.reject("provider_revision_at", "2026-10-23T00:00:00Z",
                    "revision/publication order")
        obj = dict(self.packet)
        del obj["provider_published_at"]
        obj["provider_revision_at"] = "2026-10-25T15:00:00Z"
        with self.assertRaisesRegex(intake.PacketRejected, "revision/publication order"):
            self.evaluate(obj)

    def test_original_clock_optional_but_no_implicit_verification(self):
        obj = dict(self.packet)
        del obj["provider_published_at"]
        result = self.evaluate(obj)
        self.assertIsNone(result["provider_publication_clock_claimed_at"])
        self.assertFalse(result["provider_publication_independently_verified"])

    def test_stray_source_approval_or_license_claims_fail_closed(self):
        for key in ("licensed_market_data_approved",
                    "institutional_risk_use_approved", "reviewer_signed_at",
                    "historic_first_available_at", "verified_issuer_actions"):
            with self.subTest(key=key):
                self.reject(key, False, "Unsupported packet fields")
        obj = dict(self.packet)
        obj.pop("capture_received_at")
        with self.assertRaisesRegex(intake.PacketRejected, "Required evidence metadata"):
            self.evaluate(obj)

    def test_source_registry_is_exact_existing_16_source_families(self):
        from phase1_source_family_evidence import SOURCES
        self.assertEqual(intake.ALLOWED_SOURCE_FAMILIES,
                         {s.domain for s in SOURCES})
        self.reject("source_family", "made_up_credit_feed", "Unregistered source family")

    def test_directory_escape_absolute_and_symlink_escape_denied(self):
        self.reject("payload_path", "../sample.bin", "traversal")
        self.reject("payload_path", str(self.root / "sample.bin"), "absolute")
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "outside.bin"
            outside.write_bytes(PAYLOAD)
            (self.root / "link.bin").symlink_to(outside)
            self.reject("payload_path", "link.bin", "outside approved intake root")

    def test_credential_bearing_source_url_is_never_reported(self):
        self.reject("source_uri", "http://example.test/data", "require HTTPS")
        self.reject("source_uri", "https://user:pw@example.test/data",
                    "without credentials")
        self.reject("source_uri", "https://example.test/data?api_key=secret",
                    "without credentials")
        self.reject("source_uri", "https://example.test/data?sig=secret",
                    "without credentials")

    def test_packet_identity_deterministic_and_source_key_sensitive(self):
        first = self.evaluate()["packet_id"]
        self.assertEqual(first, self.evaluate()["packet_id"])
        obj = dict(self.packet)
        obj["source_record_id"] += "-2"
        self.assertNotEqual(first, self.evaluate(obj)["packet_id"])

    def test_empty_payload_and_invalid_observation_date_rejected(self):
        (self.root / "sample.bin").write_bytes(b"")
        with self.assertRaisesRegex(intake.PacketRejected, "empty or oversized"):
            self.evaluate()
        (self.root / "sample.bin").write_bytes(PAYLOAD)
        self.reject("source_observation_date", "2026-02-31", "date invalid")

    def test_cli_sanitizes_output_and_never_writes_a_database(self):
        (self.root / "manifest.json").write_text(json.dumps(self.packet))
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            rc = intake.main(["--packet", str(self.root / "manifest.json"),
                              "--root", str(self.root)])
        self.assertEqual(rc, 0)
        payload = json.loads(o.getvalue())
        self.assertFalse(payload["institutional_risk_use_approved"])
        self.assertNotIn("?series=", o.getvalue())
        self.assertEqual(e.getvalue(), "")
        self.assertEqual({p.name for p in self.root.iterdir()},
                         {"sample.bin", "manifest.json"})

    def test_cli_rejects_without_echoing_a_secret(self):
        p = dict(self.packet)
        p["source_uri"] = "https://example.test/feeds?token=VERYPRIVATE"
        (self.root / "manifest.json").write_text(json.dumps(p))
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            rc = intake.main(["--packet", str(self.root / "manifest.json"),
                              "--root", str(self.root)])
        self.assertEqual(rc, 2)
        self.assertNotIn("VERYPRIVATE", o.getvalue() + e.getvalue())
        self.assertEqual(o.getvalue(), "")
        self.assertIn("PACKET_REJECTED:", e.getvalue())


if __name__ == "__main__":
    unittest.main()
