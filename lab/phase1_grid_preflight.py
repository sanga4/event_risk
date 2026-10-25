#!/usr/bin/env python3
"""Read-only Phase I warehouse-as-of grid preflight.

This checks *stored capture identity* and warehouse timing integrity without
starting a MotherDuck Flight, changing source data, or approving any provider
publication-time / event-causality / rights claim.

Run: python lab/phase1_grid_preflight.py
Requires a scoped MOTHERDUCK_TOKEN with read access to eventrisk_factor_lab.
"""
from __future__ import annotations

import json
import sys

import duckdb

DB = "eventrisk_factor_lab"
PREFIX = DB + ".main."


def inspect(con, prefix=PREFIX):
    """Return a read-only diagnostic snapshot; prefix can be 'main.' in tests."""
    captures, runs = con.execute(
        f"SELECT count(*), count(DISTINCT run_id) "
        f"FROM {prefix}lab_live_event_features_v1"
    ).fetchone()

    # Deliberately use exactly the same immutable composite identity as the
    # incremental producer. Existence of one factor row covers an identity;
    # adding a *new factor* to a partially covered historical identity instead
    # requires deliberate LAB_GRID_FULL_REPLAY=true, not this fast path.
    pending = con.execute(
        f"""
        SELECT count(*) FROM {prefix}lab_live_event_features_v1 AS e
        WHERE NOT EXISTS (
          SELECT 1 FROM {prefix}lab_prospective_event_factor_grid_v1 AS g
          WHERE g.event_run_id=e.run_id
            AND g.venue=e.venue AND g.market_id=e.market_id
        )
        """
    ).fetchone()[0]

    rows, future, invalid_receipt, unexpected_release = con.execute(
        f"""
        SELECT count(*),
          count(*) FILTER (WHERE factor_ingested_at > event_capture_at
                                  OR factor_available_at > event_capture_at),
          count(*) FILTER (WHERE NOT event_receipt_time_verified
                                  OR NOT factor_warehouse_asof_verified),
          count(*) FILTER (WHERE exchange_quote_time_independently_verified
                                  OR factor_publication_time_independently_verified
                                  OR event_to_factor_mapping_approved
                                  OR historical_backtest_released)
        FROM {prefix}lab_prospective_event_factor_grid_v1
        """
    ).fetchone()

    duplicate_keys = con.execute(
        f"""
        SELECT count(*) FROM (
          SELECT event_run_id, venue, market_id, factor_id
          FROM {prefix}lab_prospective_event_factor_grid_v1
          GROUP BY 1,2,3,4 HAVING count(*) > 1
        ) AS duplicate_groups
        """
    ).fetchone()[0]

    violations = {
        "future_warehouse_factor_rows": future,
        "invalid_warehouse_receipt_flags": invalid_receipt,
        "unexpected_research_approval_rows": unexpected_release,
        "duplicate_event_factor_keys": duplicate_keys,
    }
    if captures == 0 or rows == 0:
        status = "BLOCKED_MISSING_RESEARCH_DATA"
    elif any(violations.values()):
        status = "BLOCKED_GRID_INTEGRITY"
    elif pending > 0:
        status = "INCREMENTAL_CAPTURE_SCOPE_NONEMPTY"
    else:
        status = "INCREMENTAL_CAPTURE_SCOPE_EMPTY"

    return {
        "status": status,
        "data_use_class": "internal_research_only",
        "institutional_historical_pit_release": False,
        "original_provider_publication_time_certified": False,
        "stored_capture_rows": captures,
        "stored_capture_runs": runs,
        "incremental_candidate_capture_rows": pending,
        "persisted_grid_rows": rows,
        **violations,
        "full_replay_note": (
            "No claim about newly eligible factors for previously processed "
            "captures; source/method changes need operator-directed full replay."
        ),
        "flight_run_proven": False,
    }


def main():
    # This script must never write. The connection is scoped to one database;
    # every executed statement above is SELECT-only.
    con = duckdb.connect(f"md:{DB}?attach_mode=single")
    try:
        report = inspect(con)
    finally:
        con.close()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"].startswith("BLOCKED_"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
