"""Independent 96-cell HAC multiplicity correction and original price tail tests."""
from datetime import date, timedelta
from pathlib import Path
import importlib.util
import unittest
import math

SRC=Path(__file__).resolve().parents[1]/"lab"/"phase1_joint_funding_familywise_audit.py"
spec=importlib.util.spec_from_file_location("joint_familywise",SRC)
q=importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
FIRST=date(2024,1,1)

def fixture():
    rows=[]
    for i in range(48):
        ticker=f"ASSET{i:02d}"
        for variant in ("full_training","training_tail_exclusion"):
            beta=5.0 if i==0 else 1.0
            fitted=489 if variant=="full_training" else 475
            rows.append((ticker,variant,699,489,210,fitted,FIRST,
                FIRST+timedelta(days=690),FIRST+timedelta(days=691),
                FIRST+timedelta(days=1050),beta,1.0,0.004,True,
                "RESEARCH_SCREEN_PASS_NOT_INSTITUTIONAL" if i==0 else
                "REJECT_HAC_INTERVAL_INCLUDES_ZERO",0))
    return rows

class JointBetaMultiplicity(unittest.TestCase):
    def test_holm_stepdown_covers_full_96_including_rejected_fits(self):
        report=q.score(fixture())
        self.assertEqual(report["models"],96)
        self.assertEqual(report["nominal_hac_p_below_05"],2)
        self.assertEqual(report["holm_p_below_05"],2)
        self.assertEqual(report["joint_screen_pass"],2)
        self.assertEqual(report["original_research_screen_pass"],2)
        self.assertEqual(report["sign_flip_assets"],0)
        self.assertEqual(report["relative_shift_gt25_assets"],0)
        self.assertEqual(report["positive_oos_both_variants"],48)
        ordered=sorted(report["rows"],key=lambda r:r[2])
        self.assertEqual([r[2] for r in ordered],list(range(1,97)))
        self.assertTrue(all(ordered[i][6]<=ordered[i+1][6] for i in range(95)))
        self.assertAlmostEqual(report["min_nominal_p"],math.erfc(5.0/math.sqrt(2)))

    def test_nominal_significant_not_sufficient_for_96_family(self):
        rows=fixture()
        # two-sided z=2.80 nominal p≈0.0051, above 0.05/96≈0.00052
        rows=[(*r[:10],2.8,r[11],*r[12:]) if r[0]=="ASSET00" else r for r in rows]
        report=q.score(rows)
        self.assertEqual(report["nominal_hac_p_below_05"],2)
        self.assertEqual(report["holm_p_below_05"],0)
        self.assertEqual(report["original_research_screen_pass"],2)
        self.assertEqual(report["joint_screen_pass"],0)
        self.assertTrue(all(r[-1]=="REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING"
                            for r in report["rows"] if r[0]=="ASSET00"))

    def test_tail_sign_reversal_and_large_relative_beta_shift(self):
        rows=fixture()
        new=[]
        for r in rows:
            if r[0]=="ASSET01" and r[1]=="training_tail_exclusion":
                x=list(r);x[10]=-1.0;r=tuple(x)
            if r[0]=="ASSET02" and r[1]=="training_tail_exclusion":
                x=list(r);x[10]=0.6;r=tuple(x)
            new.append(r)
        report=q.score(new)
        self.assertEqual(report["sign_flip_assets"],1)
        self.assertEqual(report["relative_shift_gt25_assets"],2)
        self.assertTrue(all(r[12] for r in report["rows"] if r[0]=="ASSET01"))

    def test_strong_holm_significance_never_overrides_variant_sign_reversal(self):
        rows=fixture()
        # Both source cells remain highly significant under the original
        # nominal/Holm family, but the *security* is not beta-stable.
        altered=[]
        for r in rows:
            if r[0]=="ASSET00" and r[1]=="training_tail_exclusion":
                x=list(r);x[10]=-5.0;r=tuple(x)
            altered.append(r)
        report=q.score(altered)
        self.assertEqual(report["holm_p_below_05"],2)
        self.assertEqual(report["joint_screen_pass"],0)
        self.assertEqual(report["cross_variant_rejected_assets"],1)
        self.assertEqual(report["cross_variant_rejected_model_cells"],2)
        self.assertEqual(
            {r[-1] for r in report["rows"] if r[0]=="ASSET00"},
            {"REJECT_CROSS_VARIANT_FUNDING_BETA_SIGN_REVERSAL"})

    def test_25pct_variant_coefficient_instability_is_binding(self):
        rows=fixture()
        modified=[]
        for r in rows:
            if r[0]=="ASSET00" and r[1]=="training_tail_exclusion":
                x=list(r);x[10]=3.5;r=tuple(x)  # 30% relative shift
            modified.append(r)
        report=q.score(modified)
        self.assertEqual(report["joint_screen_pass"],0)
        self.assertEqual(report["cross_variant_rejected_assets"],1)
        self.assertEqual(
            {r[-1] for r in report["rows"] if r[0]=="ASSET00"},
            {"REJECT_CROSS_VARIANT_FUNDING_BETA_SHIFT_GT25PCT"})

    def test_one_bad_holdout_variant_rejects_otherwise_significant_pair(self):
        rows=fixture()
        modified=[]
        for r in rows:
            if r[0]=="ASSET00" and r[1]=="training_tail_exclusion":
                x=list(r);x[12]=-0.01
                x[14]="REJECT_NEGATIVE_HOLDOUT_SKILL"
                r=tuple(x)
            modified.append(r)
        report=q.score(modified)
        self.assertEqual(report["joint_screen_pass"],0)
        self.assertEqual(
            {r[-1] for r in report["rows"] if r[0]=="ASSET00"},
            {"REJECT_CROSS_VARIANT_HOLDOUT_SKILL"})

    def test_false_parent_screen_claim_is_rejected_not_inherited(self):
        for idx,value in ((12,0.0),(13,False),(10,0.5)):
            rows=fixture()
            x=list(rows[0]);x[idx]=value;rows[0]=tuple(x)
            with self.subTest(index=idx),self.assertRaisesRegex(
                ValueError,"Parent research screen contradicts fitted diagnostics"):
                q.score(rows)

    def test_failed_base_research_screen_never_upgraded_by_small_p(self):
        rows=fixture()
        x=list(rows[0]);x[14]="REJECT_NEGATIVE_HOLDOUT_SKILL";rows[0]=tuple(x)
        out=q.score(rows)
        match=next(r for r in out["rows"] if r[0]=="ASSET00"
                   and r[1]=="full_training")
        self.assertTrue(match[8])
        self.assertEqual(match[-1],"REJECT_EXISTING_HOLDOUT_OR_STABILITY_SCREEN")
        self.assertEqual(out["joint_screen_pass"],1)

    def test_missing_pair_duplicate_date_or_false_approval_block(self):
        with self.assertRaisesRegex(ValueError,"Missing original"):
            q.score(fixture()[:-1])
        items=fixture();items[1]=items[0]
        with self.assertRaisesRegex(ValueError,"Invalid key"):
            q.score(items)
        for index,value in ((3,300),(5,500),(7,FIRST),
                            (11,0),(11,float("nan")),(15,1)):
            items=fixture();x=list(items[0]);x[index]=value;items[0]=tuple(x)
            with self.subTest(index=index),self.assertRaises(ValueError):
                q.score(items)

    def test_holdout_dates_and_train_original_must_be_same(self):
        for index,value in ((2,698),(3,488),(4,209),
                            (8,FIRST+timedelta(days=900)),
                            (5,490)):
            items=fixture();x=list(items[1]);x[index]=value;items[1]=tuple(x)
            with self.subTest(index=index),self.assertRaises(ValueError):
                q.score(items)

    def test_atomically_persist_complete_96_hypotheses_in_local_duckdb(self):
        import duckdb
        prior=q.P
        q.P="main."
        try:
            with duckdb.connect(":memory:") as con:
                report=q.score(fixture())
                q.append_validated_audit(
                    con,"isolated-test-build","a"*40,"b"*64,"c"*64,
                    ("original-parent",),report)
                counts=con.execute("""SELECT count(*),sum(CAST(institutional_beta_released AS INTEGER)),
                     min(holm_familywise_p),max(familywise_rank)
                     FROM main.lab_joint_funding_familywise_models_v1""").fetchone()
                self.assertEqual(counts[0],96)
                self.assertEqual(counts[1],0)
                self.assertAlmostEqual(counts[2],report["min_holm_adjusted_p"])
                self.assertEqual(counts[3],96)
                build=con.execute("""SELECT model_cells,security_assets,
                     jointly_research_screen_pass,issuer_first_published_at_verified,
                     corporate_action_price_vintage_verified,
                     redistribution_rights_verified,institutional_risk_beta_released
                     FROM main.lab_joint_funding_familywise_builds_v1""").fetchone()
                self.assertEqual(build,(96,48,2,False,False,False,False))
                rejected=dict(report);rejected["rows"]=report["rows"][:-1]
                with self.assertRaisesRegex(ValueError,"Incomplete"):
                    q.append_validated_audit(con,"bad","a"*40,"b"*64,"c"*64,
                                             ("original-parent",),rejected)
                self.assertEqual(con.execute(
                    "SELECT count(*) FROM main.lab_joint_funding_familywise_builds_v1").fetchone()[0],1)
        finally:
            q.P=prior

    def test_no_original_time_or_institutional_beta_autoapprovals(self):
        source=SRC.read_text()
        for text in ("math.erfc","FAMILY=96","RELATIVE_SHIFT_THRESHOLD=0.25",
                     "REJECT_FAMILYWISE_HOLM_MULTIPLE_TESTING",
                     "REJECT_EXISTING_HOLDOUT_OR_STABILITY_SCREEN",
                     "issuer_pit_verified",
                     "vendor_adjustments_and_rights_approved",
                     "institutional_beta_released",
                     "FALSE,FALSE,FALSE,FALSE",
                     "PUBLICATION_PIT=FALSE LICENSE_RIGHTS=FALSE"):
            self.assertIn(text,source)

if __name__=="__main__":
    unittest.main()
