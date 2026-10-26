"""Offline independent anti-forgery replay of 96 original model Holm family.

Fixtures use synthetic security returns; no real source PIT or permissions are
approved. The production source acceptance module never calls producer.score().
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

LAB=Path(__file__).resolve().parents[1]/"lab"
sys.path.insert(0,str(LAB))
sys.path.insert(0,str(LAB.parent/"tests"))
from test_lab_joint_funding_familywise_audit import fixture
import phase1_joint_funding_familywise_audit as producer

spec=importlib.util.spec_from_file_location(
    "phase1_joint_funding_familywise_acceptance",
    LAB/"phase1_joint_funding_familywise_acceptance.py")
verify=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=verify
spec.loader.exec_module(verify)

GIT="a"*40
CODE_SHA=hashlib.sha256(
    (LAB/"phase1_joint_funding_familywise_audit.py").read_bytes()).hexdigest()
BUILD="synthetic-holm-audit"
PARENT="synthetic-original-48security-models"

def setup():
    original=sorted(fixture(),key=lambda x:(x[0],x[1]))
    scores=producer.score(original)
    models=[(BUILD,*row,False) for row in scores["rows"]]
    manifest=(
        BUILD,GIT,CODE_SHA,hashlib.sha256(repr(original).encode()).hexdigest(),
        PARENT,datetime(2026,10,26,tzinfo=timezone.utc),
        96,48,scores["nominal_hac_p_below_05"],
        scores["holm_p_below_05"],scores["original_research_screen_pass"],
        scores["joint_screen_pass"],scores["sign_flip_assets"],
        scores["relative_shift_gt25_assets"],
        scores["positive_oos_both_variants"],scores["min_nominal_p"],
        scores["min_holm_adjusted_p"],False,False,False,False,
        verify.DISPOSITION
    )
    parent=(PARENT,"b"*40,"c"*64,"d"*64,96,48,0)
    return manifest,parent,original,models

def do_accept(parts):
    return verify.verify(*parts,GIT,CODE_SHA)

class IndependentHolmReceiptFalsificationTests(unittest.TestCase):
    def test_reconstructs_synthetic_96_global_holm_family_without_producer_calls(self):
        result=do_accept(setup())
        self.assertEqual(result["status"],
                         "INDEPENDENT_HOLM_96_SOURCE_REPLAY_ACCEPTED_RESEARCH_ONLY")
        self.assertEqual(result["models"],96)
        self.assertEqual(result["assets"],48)
        self.assertEqual(result["holm_p_below_05"],2)
        self.assertEqual(result["jointly_research_screen_pass"],2)
        self.assertEqual(result["cross_training_pair_joint_survivors"],["ASSET00"])
        self.assertFalse(result["institutional_beta_release"])

    def test_wrong_manifest_commit_source_digest_or_parent_fails(self):
        for field,new in ((1,"0"*40),(2,"f"*64),(3,"0"*64),(4,"not-parent")):
            x=list(setup())
            b=list(x[0]);b[field]=new;x[0]=tuple(b)
            with self.subTest(field=field),self.assertRaises(ValueError):
                do_accept(tuple(x))

    def test_parent_issuer_rights_or_original_method_identity_fails(self):
        x=list(setup())
        parent=list(x[1]);parent[6]=1;x[1]=tuple(parent)
        with self.assertRaisesRegex(ValueError,"source model"):
            do_accept(tuple(x))
        x=list(setup());parent=list(x[1]);parent[2]="bad-sha";x[1]=tuple(parent)
        with self.assertRaises(ValueError):
            do_accept(tuple(x))

    def test_missing_or_duplicated_original_or_audit_rows_rejected(self):
        for pos in (2,3):
            x=list(setup());x[pos]=list(x[pos][:-1])
            with self.subTest(pos=pos),self.assertRaisesRegex(ValueError,"96-model"):
                do_accept(tuple(x))
        x=list(setup());cells=list(x[3]);cells[-1]=cells[0];x[3]=cells
        with self.assertRaisesRegex(ValueError,"duplicate"):
            do_accept(tuple(x))

    def test_forged_adjusted_holm_p_rank_or_nominal_p_is_rejected(self):
        for col,new in ((3,97),(6,.99),(7,.99)):
            x=list(setup());cells=list(x[3]);v=list(cells[0]);v[col]=new
            cells[0]=tuple(v);x[3]=cells
            with self.subTest(col=col),self.assertRaises(ValueError):
                do_accept(tuple(x))

    def test_forged_funding_beta_and_hac_standard_error_rejected(self):
        for col,new in ((4,999.),(5,.001)):
            x=list(setup());cells=list(x[3]);v=list(cells[0]);v[col]=new
            cells[0]=tuple(v);x[3]=cells
            with self.subTest(col=col),self.assertRaises(ValueError):
                do_accept(tuple(x))

    def test_false_cross_variant_stability_rejection_state_is_rejected(self):
        x=list(setup());cells=list(x[3]);v=list(cells[0])
        v[16]="REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING"
        cells[0]=tuple(v);x[3]=cells
        with self.assertRaisesRegex(ValueError,"rank/variant"):
            do_accept(tuple(x))

    def test_false_source_approval_or_institutional_beta_is_rejected(self):
        x=list(setup());cells=list(x[3]);v=list(cells[0]);v[17]=True
        cells[0]=tuple(v);x[3]=cells
        with self.assertRaisesRegex(ValueError,"unapproved"):
            do_accept(tuple(x))
        x=list(setup());m=list(x[0]);m[20]=True;x[0]=tuple(m)
        with self.assertRaisesRegex(ValueError,"rights"):
            do_accept(tuple(x))

    def test_forced_false_manifest_survivor_counts_rejected(self):
        x=list(setup());manifest=list(x[0]);manifest[11]=3;x[0]=tuple(manifest)
        with self.assertRaisesRegex(ValueError,"manifest counter"):
            do_accept(tuple(x))

    def test_current_auditor_source_is_readonly_and_forbids_approval(self):
        text=(LAB/"phase1_joint_funding_familywise_acceptance.py").read_text()
        self.assertIn("math.erfc",text)
        self.assertIn("SET TimeZone='UTC'",text)
        self.assertIn("INDEPENDENT_HOLM_96_SOURCE_REPLAY_ACCEPTED_RESEARCH_ONLY",text)
        self.assertNotIn("producer.score(",text)
        self.assertNotIn("INSERT INTO",text)
        self.assertNotIn("UPDATE main.",text)

if __name__=="__main__":
    unittest.main()
