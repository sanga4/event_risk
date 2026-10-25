#!/usr/bin/env python3
"""One-shot, source-pinned QA batch for MotherDuck Flights; never a release.

Journal events are execution evidence, not resumable source snapshots. A killed
process leaves STARTED without a terminal event; never infer success from that.
"""
from __future__ import annotations
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

SOURCE_COMMIT = 'c1f17147c0fe6042721c9caafbf91c3f507d458e'
P = 'eventrisk_factor_lab.main.'
# (script, build marker, manifest table, commit column, hash column)
STAGES = (
    ('phase1_price_exception_audit.py', 'BUILD_ID', 'lab_security_price_exception_builds_v1', 'git_sha', 'source_script_sha256'),
    ('phase1_adjusted_price_reconciliation.py', 'BUILD_ID', 'lab_security_adjustment_audit_builds_v1', 'git_sha', 'script_sha256'),
    ('phase1_independent_evidence_requirements.py', 'BUILD_ID', 'lab_independent_evidence_builds_v1', 'git_sha', 'source_code_sha256'),
    ('phase1_release_gates.py', 'BUILD_ID', 'lab_release_gate_history_v1', 'source_commit', 'source_script_sha256'),
    ('phase1_release_unblock_register.py', 'BLOCKER_REGISTER_BUILD', 'lab_release_unblock_register_v1', 'source_commit', 'source_sha256'),
)
SOURCE_HASHES = {'phase1_price_exception_audit.py': 'a625b1df6da1361bd59a85a2831a005be0123b0d47f6c20b172708baf40240da', 'phase1_adjusted_price_reconciliation.py': 'c9c4d8a2ef2f2f6b9ac6b48705fc9010a620470192e97efa1428b3b5b4ca1f5d', 'phase1_independent_evidence_requirements.py': 'c12ca757bf1d9297e0c731225746a508c19d9dc2caff3bd0e9bf3b8e53e93b1f', 'phase1_release_gates.py': '91b00c04d67f7e061c56fec8703bc6566479fda5594f053defa3b38a69577c2b', 'phase1_release_unblock_register.py': 'f02f12e822ca87120e108aa2c1fce0eb799d46311ddd774377b9937c3e6f7c59', 'phase1_security_rate_beta_backfill.py': 'bf070deafa89aa3f01cb39cd239ff73030d06461b77937644d0c8272930ba541'}


def fetch_sources(directory, fetch=None):
    """Verify every source before executing any child; URLs are not user input."""
    def download(name):
        url = f'https://raw.githubusercontent.com/sanga4/event_risk/{SOURCE_COMMIT}/lab/{name}'
        with urlopen(url, timeout=30) as response:
            payload = response.read(200_001)
        if len(payload) > 200_000:
            raise ValueError('Source exceeds size bound')
        return payload
    fetch = fetch or download
    for name, expected in SOURCE_HASHES.items():
        payload = fetch(name)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f'Source checksum mismatch: {name}')
        compile(payload, name, 'exec')
        (directory / name).write_bytes(payload)


def parse_build(output, marker):
    matches = re.findall(r'^' + re.escape(marker) + r'=([A-Za-z0-9_.:-]+)(?:\s|$)', output, re.M)
    if len(matches) != 1:
        raise ValueError('Expected exactly one producer build identifier')
    return matches[0]


def execute_stages(directory, emit, verify, run=subprocess.run):
    env = dict(os.environ, LAB_PIPELINE_COMMIT=SOURCE_COMMIT, LAB_RESEARCH_SCOPE='internal-only')
    completed = {}
    for ordinal, stage in enumerate(STAGES, 1):
        name, marker, *_ = stage
        emit(ordinal, name, 'STARTED', None, None)
        try:
            result = run([sys.executable, str(directory / name)], cwd=directory,
                         env=env, capture_output=True, text=True, timeout=150, check=True)
            build = parse_build(result.stdout, marker)
            verify(stage, build, completed)
        except Exception as exc:
            # Do not persist arbitrary stderr: it can contain credentials or URLs.
            emit(ordinal, name, 'FAILED', None, type(exc).__name__)
            raise
        emit(ordinal, name, 'SUCCEEDED', build, None)
        completed[name] = build
    return completed


