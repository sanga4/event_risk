"""Failure isolation, source integrity and durable producer checks."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
import duckdb

LAB = Path(__file__).resolve().parents[1] / 'lab'
spec = importlib.util.spec_from_file_location('qa_remote', LAB / 'phase1_source_qa_remote.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

class BatchTests(unittest.TestCase):
    def test_pinned_hashes_match_repo_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            qa.fetch_sources(Path(tmp), lambda name: (LAB / name).read_bytes())
            self.assertEqual(len(list(Path(tmp).iterdir())), 6)

    def test_changed_source_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                qa.fetch_sources(Path(tmp), lambda _: b'print("altered")')

    def test_no_ambiguous_build_marker(self):
        for output in ['', 'BUILD_ID=a\nBUILD_ID=b\n', 'BUILD_ID=../../bad\n']:
            with self.subTest(output=output), self.assertRaises(ValueError):
                qa.parse_build(output, 'BUILD_ID')
        self.assertEqual(qa.parse_build('BUILD_ID=abc-123 ROWS=10\n', 'BUILD_ID'), 'abc-123')

    def test_sequential_execution_and_pinned_environment(self):
        events, calls, checks = [], [], []
        def run(command, **kwargs):
            index = len(calls)
            calls.append(command)
            self.assertEqual(kwargs['env']['LAB_PIPELINE_COMMIT'], qa.SOURCE_COMMIT)
            self.assertEqual(kwargs['timeout'], 150)
            return SimpleNamespace(stdout=f'{qa.STAGES[index][1]}=build-{index}\n')
        def verify(stage, build, completed):
            checks.append(build)
            self.assertEqual(len(completed), len(checks)-1)
        result = qa.execute_stages(Path('/unused'), lambda *args: events.append(args), verify, run)
        self.assertEqual(len(result), 5)
        self.assertEqual([e[2] for e in events], ['STARTED','SUCCEEDED']*5)

    def test_failure_stops_downstream_stages_and_redacts_exception(self):
        for failure in [subprocess.TimeoutExpired('cmd',150), RuntimeError('secret-content')]:
            events = []
            def run(*args, **kwargs):
                raise failure
            with self.assertRaises(type(failure)):
                qa.execute_stages(Path('/unused'), lambda *args: events.append(args), lambda *args: None, run)
            self.assertEqual([e[2] for e in events], ['STARTED','FAILED'])
            self.assertNotIn('secret-content', repr(events))

    def test_unverified_output_cannot_mark_success(self):
        events=[]
        def verify(*args):
            raise ValueError('missing manifest')
        with self.assertRaises(ValueError):
            qa.execute_stages(Path('/unused'), lambda *args: events.append(args), verify,
                lambda *args, **kwargs: SimpleNamespace(stdout='BUILD_ID=forged\n'))
        self.assertEqual(events[-1][2], 'FAILED')

    def test_manifest_requires_exact_commit_and_hash(self):
        old=qa.P;qa.P='main.'
        con=duckdb.connect(':memory:')
        try:
            stage=qa.STAGES[0]
            con.execute(f'CREATE TABLE {stage[2]}(build_id VARCHAR,git_sha VARCHAR,source_script_sha256 VARCHAR)')
            with self.assertRaises(ValueError): qa.verify_build(con,stage,'b',{})
            con.execute(f'INSERT INTO {stage[2]} VALUES (?,?,?)',['b',qa.SOURCE_COMMIT,qa.SOURCE_HASHES[stage[0]]])
            qa.verify_build(con,stage,'b',{})
            con.execute(f"UPDATE {stage[2]} SET git_sha='wrong'")
            with self.assertRaises(ValueError): qa.verify_build(con,stage,'b',{})
        finally:
            qa.P=old;con.close()

if __name__ == '__main__': unittest.main()
