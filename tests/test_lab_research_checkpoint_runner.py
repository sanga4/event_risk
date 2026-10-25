"""Checkpointed remote research run offline contract; no warehouse/network access."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_research_checkpoint_runner.py"
spec=importlib.util.spec_from_file_location("checkpoint_research",SRC)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
TEST_SHA="a"*40
TEST_RUNNER_SHA="f"*64
TEST_BATCH="1"*32


class FakeConnection:
    def __init__(self,events):
        self.events=events
        self.args=None

    def __enter__(self):
        return self

    def __exit__(self,*args):
        return False

    def execute(self,sql,args=None):
        self.args=args
        return self

    def fetchall(self):
        return [tuple(r[k] for k in ("ordinal","stage","state","build",
                                    "sha","source","runner","runner_sha"))
                for r in self.events if r["batch"]==self.args[0]]


def fixture_hashes():
    return {stage[1]:"b"*64 for stage in runner.STAGES}


class CheckpointResearchTests(TestCase):
    def test_pinned_stage_sources_are_immutable(self):
        self.assertEqual(len(runner.STAGES),5)
        self.assertEqual(len(set(s[0] for s in runner.STAGES)),5)
        self.assertEqual(len(set(s[1] for s in runner.STAGES)),5)
        for step in runner.STAGES:
            self.assertEqual(len(step[7]),40)
        data=b"print('source')\n"
        expected=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\x00"+data).hexdigest()
        runner.verify_git_blob(data,expected)
        with self.assertRaisesRegex(ValueError,"blob"):
            runner.verify_git_blob(b"print('wrong')",expected)

    def test_exact_build_marker_required(self):
        self.assertEqual(runner.parse_build("a\nBUILD_ID=build.123\n","BUILD_ID"),"build.123")
        for bad in ("", "BUILD_ID=first\nBUILD_ID=second\n", "prefix_BUILD_ID=one\n"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                runner.parse_build(bad,"BUILD_ID")

    def test_resume_only_complete_verified_predecessors(self):
        stage=runner.STAGES[0]
        record=dict(batch=TEST_BATCH,ordinal=1,stage=stage[0],state="SUCCEEDED",
            build="build1",sha="b"*64,source=runner.SOURCE_COMMIT,
            runner=TEST_SHA,runner_sha=TEST_RUNNER_SHA)
        source={s[1]:"b"*64 for s in runner.STAGES}
        self.assertEqual(runner.load_checkpoint(FakeConnection([record]),TEST_BATCH,
                       TEST_SHA,TEST_RUNNER_SHA,source),{1:"build1"})
        bad=dict(record,source="c"*40)
        with self.assertRaisesRegex(RuntimeError,"identity"):
            runner.load_checkpoint(FakeConnection([bad]),TEST_BATCH,
                  TEST_SHA,TEST_RUNNER_SHA,source)
        bad=dict(record,sha="e"*64)
        with self.assertRaisesRegex(RuntimeError,"digest"):
            runner.load_checkpoint(FakeConnection([bad]),TEST_BATCH,
                  TEST_SHA,TEST_RUNNER_SHA,source)
        bad=dict(record,ordinal=2,stage=runner.STAGES[1][0])
        with self.assertRaisesRegex(RuntimeError,"prerequisite"):
            runner.load_checkpoint(FakeConnection([bad]),TEST_BATCH,
                  TEST_SHA,TEST_RUNNER_SHA,source)

    def test_failed_partial_batch_replays_only_uncompleted_stages(self):
        # Fake journal and verified-output manifest; no external connection.
        journal=[]
        completed={}
        executions=[]
        fail_once={"active":True}
        hashes=fixture_hashes()

        def emit(con,batch,attempt,ordinal,name,state,build,digest,commit,sha,error=None):
            journal.append(dict(batch=batch,ordinal=ordinal,stage=name,state=state,
                build=build,sha=digest,source=runner.SOURCE_COMMIT,
                runner=commit,runner_sha=sha))

        def verify(con,item,build,digest,previous):
            self.assertEqual(build,"good-"+item[0])
            self.assertEqual(digest,"b"*64)
            completed[item[0]]=build

        def fake_execute(args,**kwargs):
            name=Path(args[1]).name
            stage=next(s for s in runner.STAGES if s[1]==name)
            executions.append(stage[0])
            if stage[0]=="beta" and fail_once["active"]:
                fail_once["active"]=False
                raise subprocess.CalledProcessError(1,args)
            return SimpleNamespace(stdout=stage[2]+"=good-"+stage[0]+"\n")

        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for s in runner.STAGES:
                (folder/s[1]).write_text("pass\n")
            with (patch.object(runner,"create_events",return_value=None),
                  patch.object(runner,"append_event",side_effect=emit),
                  patch.object(runner,"verify_output",side_effect=verify)):
                def connect():
                    return FakeConnection(journal)
                with self.assertRaises(subprocess.CalledProcessError):
                    runner.run_sequence(TEST_BATCH,TEST_SHA,TEST_RUNNER_SHA,folder,
                                        hashes,connect,execute=fake_execute)
                self.assertEqual(executions,["clock","tail","beta"])
                runner.run_sequence(TEST_BATCH,TEST_SHA,TEST_RUNNER_SHA,folder,
                                    hashes,connect,execute=fake_execute)
        self.assertEqual(executions,["clock","tail","beta","beta","gates","register"])
        self.assertEqual(set(completed),{"clock","tail","beta","gates","register"})
        self.assertEqual(sum(x["state"]=="SKIPPED_VERIFIED" for x in journal),2)
        self.assertTrue(all(x.get("state")!="SUCCEEDED" or x["build"] for x in journal))

    def test_batch_identity_and_stage_graph_fail_closed(self):
        self.assertTrue(runner.VALID_ID.fullmatch(TEST_BATCH))
        self.assertFalse(runner.VALID_ID.fullmatch("not-a-uuid"))
        self.assertTrue(runner.VALID_COMMIT.fullmatch(TEST_SHA))
        self.assertFalse(runner.VALID_COMMIT.fullmatch("HEAD"))
        stage=runner.STAGES[0]
        record=dict(batch=TEST_BATCH,ordinal=1,stage="wrong",state="SUCCEEDED",
           build="good",sha="b"*64,source=runner.SOURCE_COMMIT,
           runner=TEST_SHA,runner_sha=TEST_RUNNER_SHA)
        with self.assertRaisesRegex(RuntimeError,"graph"):
            runner.load_checkpoint(FakeConnection([record]),TEST_BATCH,
                                   TEST_SHA,TEST_RUNNER_SHA,fixture_hashes())


if __name__=="__main__":
    import unittest
    unittest.main()
