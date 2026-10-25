#!/usr/bin/env python3
"""Two distinct, temporally explicit EventRisk Phase I research estimands.

1. Prediction-market belief revision: 100*(post_prob-pre_prob) in probability
   points using ORIGINAL quote clocks on the same unchanged contract.
2. Macroeconomic release surprise: first_published_actual - pre-release
   consensus in strictly matching source units, optionally scaled by a frozen
   pre-release forecast dispersion.

Neither measurement is by itself an exogenous event shock, causal estimate,
tradeable market surprise, independently source-verified PIT record, or beta.
These pure functions never fetch sources, write data, issue licenses or certify
reviewer approvals. Missing original clocks MUST fail closed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re

RESEARCH_ONLY = "MEASUREMENT_CANDIDATE_EXTERNAL_PIT_RIGHTS_AND_CAUSAL_REVIEW_REQUIRED"
HASH = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_UNITS = frozenset((
    "basis_points", "index_points", "percent_yoy", "percent_annualized",
    "thousands", "millions", "currency_native", "persons", "ratio",
))
MAX_WINDOW_MINUTES = 1440


class MethodologyRejected(ValueError):
    """Evidence or chronological eligibility is insufficient."""


def at(value: str, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 50:
        raise MethodologyRejected(f"{field}: timezone-aware ISO-8601 clock required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MethodologyRejected(f"{field}: invalid ISO-8601 clock") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise MethodologyRejected(f"{field}: naive clock prohibited")
    return dt.astimezone(timezone.utc)


def field(record: dict, name: str):
    if not isinstance(record, dict) or name not in record or record[name] is None:
        raise MethodologyRejected(f"Missing original source field: {name}")
    return record[name]


def number(record: dict, name: str) -> float:
    v = field(record, name)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise MethodologyRejected(f"{name}: finite numeric source required")
    return float(v)


def sha(record: dict, name: str) -> str:
    s = field(record, name)
    if not isinstance(s, str) or not HASH.fullmatch(s):
        raise MethodologyRejected(f"{name}: immutable exact SHA256 expected")
    return s


def no_approval_inputs(record: dict, allowed: set[str]) -> None:
    if not isinstance(record, dict) or set(record) - allowed:
        raise MethodologyRejected("Unsupported fields, including caller-supplied approval assertions")


def disposition() -> dict:
    return {
        "status": RESEARCH_ONLY,
        "original_provider_timestamps_independently_authenticated": False,
        "original_source_bytes_independently_authenticated": False,
        "vendor_rights_approved": False,
        "surprise_methodology_independently_approved": False,
        "identified_causal_event_shock": False,
        "released_for_historical_pit_backtesting": False,
        "institutional_beta_released": False,
    }


def belief_revision(record: dict, *, pre_window_minutes: int = 60,
                    post_window_minutes: int = 30) -> dict:
    """Measure a descriptive change in SAME-contract beliefs around an event.

    Provider quote-publication clock is NOT warehouse receipt clock. Revisions
    may represent market liquidity, rumor, term changes or endogenous news;
    no unexpected-event or economic-causality label is assigned.
    """
    allowed = {
        "event_id", "contract_version", "announcement_published_at",
        "pre_provider_quote_at", "post_provider_quote_at",
        "pre_quote_received_at", "post_quote_received_at",
        "pre_probability", "post_probability",
        "pre_quote_source_sha256", "post_quote_source_sha256",
        "pre_contract_sha256", "post_contract_sha256",
        "decision_asof_at",
    }
    no_approval_inputs(record, allowed)
    if (type(pre_window_minutes) is not int or
        type(post_window_minutes) is not int or
        not 1 <= pre_window_minutes <= MAX_WINDOW_MINUTES or
        not 1 <= post_window_minutes <= MAX_WINDOW_MINUTES):
        raise MethodologyRejected("Pre-registered event time windows must be 1–1440 minutes")
    event_id = field(record, "event_id")
    contract = field(record, "contract_version")
    if not isinstance(event_id,str) or not 1 <= len(event_id) <= 200:
        raise MethodologyRejected("Event ID missing or malformed")
    if not isinstance(contract,str) or not 1 <= len(contract) <= 200:
        raise MethodologyRejected("Original contract-version identity required")
    announce = at(field(record,"announcement_published_at"),"announcement_published_at")
    pre = at(field(record,"pre_provider_quote_at"),"pre_provider_quote_at")
    post = at(field(record,"post_provider_quote_at"),"post_provider_quote_at")
    pre_seen = at(field(record,"pre_quote_received_at"),"pre_quote_received_at")
    post_seen = at(field(record,"post_quote_received_at"),"post_quote_received_at")
    asof = at(field(record,"decision_asof_at"),"decision_asof_at")
    if not (announce - timedelta(minutes=pre_window_minutes) <= pre < announce
            <= post <= announce + timedelta(minutes=post_window_minutes)):
        raise MethodologyRejected("Original quote publication outside pre-registered event window")
    if not (pre <= pre_seen < announce <= post <= post_seen <= asof):
        raise MethodologyRejected("Quote receipt chronology cannot establish pre/post as-known pair")
    p0 = number(record,"pre_probability")
    p1 = number(record,"post_probability")
    if not 0 <= p0 <= 1 or not 0 <= p1 <= 1:
        raise MethodologyRejected("Out of range quote probability")
    sha(record,"pre_quote_source_sha256")
    sha(record,"post_quote_source_sha256")
    if sha(record,"pre_contract_sha256") != sha(record,"post_contract_sha256"):
        raise MethodologyRejected("Changed event contract terms across quoted event window")
    # A quote changing at event time is NOT itself an independent announcement
    # surprise; the exact source clock claims must be independently reviewed.
    return {
        "measure": "MARKET_BELIEF_REVISION_NOT_EVENT_SURPRISE",
        "event_id": event_id,
        "contract_version": contract,
        "belief_revision_probability_points": 100.0 * (p1-p0),
        "pre_probability": p0,
        "post_probability": p1,
        "original_quote_pre_age_seconds": (announce-pre).total_seconds(),
        "original_quote_post_lag_seconds": (post-announce).total_seconds(),
        "event_surprise_probability_points": None,
        **disposition(),
    }


def macro_release_surprise(record: dict) -> dict:
    """First-print macro release minus frozen pre-announcement consensus.

    Statistical 'surprise' is a deviation from a prespecified expectation,
    not the change in a prediction-market price and not a causal beta.
    """
    allowed = {
        "release_id", "series_id", "unit", "announcement_scheduled_at",
        "first_print_published_at", "first_print_received_at",
        "consensus_published_at", "consensus_received_at", "decision_asof_at",
        "actual_first_print", "expected_pre_release",
        "frozen_consensus_std", "actual_source_sha256",
        "consensus_source_sha256", "first_print_revision_id",
        "actual_unit", "consensus_unit",
    }
    no_approval_inputs(record, allowed)
    for name in ("release_id","series_id","first_print_revision_id"):
        v = field(record, name)
        if not isinstance(v,str) or not 1 <= len(v) <= 200:
            raise MethodologyRejected(f"{name}: original source version identity required")
    unit = field(record,"unit")
    if (unit not in ALLOWED_UNITS
        or field(record,"actual_unit") != unit
        or field(record,"consensus_unit") != unit):
        raise MethodologyRejected("Unknown or mismatched source-native release units")
    scheduled=at(field(record,"announcement_scheduled_at"),"announcement_scheduled_at")
    first=at(field(record,"first_print_published_at"),"first_print_published_at")
    first_seen=at(field(record,"first_print_received_at"),"first_print_received_at")
    expected_at=at(field(record,"consensus_published_at"),"consensus_published_at")
    expected_seen=at(field(record,"consensus_received_at"),"consensus_received_at")
    asof=at(field(record,"decision_asof_at"),"decision_asof_at")
    if not (expected_at <= expected_seen < scheduled <= first
            <= first_seen <= asof):
        raise MethodologyRejected("Consensus or first-print chronology violates frozen event cutoff")
    actual = number(record,"actual_first_print")
    expected = number(record,"expected_pre_release")
    sd = number(record,"frozen_consensus_std")
    if sd <= 0:
        raise MethodologyRejected("Frozen pre-release dispersion must be positive")
    sha(record,"actual_source_sha256")
    sha(record,"consensus_source_sha256")
    surprise = actual - expected
    return {
        "measure": "MACRO_FIRST_PRINT_MINUS_PRE_RELEASE_CONSENSUS",
        "release_id": record["release_id"],
        "series_id": record["series_id"],
        "first_print_revision_id": record["first_print_revision_id"],
        "source_native_unit": unit,
        "macro_surprise_source_native_units": surprise,
        "macro_surprise_frozen_consensus_std_units": surprise/sd,
        "announcement_to_first_print_seconds": (first-scheduled).total_seconds(),
        "market_probability_belief_revision_pp": None,
        **disposition(),
    }
