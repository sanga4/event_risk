#!/usr/bin/env python3
"""Verify manual, source-pinned MotherDuck producer records after GitHub Actions.

Never runs a producer itself. A completed process and its append-only manifest
must both be checked before calling a run materialized. This is a *research*
execution attestation, not an original publisher PIT or rights approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

DB = "eventrisk_factor_lab"
P = DB + ".main."
SHA = re.compile(r"^[0-9a-f]{40}$")
MODES = frozenset(("incremental_grid_only", "field_contracts_only",
                   "incremental_grid_and_field_contracts"))


def local_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_grid(row: tuple, commit: str, code_hash: str) -> dict:
    # full_git_sha, script_sha256, build_id, new factor vintages, new grid rows,
    # future warehouse, independently provider-time verified rows, status
    if row is None or len(row) != 8:
        raise ValueError("Missing or incompatible warehouse grid run manifest")
    sha, digest, build, factors, added, future, certified, status = row
    if (sha != commit or digest != code_hash or not build
        or any(type(n) is not int or n < 0 for n in
               (factors, added, future, certified))
        or future or certified or status != "MATERIALIZED_RESEARCH_ONLY"):
        raise ValueError("Warehouse grid manifest incompatible or approved")
    return {
        "producer": "incremental_warehouse_grid",
        "build_id": build,
        "new_factor_vintages": factors,
        "new_grid_rows": added,
        "future_warehouse_factor_rows": future,
        "provider_pit_verified_rows": 0,
        "institutional_release_approved": False,
        "status": "RESEARCH_PRODUCER_MANIFEST_VERIFIED",
    }


def verify_fields(row: tuple, commit: str, code_hash: str) -> dict:
    # source_git_commit, source_script_sha256, build_id, contract domains,
    # field rules, missing, empty, uncertified, institutionally approved, state
    if row is None or len(row) != 10:
        raise ValueError("Missing or incompatible institutional field run manifest")
    sha, digest, build, domains, rules, missing, empty, uncertified, approved, state = row
    if (sha != commit or digest != code_hash or not build
        or domains != 16 or rules != 274
        or any(type(n) is not int or n < 0 for n in
               (missing, empty, uncertified))
        or missing + empty > 255 or uncertified != 255
        or approved is not False
        or state != "RELEASE_BLOCKED_SOURCE_CERTIFICATIONS_INCOMPLETE"):
        raise ValueError("Institutional field manifest incompatible or falsely released")
    return {
        "producer": "institutional_field_audit",
        "build_id": build,
        "source_domains": domains,
        "field_rules": rules,
        "required_fields_missing": missing,
        "required_fields_empty": empty,
        "required_fields_uncertified": uncertified,
        "institutional_release_approved": False,
        "status": "RESEARCH_PRODUCER_MANIFEST_VERIFIED",
    }


def latest(con, sql: str):
    return con.execute(sql).fetchone()


def verify(con, *, commit: str, mode: str, lab: Path) -> dict:
    if not SHA.fullmatch(commit) or mode not in MODES:
        raise ValueError("Unknown source version or mutating execution mode")
    output = {"mode": mode, "source_commit": commit,
              "institutional_release_approved": False,
              "publisher_first_publication_verified": False, "producers": []}
    if mode in ("incremental_grid_only", "incremental_grid_and_field_contracts"):
        grid = latest(con, f"""
          SELECT full_git_sha, script_sha256, build_id,
                 new_factor_vintage_rows, new_coobservation_rows,
                 future_warehouse_factor_rows, externally_certified_pit_rows,
                 status
          FROM {P}lab_prospective_grid_runs_v1
          ORDER BY started_at DESC, build_id DESC LIMIT 1
        """)
        output["producers"].append(verify_grid(
            grid, commit, local_sha(lab / "phase1_warehouse_asof_grid.py")
        ))
    if mode in ("field_contracts_only", "incremental_grid_and_field_contracts"):
        fields = latest(con, f"""
          SELECT source_git_commit,source_script_sha256,build_id,
                 contracts_defined,field_rules_defined,required_fields_missing,
                 required_fields_unpopulated,uncertified_required_fields,
                 institutional_release_approved,release_state
          FROM {P}lab_institutional_data_contract_builds_v1
          ORDER BY built_at DESC, build_id DESC LIMIT 1
        """)
        output["producers"].append(verify_fields(
            fields, commit, local_sha(lab / "phase1_field_coverage.py")
        ))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    args = parser.parse_args()
    import duckdb
    with duckdb.connect(f"md:{DB}?attach_mode=single") as con:
        con.execute("SET TimeZone='UTC'")
        report = verify(con, commit=args.source_commit, mode=args.mode,
                        lab=Path(__file__).resolve().parent)
    print(json.dumps(report, indent=2, sort_keys=True))
    print("INSTITUTIONAL_RELEASE=FALSE PROVIDER_PIT_CERTIFICATION=FALSE")


if __name__ == "__main__":
    sys.exit(main())
