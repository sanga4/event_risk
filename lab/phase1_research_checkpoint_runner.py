#!/usr/bin/env python3
"""Checkpointed, source-pinned *research* QA batch (not a production release).

One on-demand MotherDuck Flight runs five append-only institutional evidence
audits in order. A matching LAB_BATCH_ID can be re-run to skip *verified*
successful stages and continue failed ones. Retries aren't exactly-once
snapshots: upstream source data can change between stages/runs. Do not
interpret internal warehouse-first-known evidence as original provider PIT.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import urlopen
from uuid import uuid4

import duckdb

P = "eventrisk_factor_lab.main."
VERSION = "phase1-research-checkpoint-runner-v1.0.0"
SOURCE_COMMIT = "dd7f4dcff70dba20e35db358fec4233c7282361f"
# Pin git blob hashes to detect unexpected source content at this immutable ref.
# (stage, script, build stdout marker, manifest table, producer commit column,
#  script SHA256 column, institutional approval column, expected Git blob SHA1)
STAGES = (
    ("clock", "phase1_source_clock_gap_audit.py", "BUILD_ID",
     "lab_source_clock_gap_builds_v1", "git_sha", "script_sha256",
     "institutional_release_approved", "c4836328bcb66891862d8113bc7178c6314457c7"),
    ("tail", "phase1_covariance_tail_calibration.py", "BUILD_ID",
     "lab_cov_tail_calibration_builds_v1", "source_git_sha", "code_sha256",
     "institutional_model_release", "cc26e06e63f9964fd0195681fd093ce59be0f324"),
    ("beta", "phase1_ff6_metric_integrity_audit.py", "BUILD_ID",
     "lab_ff6_metric_integrity_builds_v1", "source_git_sha", "script_sha256",
     "institutional_beta_model_released", "576a6a1e5537bda0334df8dd23da0d730f83ba3f"),
    ("gates", "phase1_release_gates.py", "BUILD_ID",
     "lab_release_gate_history_v1", "source_commit", "source_script_sha256",
     None, "31e979756697543f2ac254d56891ec002586f13f"),
    ("register", "phase1_release_unblock_register.py", "BLOCKER_REGISTER_BUILD",
     "lab_release_unblock_register_v1", "source_commit", "source_sha256",
     "institutional_release_approved", "8cd99af036a2c8dbbfbacd0fbf8bc5c8b5cebc76"),
)
EVENT_TABLE = P + "lab_research_checkpoint_events_v1"
VALID_ID = re.compile(r"^[0-9a-f]{32}$")
VALID_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def verify_git_blob(payload: bytes, expected: str) -> None:
    blob = b"blob " + str(len(payload)).encode() + b"\x00" + payload
    if hashlib.sha1(blob).hexdigest() != expected:
        raise ValueError("Pinned Git blob mismatch")
    if len(payload) > 150_000 or not payload:
        raise ValueError("Source size invalid")


def fetch_sources(directory: Path, fetch=None):
    """Retrieve source only at pinned commit; test with an injectable fetcher."""
    def remote(name):
        url = f"https://raw.githubusercontent.com/sanga4/event_risk/{SOURCE_COMMIT}/lab/{name}"
        with urlopen(url, timeout=30) as response:
            blob = response.read(150_001)
        return blob
    fetch = fetch or remote
    digests = {}
    for _stage, name, *_rest, expected_blob in STAGES:
        payload = fetch(name)
        verify_git_blob(payload, expected_blob)
        compile(payload, name, "exec")
        (directory / name).write_bytes(payload)
        digests[name] = hashlib.sha256(payload).hexdigest()
    return digests


def parse_build(stdout: str, marker: str) -> str:
    names = re.findall(r"^" + re.escape(marker) +
                       r"=([a-zA-Z0-9_.:-]{5,200})(?:\s|$)", stdout, flags=re.M)
    if len(names) != 1:
        raise ValueError("Exactly one producer build marker required")
    return names[0]


def create_events(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {EVENT_TABLE} (
      batch_id VARCHAR NOT NULL,attempt_id VARCHAR NOT NULL,
      stage_ordinal INTEGER NOT NULL,stage VARCHAR NOT NULL,
      state VARCHAR NOT NULL,producer_build_id VARCHAR,
      producer_script_sha256 VARCHAR,source_commit VARCHAR NOT NULL,
      runner_commit VARCHAR NOT NULL,runner_sha256 VARCHAR NOT NULL,
      error_class VARCHAR,recorded_at TIMESTAMPTZ NOT NULL,
      institutional_release_approved BOOLEAN NOT NULL)""")


def append_event(con, batch, attempt, ordinal, stage, state, build, script_sha,
                 runner_commit, runner_sha, error=None):
    if state not in ("STARTED","FAILED","SUCCEEDED","SKIPPED_VERIFIED"):
        raise ValueError("Invalid checkpoint state")
    con.execute(f"""INSERT INTO {EVENT_TABLE}
      VALUES (?,?,?,?,?,?,?,?,?,?,?,current_timestamp,FALSE)""",
      [batch,attempt,ordinal,stage,state,build,script_sha,
       SOURCE_COMMIT,runner_commit,runner_sha,error])


