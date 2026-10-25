"""Offline methodology negative controls: no source grant, no historical PIT."""
import importlib.util
from pathlib import Path
import sys
import unittest

LAB = Path(__file__).resolve().parents[1] / "lab"
spec=importlib.util.spec_from_file_location("event_temporal_methodology",
    LAB/"phase1_event_surprise_temporal_methodology.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)
SHA_A="a"*64
SHA_B="b"*64


def market():
    return {
        "event_id":"event-2026-01","contract_version":"immutable-terms-v1",
        "announcement_published_at":"2026-10-25T12:00:00Z",
        "pre_provider_quote_at":"2026-10-25T11:55:00Z",
        "post_provider_quote_at":"2026-10-25T12:05:00Z",
        "pre_quote_received_at":"2026-10-25T11:55:02Z",
        "post_quote_received_at":"2026-10-25T12:05:02Z",
        "pre_probability":0.40,"post_probability":0.55,
        "pre_quote_source_sha256":SHA_A,"post_quote_source_sha256":SHA_B,
        "decision_asof_at":"2026-10-25T12:06:00Z"
    }


def macro():
    return {
        "release_id":"cpi-2026-09","series_id":"CPI-YOY",
        "unit":"percent_yoy","announcement_scheduled_at":"2026-10-25T12:00:00Z",
        "first_print_published_at":"2026-10-25T12:00:01Z",
        "first_print_received_at":"2026-10-25T12:00:02Z",
        "consensus_published_at":"2026-10-25T11:30:00Z",
        "consensus_received_at":"2026-10-25T11:31:00Z",
        "decision_asof_at":"2026-10-25T12:05:00Z",
        "actual_first_print":2.8,"expected_pre_release":2.5,
        "frozen_consensus_std":0.15,
        "actual_source_sha256":SHA_A,
        "consensus_source_sha256":SHA_B,
        "first_print_revision_id":"initial-release-v1"
    }


class TemporalIdentificationTests(unittest.TestCase):
    def reject(self, fn, record, field, value, expected):
        d=dict(record);d[field]=value
        with self.assertRaisesRegex(m.MethodologyRejected,expected):
            fn(d)

    def test_belief_revision_is_not_macro_surprise_or_approved_causal_shock(self):
        result=m.belief_revision(market())
        self.assertAlmostEqual(result["belief_revision_probability_points"],15)
        self.assertIsNone(result["event_surprise_probability_points"])
        self.assertEqual(result["original_quote_pre_age_seconds"],300)
        self.assertEqual(result["original_quote_post_lag_seconds"],300)
        self.assertFalse(result["identified_causal_event_shock"])
        self.assertFalse(result["institutional_beta_released"])
        self.assertFalse(result["original_provider_timestamps_independently_authenticated"])

    def test_frozen_macro_surprise_retains_source_unit_and_unverified_state(self):
        r=m.macro_release_surprise(macro())
        self.assertAlmostEqual(r["macro_surprise_source_native_units"],.3)
        self.assertAlmostEqual(r["macro_surprise_frozen_consensus_std_units"],2.)
        self.assertEqual(r["source_native_unit"],"percent_yoy")
        self.assertIsNone(r["market_probability_belief_revision_pp"])
        self.assertFalse(r["released_for_historical_pit_backtesting"])

    def test_event_original_quote_timestamp_must_be_pre_and_post_event(self):
        self.reject(m.belief_revision,market(),"pre_provider_quote_at",
                    "2026-10-25T12:00:00Z","pre-registered event window")
        self.reject(m.belief_revision,market(),"post_provider_quote_at",
                    "2026-10-25T11:59:59Z","pre-registered event window")

    def test_original_quote_must_be_pre_event_receipt_and_as_known(self):
        self.reject(m.belief_revision,market(),"pre_quote_received_at",
                    "2026-10-25T12:01:00Z","receipt chronology")
        self.reject(m.belief_revision,market(),"decision_asof_at",
                    "2026-10-25T12:00:00Z","receipt chronology")

    def test_original_quote_window_cap_prevents_post_hoc_horizon_tuning(self):
        with self.assertRaisesRegex(m.MethodologyRejected,"Pre-registered"):
            m.belief_revision(market(),pre_window_minutes=0)
        with self.assertRaisesRegex(m.MethodologyRejected,"Pre-registered"):
            m.belief_revision(market(),post_window_minutes=3000)
        with self.assertRaisesRegex(m.MethodologyRejected,"Pre-registered"):
            m.belief_revision(market(),pre_window_minutes=True)
        self.reject(m.belief_revision,market(),"post_provider_quote_at",
                    "2026-10-25T14:00:00Z","pre-registered event window")

    def test_contract_must_remain_known_and_versioned(self):
        self.reject(m.belief_revision,market(),"contract_version",None,"Missing original")
        self.reject(m.belief_revision,market(),"event_id","","Event ID")
        self.reject(m.belief_revision,market(),"pre_quote_source_sha256","bad","SHA256")

    def test_probabilities_are_normalized_before_percent_point_change(self):
        self.reject(m.belief_revision,market(),"pre_probability",1.2,"Out of range")
        self.reject(m.belief_revision,market(),"post_probability",float("nan"),"finite")
        self.reject(m.belief_revision,market(),"pre_probability",True,"finite")

    def test_macro_consensus_must_be_known_pre_release_not_retrospective(self):
        self.reject(m.macro_release_surprise,macro(),"consensus_received_at",
                    "2026-10-25T12:01:00Z","chronology")
        self.reject(m.macro_release_surprise,macro(),"consensus_published_at",
                    "2026-10-25T12:01:00Z","chronology")
        self.reject(m.macro_release_surprise,macro(),"first_print_received_at",
                    "2026-10-25T11:55:00Z","chronology")

    def test_macro_frozen_dispersion_must_exist_before_holdout(self):
        self.reject(m.macro_release_surprise,macro(),"frozen_consensus_std",0,"positive")
        self.reject(m.macro_release_surprise,macro(),"frozen_consensus_std",
                    float("inf"),"finite")
        self.reject(m.macro_release_surprise,macro(),"expected_pre_release",None,
                    "Missing original")
        self.reject(m.macro_release_surprise,macro(),"unit","unknown","Unknown")

    def test_unpublished_first_print_never_substituted_with_observation_date(self):
        self.reject(m.macro_release_surprise,macro(),"first_print_published_at",None,
                    "Missing original")
        self.reject(m.macro_release_surprise,macro(),"first_print_published_at",
                    "2026-10-25T00:00:00","naive clock")
        self.reject(m.macro_release_surprise,macro(),"first_print_published_at",
                    "2026-10-25T11:59:00Z","chronology")

    def test_user_fabricated_license_or_approval_fails_closed(self):
        self.reject(m.belief_revision,market(),"licensed_risk_use_approved",True,
                    "Unsupported fields")
        self.reject(m.macro_release_surprise,macro(),"surprise_methodology_approved",True,
                    "Unsupported fields")
        self.reject(m.macro_release_surprise,macro(),"original_pit_verified",False,
                    "Unsupported fields")

    def test_cross_timezone_equivalent_times_work_as_instants(self):
        d=market()
        d["announcement_published_at"]="2026-10-25T05:00:00-07:00"
        self.assertAlmostEqual(m.belief_revision(d)["belief_revision_probability_points"],15)

    def test_no_api_no_writes_or_automatic_approval_in_source(self):
        source=(LAB/"phase1_event_surprise_temporal_methodology.py").read_text()
        self.assertNotIn("duckdb.connect",source)
        self.assertNotIn("requests.get",source)
        self.assertNotIn("urllib.request",source)
        self.assertNotIn("INSERT INTO",source)
        self.assertIn("released_for_historical_pit_backtesting",source)


if __name__=="__main__":
    unittest.main()
