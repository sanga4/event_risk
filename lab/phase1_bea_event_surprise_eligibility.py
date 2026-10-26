#!/usr/bin/env python3
"""Read-only Phase I BEA source-economic and release-gate freshness acceptance.

This is a *consistency* check of the already independently accepted original
BEA packet receipt, not a certificate of original first publication, consensus,
historical PIT, source rights, causal surprise, or institutionally approved beta.
Require a caller-pinned immutable warehouse build, Git commit and packet hashes.
No write SQL, HTTP calls, publisher-time inference or approval mutations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
import re

DB = "eventrisk_factor_lab"
PREFIX = DB + ".main."
SOURCE_URLS = {
    "aug2026_personal_income": "https://www.bea.gov/news/2026/personal-income-and-outlays-August-2026",
    "aug2026_international_trade": "https://www.bea.gov/news/2026/us-international-trade-goods-and-services-august-2026",
}
PERSONAL_INCOME_METRICS = frozenset((
    "Current-dollar personal income", "Current-dollar DPI", "Real DPI",
    "Current-dollar PCE", "Real PCE", "PCE price index",
    "PCE price index excluding food and energy",
))
TRADE_METRICS = frozenset((
    "deficit_reported_magnitude", "exports_reported_magnitude",
    "imports_reported_magnitude",
))
EXPECTED_METRICS = {
    "aug2026_personal_income": PERSONAL_INCOME_METRICS,
    "aug2026_international_trade": TRADE_METRICS,
}
SOURCE_STATE = "ORIGINAL_BEA_RELEASE_PAGE_RETRIEVED_LATER_NOT_FIRST_PUBLICATION"
RELEASE_STATE = "BLOCKED_NOT_INSTITUTIONALLY_APPROVED"
PACKET_FALSE = (
    "provider_first_publication_verified", "original_revision_vintage_verified",
    "pre_event_consensus_verified", "redistribution_rights_approved",
    "institutional_event_model_approved",
)
VALUE_FALSE = (
    "original_provider_first_release_certified", "survey_consensus_asof_verified",
    "licensed_downstream_use", "institutional_model_approved",
)


def _utc(value):
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _real(value):
    return type(value) in (int, float) and math.isfinite(value)


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def audit(packets, values, gate, *, source_build, producer_commit,
          gate_build, packet_shas):
    """Reject source tampering and unearned publication/rights/release assertions.

    Gate freshness is reported separately from its pass ratio: an earlier gate
    snapshot is NOT proof that a newly captured packet has passed new gates.
    """
    if (not source_build or not gate_build or
        re.fullmatch(r"[0-9a-f]{40}", producer_commit or "") is None or
        set(packet_shas) != set(SOURCE_URLS) or
        not all(_sha(v) for v in packet_shas.values())):
        raise ValueError("Immutable source build, source Git SHA and both packet hashes required")
    if len(packets) != 2 or len(values) != 10:
        raise ValueError("Expected exactly two independently accepted packets and ten values")

    originals = {}
    for row in packets:
        kind = row["source_kind"]
        if (kind not in SOURCE_URLS or kind in originals or
            row["build_id"] != source_build or row["source_git_commit"] != producer_commit or
            row["source_url"] != SOURCE_URLS[kind] or row["source_status"] != SOURCE_STATE or
            row["parsed_observation_count"] != len(EXPECTED_METRICS[kind]) or
            any(row.get(flag) is not False for flag in PACKET_FALSE)):
            raise ValueError("BEA source identity, manifest, or approval flags inconsistent")
        received, ingested = row["source_http_received_at"], row["warehouse_ingested_at"]
        raw = row["original_html"]
        digest = row["original_payload_sha256"]
        if (not _utc(received) or not _utc(ingested) or received > ingested or
            not isinstance(raw, bytes) or not 10000 <= len(raw) <= 1000000 or
            digest != packet_shas[kind] or
            hashlib.sha256(raw).hexdigest() != digest):
            raise ValueError("BEA packet bytes, pinned digest, or actual receipt clocks invalid")
        originals[kind] = row
    if set(originals) != set(SOURCE_URLS):
        raise ValueError("Incomplete official BEA source packet set")

    seen = set()
    numbers = {}
    for row in values:
        kind, metric = row["source_kind"], row["reported_metric"]
        key = (kind, metric)
        if (kind not in originals or key in seen or
            metric not in EXPECTED_METRICS[kind] or row["build_id"] != source_build or
            row["reported_period"] != "2026-08" or
            row["original_payload_sha256"] != originals[kind]["original_payload_sha256"] or
            row["source_http_received_at"] != originals[kind]["source_http_received_at"] or
            row["warehouse_ingested_at"] != originals[kind]["warehouse_ingested_at"] or
            row["publisher_first_known_at"] is not None or
            row["verified_announcement_surprise"] is not None or
            any(row.get(flag) is not False for flag in VALUE_FALSE)):
            raise ValueError("BEA actual source linkage or unearned surprise/rights flag")
        number, previous = row["reported_value"], row["prior_month_value"]
        if not _real(number):
            raise ValueError("Nonfinite or nonnumeric BEA original reported value")
        if kind == "aug2026_personal_income":
            if (row["reported_unit"] != "percent_change_from_previous_month" or
                not _real(previous) or not -100 < number < 100 or not -100 < previous < 100):
                raise ValueError("Invalid PCE/personal-income monthly change unit or comparative")
        elif (row["reported_unit"] != "usd_billions" or previous is not None
              or number <= 0):
            raise ValueError("Trade amounts must be positive source-reported USD billion magnitudes")
        seen.add(key)
        numbers[key] = number
    if seen != {(kind, name) for kind, names in EXPECTED_METRICS.items() for name in names}:
        raise ValueError("Incomplete authentic BEA metric coverage")

    trade = "aug2026_international_trade"
    imports = numbers[(trade, "imports_reported_magnitude")]
    exports = numbers[(trade, "exports_reported_magnitude")]
    deficit = numbers[(trade, "deficit_reported_magnitude")]
    # All three are separately rounded to $0.1bn; allow a <=$0.15bn
    # discrepancy due to independent 1-decimal rounding, not exact equality.
    residual = (imports - exports) - deficit
    if abs(residual) > 0.150000001:
        raise ValueError("Original BEA trade reported magnitudes violate accounting reconciliation")

    if (not gate or gate["build_id"] != gate_build or
        not _utc(gate["asof_utc"]) or
        type(gate["computed_gates"]) is not int or
        type(gate["passed_gates"]) is not int or
        type(gate["blocked_gates"]) is not int or
        type(gate["external_manual_gates"]) is not int or
        gate["computed_gates"] <= 0 or gate["passed_gates"] < 0 or
        gate["blocked_gates"] < 0 or gate["external_manual_gates"] < 1 or
        gate["passed_gates"] + gate["blocked_gates"] != gate["computed_gates"] or
        gate["released_to_institutional_production"] is not False or
        gate["release_state"] != RELEASE_STATE):
        raise ValueError("Historical release gate build missing or falsely approved")

    latest_receipt = max(row["warehouse_ingested_at"] for row in packets)
    gate_stale = gate["asof_utc"] < latest_receipt
    return {
        "research_evidence": "ORIGINAL_BEA_RECEIPT_AND_NATIVE_VALUES_ONLY",
        "source_build": source_build, "producer_commit": producer_commit,
        "packet_sha256": {kind: packet_shas[kind] for kind in sorted(packet_shas)},
        "verified_packet_receipts": 2, "verified_native_value_rows": 10,
        "trade_accounting_residual_usd_billions": round(residual, 8),
        "last_packet_ingested_at_utc": latest_receipt.isoformat(),
        "gate_build": gate_build, "gate_asof_utc": gate["asof_utc"].isoformat(),
        "gate_automatic_passed": gate["passed_gates"],
        "gate_automatic_total": gate["computed_gates"],
        "gate_predates_latest_source_ingestion": gate_stale,
        "gate_refresh_required_to_evaluate_new_source": gate_stale,
        "original_first_publication_verified": False,
        "pre_release_consensus_verified": False,
        "admissible_first_print_surprise_rows": 0,
        "licensed_downstream_use": False,
        "institutional_beta_approved": False,
        "institutional_release_approved": False,
        "disposition": RELEASE_STATE,
    }


def _dicts(cur):
    names = [c[0] for c in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def load(con, source_build, gate_build):
    """SELECT-only, single connection, immutable build-pinned evidence reads."""
    packets = _dicts(con.execute(f"""SELECT build_id,source_git_commit,source_kind,
      source_url,source_http_received_at,original_payload_sha256,original_html,
      parsed_observation_count,warehouse_ingested_at,provider_first_publication_verified,
      original_revision_vintage_verified,pre_event_consensus_verified,
      redistribution_rights_approved,institutional_event_model_approved,source_status
      FROM {PREFIX}lab_bea_original_release_page_receipts_v1
      WHERE build_id=? ORDER BY source_kind""", [source_build]))
    values = _dicts(con.execute(f"""SELECT build_id,source_kind,original_payload_sha256,
      reported_period,reported_metric,reported_value,prior_month_value,reported_unit,
      source_http_received_at,warehouse_ingested_at,publisher_first_known_at,
      verified_announcement_surprise,original_provider_first_release_certified,
      survey_consensus_asof_verified,licensed_downstream_use,institutional_model_approved
      FROM {PREFIX}lab_bea_original_reported_values_v1
      WHERE build_id=? ORDER BY source_kind,reported_metric""", [source_build]))
    gates = _dicts(con.execute(f"""SELECT build_id,asof_utc,computed_gates,
      passed_gates,blocked_gates,external_manual_gates,
      released_to_institutional_production,release_state
      FROM {PREFIX}lab_release_gate_summary_v1 WHERE build_id=?""", [gate_build]))
    if len(gates) != 1:
        raise ValueError("Release gate snapshot must be exactly one pinned row")
    return packets, values, gates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-build", required=True)
    parser.add_argument("--producer-commit", required=True)
    parser.add_argument("--gate-build", required=True)
    parser.add_argument("--income-sha256", required=True)
    parser.add_argument("--trade-sha256", required=True)
    args = parser.parse_args()
    # Validate pins before connecting to any warehouse.
    shas = {
        "aug2026_personal_income": args.income_sha256,
        "aug2026_international_trade": args.trade_sha256,
    }
    if (not args.source_build or not args.gate_build or
        not re.fullmatch(r"[0-9a-f]{40}", args.producer_commit) or
        not all(_sha(s) for s in shas.values())):
        parser.error("Exact pinned warehouse build, original commit and both 64-char SHAs required")
    import duckdb
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        packets, values, gate = load(con, args.source_build, args.gate_build)
        result = audit(packets, values, gate, source_build=args.source_build,
                       producer_commit=args.producer_commit, gate_build=args.gate_build,
                       packet_shas=shas)
    print(json.dumps(result, sort_keys=True, indent=2))
    print("BEA_RECEIPT_ECONOMIC_IDENTITY_AND_RELEASE_FRESHNESS_QA=PASS")


if __name__ == "__main__":
    main()