def load_checkpoint(con, batch, runner_commit, runner_sha, source_digests):
    """Return completed builds only after metadata/schema/lineage agreement."""
    records = con.execute(f"""SELECT stage_ordinal,stage,state,producer_build_id,
        producer_script_sha256,source_commit,runner_commit,runner_sha256
        FROM {EVENT_TABLE} WHERE batch_id=? ORDER BY recorded_at""",[batch]).fetchall()
    stages = {}
    for ordinal,stage,state,build,sha,source,runner,runner_hash in records:
        if source != SOURCE_COMMIT or runner != runner_commit or runner_hash != runner_sha:
            raise RuntimeError("Batch reused with different runner/source identity")
        if not 1 <= ordinal <= len(STAGES) or STAGES[ordinal-1][0] != stage:
            raise RuntimeError("Checkpoint stage graph mismatch")
        name = STAGES[ordinal-1][1]
        if sha is not None and sha != source_digests[name]:
            raise RuntimeError("Checkpoint source digest mismatch")
        if state == "SUCCEEDED":
            if ordinal in stages and stages[ordinal] != build:
                raise RuntimeError("Conflicting successful stage builds")
            stages[ordinal] = build
    # If later stages have succeeded without earlier recorded stages, reject.
    if stages and set(stages) != set(range(1,max(stages)+1)):
        raise RuntimeError("Incomplete prerequisite checkpoint chain")
    return stages


def verify_output(con, item, build, digest, previous):
    stage, name, _, manifest, commit_column, hash_column, approval, _ = item
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{5,200}", build):
        raise RuntimeError("Untrusted producer build marker")
    # Table/column names are immutable source constants; SQL values parameterized.
    approval_filter = "" if approval is None else f" OR {approval} IS DISTINCT FROM FALSE"
    count,bad = con.execute(f"""SELECT count(*),count(*) FILTER(WHERE
         {commit_column} IS DISTINCT FROM ? OR {hash_column} IS DISTINCT FROM ?
         {approval_filter}) FROM {P}{manifest} WHERE build_id=?""",
         [SOURCE_COMMIT,digest,build]).fetchone()
    if count < 1 or bad != 0:
        raise RuntimeError("Producer build not independently verified")
    if stage=="gates":
        flags = con.execute(f"""SELECT released_to_institutional_production,
            computed_gates,passed_gates,blocked_gates
            FROM {P}lab_release_gate_summary_v1 WHERE build_id=?""",[build]).fetchall()
        if len(flags)!=1 or flags[0][0] is not False or flags[0][1]<40 or flags[0][2]+flags[0][3]!=flags[0][1]:
            raise RuntimeError("Gate assessment structurally invalid or auto-released")
    if stage=="register":
        if 4 not in previous:
            raise RuntimeError("Missing prerequisite gate stage")
        wrong = con.execute(f"""SELECT count(*) FROM {P}lab_release_unblock_register_v1
            WHERE build_id=? AND (gate_build_id IS DISTINCT FROM ?
             OR institutional_release_approved IS DISTINCT FROM FALSE)""",
            [build,previous[4]]).fetchone()[0]
        if wrong:
            raise RuntimeError("Blocker register incorrectly linked or approved")


def run_sequence(batch, runner_commit, runner_sha, directory, source_digests,
                 con_factory, execute=None):
    """Resume only verified finished stages; failed append-only stage reruns.

    The caller must serialize batch invocations; this journal is NOT an atomic
    distributed execution lock. Mutable upstream sources aren't snapshotted.
    """
    attempt=uuid4().hex
    execute = execute or subprocess.run
    env=dict(os.environ,LAB_PIPELINE_COMMIT=SOURCE_COMMIT,LAB_RESEARCH_SCOPE="internal-only")
    with con_factory() as con:
        create_events(con)
        prior=load_checkpoint(con,batch,runner_commit,runner_sha,source_digests)
        completed={}
        for i,item in enumerate(STAGES,1):
            stage,name,marker,*_=item
            digest=source_digests[name]
            if i in prior:
                verify_output(con,item,prior[i],digest,completed)
                append_event(con,batch,attempt,i,stage,"SKIPPED_VERIFIED",prior[i],
                             digest,runner_commit,runner_sha)
                completed[i]=prior[i]
                continue
            append_event(con,batch,attempt,i,stage,"STARTED",None,digest,
                         runner_commit,runner_sha)
            try:
                result=execute([sys.executable,str(directory/name)],cwd=directory,
                    env=env,text=True,capture_output=True,check=True,timeout=180)
                build=parse_build(result.stdout,marker)
                verify_output(con,item,build,digest,completed)
            except Exception as exc:
                # Avoid persisting exception strings, subprocess stdout/stderr,
                # provider URLs, auth headers, tokens or original source bytes.
                append_event(con,batch,attempt,i,stage,"FAILED",None,digest,
                             runner_commit,runner_sha,type(exc).__name__)
                raise
            append_event(con,batch,attempt,i,stage,"SUCCEEDED",build,digest,
                         runner_commit,runner_sha)
            completed[i]=build
            print(f"STAGE={stage} STATE=SUCCEEDED BUILD={build}",flush=True)
        print(f"BATCH={batch} COMPLETED_STAGES={len(completed)}",flush=True)
        print("INSTITUTIONAL_RELEASE=FALSE",flush=True)
    return completed


def main():
    batch=os.getenv("LAB_BATCH_ID","")
    runner=os.getenv("LAB_RUNNER_COMMIT","")
    if (os.getenv("LAB_RESEARCH_SCOPE")!="internal-only" or
        not VALID_ID.fullmatch(batch) or not VALID_COMMIT.fullmatch(runner)):
        raise RuntimeError("Require explicit 32-hex batch ID and pinned runner SHA")
    runner_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def connect():
        con=duckdb.connect("md:eventrisk_factor_lab?attach_mode=single")
        con.execute("SET TimeZone='UTC'")
        return con
    with tempfile.TemporaryDirectory(prefix="eventrisk-research-batch-") as temp:
        directory=Path(temp)
        hashes=fetch_sources(directory)
        run_sequence(batch,runner,runner_sha,directory,hashes,connect)


if __name__=="__main__":
    main()
