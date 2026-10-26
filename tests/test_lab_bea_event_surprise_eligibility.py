"""Offline adversarial tests for immutable BEA receipt and non-surprise eligibility."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
import phase1_bea_event_surprise_eligibility as mod

BUILD = "phase1-bea-original-release-values-receipt-v1.0.0-test-pinned"
COMMIT = "a" * 40
GATE = "phase1-gates-v2.4.0-test-pinned"
UTC = timezone.utc
RECEIVED = datetime(2026, 10, 26, 3, 23, 52, tzinfo=UTC)
INGESTED = RECEIVED + timedelta(seconds=2)


def fixture():
    packets, values, pins = [], [], {}
    for kind, url in mod.SOURCE_URLS.items():
        raw = ("Immutable source bytes for " + kind).encode() * 600
        digest = hashlib.sha256(raw).hexdigest()
        pins[kind] = digest
        packets.append({
            "build_id": BUILD, "source_git_commit": COMMIT,
            "source_kind": kind, "source_url": url,
            "source_http_received_at": RECEIVED, "warehouse_ingested_at": INGESTED,
            "original_html": raw, "original_payload_sha256": digest,
            "parsed_observation_count": len(mod.EXPECTED_METRICS[kind]),
            "source_status": mod.SOURCE_STATE,
            **{key: False for key in mod.PACKET_FALSE},
        })
        for metric in sorted(mod.EXPECTED_METRICS[kind]):
            trade_values = {
                "deficit_reported_magnitude": 105.6,
                "exports_reported_magnitude": 315.2,
                "imports_reported_magnitude": 420.8,
            }
            is_trade = kind == "aug2026_international_trade"
            values.append({
                "build_id": BUILD, "source_kind": kind,
                "original_payload_sha256": digest,
                "reported_period": "2026-08", "reported_metric": metric,
                "reported_value": trade_values[metric] if is_trade else 0.3,
                "prior_month_value": None if is_trade else 0.1,
                "reported_unit": "usd_billions" if is_trade else "percent_change_from_previous_month",
                "source_http_received_at": RECEIVED,
                "warehouse_ingested_at": INGESTED,
                "publisher_first_known_at": None,
                "verified_announcement_surprise": None,
                **{key: False for key in mod.VALUE_FALSE},
            })
    gate = {
        "build_id": GATE, "asof_utc": RECEIVED - timedelta(hours=1),
        "computed_gates": 54, "passed_gates": 25,
        "blocked_gates": 29, "external_manual_gates": 4,
        "released_to_institutional_production": False,
        "release_state": mod.RELEASE_STATE,
    }
    return packets, values, gate, pins


def run(p, v, g, hashes):
    return mod.audit(p, v, g, source_build=BUILD, producer_commit=COMMIT,
                     gate_build=GATE, packet_shas=hashes)


class OriginalBEAEconomicGateTests(unittest.TestCase):
    def setUp(self):
        self.p, self.v, self.g, self.pins = fixture()

    def check_reject(self):
        with self.assertRaises(ValueError):
            run(self.p, self.v, self.g, self.pins)

    def test_actuals_accepted_only_as_research_receipt(self):
        result = run(self.p, self.v, self.g, self.pins)
        self.assertEqual(result["verified_native_value_rows"], 10)
        self.assertEqual(result["admissible_first_print_surprise_rows"], 0)
        self.assertTrue(result["gate_predates_latest_source_ingestion"])
        self.assertTrue(result["gate_refresh_required_to_evaluate_new_source"])
        self.assertFalse(result["institutional_release_approved"])
        self.assertEqual(result["trade_accounting_residual_usd_billions"], 0)

    def test_gate_snapshot_after_ingestion_is_fresh_but_not_approval(self):
        self.g["asof_utc"] = INGESTED + timedelta(minutes=1)
        result = run(self.p, self.v, self.g, self.pins)
        self.assertFalse(result["gate_refresh_required_to_evaluate_new_source"])
        self.assertFalse(result["institutional_release_approved"])
        self.assertEqual(result["admissible_first_print_surprise_rows"], 0)

    def test_altered_original_blob_fails_digest(self):
        self.p[0]["original_html"] += b"changed"
        self.check_reject()

    def test_unpinned_payload_digest_fails_even_with_matching_blob(self):
        self.p[0]["original_html"] += b"changed"
        self.p[0]["original_payload_sha256"] = hashlib.sha256(self.p[0]["original_html"]).hexdigest()
        self.check_reject()

    def test_swapped_source_url_rejected(self):
        self.p[0]["source_url"] = "https://www.bea.gov/news/2026/other"
        self.check_reject()

    def test_mixed_source_build_rejected(self):
        self.p[0]["build_id"] = "someone-elses-build"
        self.check_reject()

    def test_mixed_value_build_rejected(self):
        self.v[0]["build_id"] = "someone-elses-build"
        self.check_reject()

    def test_duplicate_source_packet_rejected(self):
        self.p[1] = copy.deepcopy(self.p[0])
        self.check_reject()

    def test_missing_observation_rejected(self):
        self.v.pop()
        self.check_reject()

    def test_duplicate_observation_rejected(self):
        self.v[1] = copy.deepcopy(self.v[0])
        self.check_reject()

    def test_false_first_known_timestamp_rejected(self):
        self.v[0]["publisher_first_known_at"] = RECEIVED
        self.check_reject()

    def test_fabricated_announcement_surprise_rejected(self):
        self.v[0]["verified_announcement_surprise"] = 0.1
        self.check_reject()

    def test_claimed_rights_approval_rejected(self):
        self.p[0]["redistribution_rights_approved"] = True
        self.check_reject()

    def test_unknown_rights_flag_rejected(self):
        self.p[0]["redistribution_rights_approved"] = None
        self.check_reject()

    def test_publisher_pit_claim_rejected(self):
        self.v[0]["original_provider_first_release_certified"] = True
        self.check_reject()

    def test_unverified_consensus_claim_rejected(self):
        self.v[0]["survey_consensus_asof_verified"] = True
        self.check_reject()

    def test_incorrect_reported_unit_rejected(self):
        self.v[0]["reported_unit"] = "percentage_points_surprise"
        self.check_reject()

    def test_wrong_observation_period_rejected(self):
        self.v[0]["reported_period"] = "2026-09"
        self.check_reject()

    def test_missing_prior_month_pce_rejected(self):
        value = next(r for r in self.v if r["source_kind"] == "aug2026_personal_income")
        value["prior_month_value"] = None
        self.check_reject()

    def test_nonfinite_numeric_rejected(self):
        self.v[0]["reported_value"] = float("nan")
        self.check_reject()

    def test_boolean_metric_rejected(self):
        self.v[0]["reported_value"] = True
        self.check_reject()

    def test_wrong_deficit_sign_or_accounting_identity_rejected(self):
        value = next(r for r in self.v if r["reported_metric"] == "deficit_reported_magnitude")
        value["reported_value"] = 100.0
        self.check_reject()

    def test_rounding_tolerance_under_015_billion_allowed(self):
        value = next(r for r in self.v if r["reported_metric"] == "deficit_reported_magnitude")
        value["reported_value"] = 105.7
        self.assertAlmostEqual(run(self.p, self.v, self.g, self.pins)["trade_accounting_residual_usd_billions"], -0.1)

    def test_retrieval_after_warehouse_ingestion_rejected(self):
        self.p[0]["source_http_received_at"] = INGESTED + timedelta(minutes=1)
        self.check_reject()

    def test_naive_utc_time_rejected(self):
        self.p[0]["source_http_received_at"] = RECEIVED.replace(tzinfo=None)
        self.check_reject()

    def test_value_packet_clock_mismatch_rejected(self):
        self.v[0]["warehouse_ingested_at"] = INGESTED + timedelta(seconds=1)
        self.check_reject()

    def test_gate_missing_rejected(self):
        self.g = None
        self.check_reject()

    def test_gate_build_mismatch_rejected(self):
        self.g["build_id"] = "other-gate"
        self.check_reject()

    def test_gate_total_inconsistent_rejected(self):
        self.g["computed_gates"] = 53
        self.check_reject()

    def test_claimed_institutional_release_rejected(self):
        self.g["released_to_institutional_production"] = True
        self.check_reject()

    def test_manual_approval_zero_rejected(self):
        self.g["external_manual_gates"] = 0
        self.check_reject()

    def test_unreviewed_source_git_sha_rejected(self):
        with self.assertRaises(ValueError):
            mod.audit(self.p, self.v, self.g, source_build=BUILD,
                      producer_commit="short", gate_build=GATE, packet_shas=self.pins)

    def test_missing_expected_packet_pin_rejected(self):
        self.pins.pop("aug2026_personal_income")
        self.check_reject()


if __name__ == "__main__":
    unittest.main()
