#!/usr/bin/env python3
"""Read-only, build-consistent Phase I institutional source-field gap evidence.

This consumes the LAST COMPLETED audit snapshot. It never touches live source
tables, materializes data, creates missing columns, or certifies source rights,
publication clocks, historic PIT correctness or models.

Usage: python lab/phase1_source_field_gap_preflight.py
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import sys

DB = "eventrisk_factor_lab"
P = DB + ".main."

MISSING = frozenset(("MISSING_DATASET", "MISSING_FIELD", "TYPE_MISMATCH"))
EMPTY = frozenset(("EMPTY",))
POPULATED = frozenset(("PARTIALLY_POPULATED", "POPULATED_NOT_CERTIFIED"))
ALL_STATES = MISSING | EMPTY | POPULATED
P0_SOURCE_DOMAINS = frozenset((
    "event_quote_receipt", "market_contract_version",
    "historical_market_quote", "factor_observation",
    "source_release_calendar", "security_price",
    "security_adjusted_return", "event_economic_factor_mapping",
    "event_innovation",
))


def analyze(build: dict, fields: list[dict], datasets: list[dict],
            earlier_missing: int | None = None) -> dict:
    """Reconcile a single immutable audit build; raise on inconsistent source.

    Build and field rows MUST belong to the same materialization. A new schema
    or backfill after that build is not represented by these measurements.
    """
    if not build or not build.get("build_id"):
        raise ValueError("No auditable source-contract build")
    if build["institutional_release_approved"] is not False:
        raise ValueError("Source contract audit cannot authorize production")
    if (len(datasets) != build["contracts_defined"] or
            len(fields) != build["field_rules_defined"]):
        raise ValueError("Incomplete audit rows or incompatible build manifest")

    grouped = defaultdict(list)
    field_keys = set()
    for f in fields:
        key = (f["dataset_id"], f["field_name"])
        if key in field_keys:
            raise ValueError("Duplicate institutional contract field")
        field_keys.add(key)
        if f["build_id"] != build["build_id"] or f["inventory_status"] not in ALL_STATES:
            raise ValueError("Mixed audit builds or unsupported field status")
        if f["requirement_level"] not in ("technical", "institutional", "optional"):
            raise ValueError("Unknown institutional requirement level")
        if f["independently_certified_for_production"] is not False:
            raise ValueError("Unsubstantiated independent field approval")
        if f["inventory_status"] == "TYPE_MISMATCH" and f["type_class_pass"] is not False:
            raise ValueError("Type mismatch cannot be marked type-valid")
        if f["inventory_status"] == "MISSING_DATASET" and f["source_table_exists"]:
            raise ValueError("Missing dataset contradicted by source existence flag")
        if f["inventory_status"] != "MISSING_DATASET" and not f["source_table_exists"]:
            raise ValueError("Existing source inventory contradicted by missing table")
        grouped[f["dataset_id"]].append(f)

    output = []
    missing = empty = populated = uncertified = total_required = 0
    names = set()
    for d in datasets:
        dataset = d["dataset_id"]
        if dataset in names or d["build_id"] != build["build_id"]:
            raise ValueError("Duplicate or mixed-build dataset report")
        names.add(dataset)
        group = grouped.pop(dataset, None)
        if not group:
            raise ValueError("Dataset has no field contract records")
        if {f["source_table"] for f in group} != {d["source_table"]}:
            raise ValueError("Mismatch between source table contracts")
        if d["source_certification_complete"] is not False:
            raise ValueError("Source dataset cannot be certified by inventory alone")
        req = [f for f in group if f["requirement_level"] != "optional"]
        gaps = [f for f in req if f["inventory_status"] in MISSING]
        blanks = [f for f in req if f["inventory_status"] in EMPTY]
        have = [f for f in req if f["inventory_status"] in POPULATED]
        if (len(req) != d["total_fields_required"] or
                len(gaps) != d["required_fields_missing"] or
                len(blanks) != d["required_fields_unpopulated"] or
                len(have) != d["populated_required_fields"]):
            raise ValueError("Per-dataset audit totals do not reconcile")
        if any(f["source_table_rows"] != d["source_row_count"] for f in group):
            raise ValueError("Source row count changed within an audit build")
        if any(f["source_table_exists"] != d["table_exists"] for f in group):
            raise ValueError("Source table existence changed within an audit build")
        missing += len(gaps)
        empty += len(blanks)
        populated += len(have)
        uncertified += sum(not f["independently_certified_for_production"] for f in req)
        total_required += len(req)
        output.append({
            "dataset_id": dataset,
            "source_table": d["source_table"],
            "priority": "P0_SOURCE_EVIDENCE" if dataset in P0_SOURCE_DOMAINS else "P1_MODEL_OR_SCOPE",
            "source_table_rows_at_audit": d["source_row_count"],
            "status_at_audit": d["status"],
            "required_fields": len(req),
            "populated_required_not_certified": len(have),
            "missing_required": [
                {"field": f["field_name"], "state": f["inventory_status"],
                 "level": f["requirement_level"], "expected_type": f["expected_type_class"]}
                for f in sorted(gaps, key=lambda x: x["field_name"])
            ],
            "empty_required": [
                {"field": f["field_name"], "state": f["inventory_status"],
                 "level": f["requirement_level"], "expected_type": f["expected_type_class"]}
                for f in sorted(blanks, key=lambda x: x["field_name"])
            ],
        })
    if grouped:
        raise ValueError("Orphan field records absent from dataset ledger")
    if (missing != build["required_fields_missing"] or
            empty != build["required_fields_unpopulated"] or
            uncertified != build["uncertified_required_fields"] or
            missing + empty + populated != total_required):
        raise ValueError("Overall field contract build manifest does not reconcile")

    output.sort(key=lambda d:(d["priority"], -len(d["missing_required"]),
                               -len(d["empty_required"]), d["dataset_id"]))
    return {
        "disposition": "BLOCKED_NOT_INSTITUTIONALLY_APPROVED",
        "evidence_level": "LAST_COMPLETED_AUDIT_SNAPSHOT_NOT_LIVE_SOURCE_RESCAN",
        "build_id": build["build_id"],
        "audited_at": str(build["built_at"]),
        "source_git_commit": build["source_git_commit"],
        "dataset_count": len(output),
        "field_rules": len(fields),
        "required_total": total_required,
        "required_populated_but_uncertified": populated,
        "required_missing": missing,
        "required_empty": empty,
        "required_independently_uncertified": uncertified,
        "missing_change_from_previous_build": (
            missing - earlier_missing if earlier_missing is not None else None
        ),
        "institutional_release_approved": False,
        "provider_publication_time_certified_by_this_report": False,
        "datasets": output,
    }


def _dicts(cursor):
    cols = [x[0] for x in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def fetch_snapshot(con, prefix=P):
    builds = _dicts(con.execute(f"""
        SELECT build_id, built_at, source_git_commit, contracts_defined,
               field_rules_defined, required_fields_missing,
               required_fields_unpopulated, uncertified_required_fields,
               institutional_release_approved
        FROM {prefix}lab_institutional_data_contract_builds_v1
        ORDER BY built_at DESC, build_id DESC LIMIT 2
    """))
    if not builds:
        raise ValueError("No source contract build found")
    build = builds[0]
    fields = _dicts(con.execute(f"""
        SELECT build_id,dataset_id,source_table,field_name,requirement_level,
               source_table_exists,expected_type_class,type_class_pass,
               source_table_rows,inventory_status,independently_certified_for_production
        FROM {prefix}lab_institutional_field_audit_v1 WHERE build_id = ?
    """, [build["build_id"]]))
    datasets = _dicts(con.execute(f"""
        SELECT build_id,dataset_id,source_table,table_exists,source_row_count,
               total_fields_required,required_fields_missing,
               required_fields_unpopulated,populated_required_fields,
               source_certification_complete,status
        FROM {prefix}lab_institutional_dataset_audit_v1 WHERE build_id = ?
    """, [build["build_id"]]))
    previous = builds[1]["required_fields_missing"] if len(builds) > 1 else None
    return analyze(build, fields, datasets, previous)


def main():
    import duckdb
    # Only SELECT statements are executed; the single-attach connection cannot
    # be mistaken for independent data-source issuance or a live PIT replay.
    con = duckdb.connect(f"md:{DB}?attach_mode=single")
    try:
        result = fetch_snapshot(con)
    finally:
        con.close()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