def verify_build(con, stage, build, completed):
    name, _, table, commit_column, hash_column = stage
    # Identifiers are constants from STAGES; values remain parameterized.
    row = con.execute(f'''SELECT count(*),count(*) FILTER(
        WHERE {commit_column} IS DISTINCT FROM ? OR {hash_column} IS DISTINCT FROM ?)
        FROM {P}{table} WHERE build_id=?''',
        [SOURCE_COMMIT, SOURCE_HASHES[name], build]).fetchone()
    if row[0] == 0 or row[1] != 0:
        raise ValueError('Producer output missing or source lineage mismatch')
    if name == 'phase1_release_gates.py':
        flags = con.execute(f'SELECT released_to_institutional_production FROM {P}lab_release_gate_summary_v1 WHERE build_id=?', [build]).fetchall()
        if flags != [(False,)]:
            raise ValueError('Research batch cannot approve institutional release')
    if name == 'phase1_release_unblock_register.py':
        expected = completed['phase1_release_gates.py']
        wrong = con.execute(f'''SELECT count(*) FROM {P}lab_release_unblock_register_v1
            WHERE build_id=? AND (gate_build_id IS DISTINCT FROM ? OR institutional_release_approved IS DISTINCT FROM FALSE)''', [build, expected]).fetchone()[0]
        if wrong:
            raise ValueError('Blocker register consumed another gate build or approved release')


def main():
    runner_commit = os.getenv('LAB_PIPELINE_COMMIT', '')
    if not re.fullmatch('[0-9a-f]{40}', runner_commit) or os.getenv('LAB_RESEARCH_SCOPE') != 'internal-only':
        raise RuntimeError('Pinned runner SHA and internal-only scope required')
    batch = 'source-qa-' + str(uuid4())
    runner_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def connect():
        con = duckdb.connect('md:eventrisk_factor_lab?attach_mode=single')
        con.execute("SET TimeZone='UTC'")
        return con
    with connect() as con:
        con.execute(f'''CREATE TABLE IF NOT EXISTS {P}lab_source_qa_batch_events_v1(
            batch_id VARCHAR NOT NULL, ordinal INTEGER NOT NULL, stage VARCHAR NOT NULL,
            state VARCHAR NOT NULL, producer_build_id VARCHAR, error_class VARCHAR,
            source_commit VARCHAR NOT NULL, runner_commit VARCHAR NOT NULL,
            runner_sha256 VARCHAR NOT NULL, recorded_at TIMESTAMPTZ NOT NULL,
            institutional_release_approved BOOLEAN NOT NULL)''')
    def emit(ordinal, name, state, build, error):
        with connect() as con:
            con.execute(f'''INSERT INTO {P}lab_source_qa_batch_events_v1
                VALUES (?,?,?,?,?,?,?,?,?,current_timestamp,FALSE)''',
                [batch, ordinal, name, state, build, error, SOURCE_COMMIT, runner_commit, runner_hash])
        print(f'BATCH={batch} STAGE={name} STATE={state} BUILD={build}', flush=True)
    def verify(stage, build, completed):
        with connect() as con:
            verify_build(con, stage, build, completed)
    emit(0, 'batch', 'STARTED', None, None)
    try:
        with tempfile.TemporaryDirectory(prefix='eventrisk-qa-') as work:
            directory = Path(work)
            fetch_sources(directory)
            execute_stages(directory, emit, verify)
    except Exception as exc:
        emit(0, 'batch', 'FAILED', None, type(exc).__name__)
        raise
    emit(0, 'batch', 'SUCCEEDED', None, None)
    print('INSTITUTIONAL_RELEASE=FALSE', flush=True)

if __name__ == '__main__':
    main()
