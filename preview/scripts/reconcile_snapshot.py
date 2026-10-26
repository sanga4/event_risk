#!/usr/bin/env python3
"""Read-only optional reconciliation of preview aggregate metrics with MotherDuck.

Run manually with a separately scoped research READ token. Never runs on
public preview server, in CI, or on Railway. Never writes to MotherDuck or
updates the reviewed frozen JSON snapshot. No provider rights/PIT approval.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import read_snapshot

DB="eventrisk_factor_lab"
P=DB+".main."
QUERIES={
 "venue_receipts": f"SELECT count(*) FROM {P}lab_live_market_captures_v1",
 "asof_grid": f"SELECT count(*) FROM {P}lab_prospective_event_factor_grid_v1",
 "panel_v2": f"SELECT count(*) FROM {P}lab_event_factor_panel_v2",
 "panel_v4": f"SELECT count(*) FROM {P}lab_event_factor_panel_v4",
 "paired_losses": f"SELECT count(*) FROM {P}lab_joint_funding_daily_paired_losses_v1",
 "security_models": f"SELECT count(*) FROM {P}lab_joint_funding_familywise_models_v1",
 "bea_values": f"SELECT count(*) FROM {P}lab_bea_original_reported_values_v1",
}

def inspect(con, snapshot):
    expected={m["key"]:m["value"] for m in snapshot["metrics"]}
    observed={}
    for key,sql in QUERIES.items():
        observed[key]=int(con.execute(sql).fetchone()[0])
    gate=con.execute(f"""SELECT build_id,computed_gates,passed_gates,blocked_gates,
                external_manual_gates,released_to_institutional_production
                FROM {P}lab_release_gate_summary_v1
                ORDER BY asof_utc DESC LIMIT 1""").fetchone()
    if not gate or gate[-1] is not False:
        raise ValueError("Institutional release missing or unexpectedly approved: fail closed")
    field=con.execute(f"""SELECT required_fields_missing,uncertified_required_fields
                FROM {P}lab_institutional_data_contract_builds_v1
                ORDER BY built_at DESC LIMIT 1""").fetchone()
    if not field:
        raise ValueError("Source field contract build missing")
    output={
        "scope":"SELECT_ONLY_RECONCILIATION_NOT_SOURCE_APPROVAL",
        "frozen_snapshot_id":snapshot["snapshot_id"],
        "frozen_as_of_utc":snapshot["as_of_utc"],
        "counts":{k:{"snapshot":expected[k],"warehouse_now":observed[k],
                      "drift":observed[k]-expected[k]} for k in QUERIES},
        "latest_gate":{"build_id":gate[0],"automatic_total":gate[1],
                       "automatic_passed":gate[2],"automatic_blocked":gate[3],
                       "manual_blocked":gate[4],"institutional_approval":False},
        "required_missing_fields":int(field[0]),
        "uncertified_required_fields":int(field[1]),
        "snapshot_gates_still_current":gate[0]==snapshot["release"]["gate_build_id"],
        "preview_data_refreshed":False,
        "institutional_release_approved":False
    }
    return output

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--fail-on-drift",action="store_true",
      help="Exit nonzero if source counts differ from reviewed snapshot; drift may be genuine new research")
    args=cli.parse_args()
    if not os.getenv("MOTHERDUCK_TOKEN"):
        cli.error("READ-ONLY MotherDuck credential required via environment; do not place token in arguments")
    import duckdb
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as conn:
        conn.execute("SET TimeZone='UTC'")
        report=inspect(conn,read_snapshot())
    print(json.dumps(report,indent=2,sort_keys=True))
    if args.fail_on_drift and (
        not report["snapshot_gates_still_current"] or
        any(m["drift"] for m in report["counts"].values())):
        raise SystemExit(2)

if __name__=="__main__":
    main()
