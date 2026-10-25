"""No-network source-locked reconstruction of paired security holdout losses.

Uses synthetic 48-security, 620-shared-date fixtures only. Real market/model
outputs MUST be reconciled to immutable warehouse source and first-vintage
evidence before anyone interprets them as original point-in-time estimates.
"""
from datetime import date,timedelta
import importlib.util
from pathlib import Path
import sys
import unittest
import hashlib

import duckdb
import numpy as np

LAB=Path(__file__).resolve().parents[1]/"lab"
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location(
    "joint_daily_paired_loss_research",
    LAB/"phase1_joint_daily_paired_loss_research.py")
q=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=q
spec.loader.exec_module(q)


def synthetic_parent():
    rng=np.random.default_rng(20991)
    n=620
    market=rng.normal(0,85,n)
    d2=rng.normal(0,4,n)
    d10=.5*d2+rng.normal(0,4,n)
    funding=rng.normal(0,2,n)
    x=np.column_stack((market,d2,d10,funding))
    days=[date(2024,1,1)+timedelta(days=k) for k in range(n)]
    rows=[]
    for i in range(48):
        noise=rng.normal(0,12,n)
        response=market*.7+d2*.2-d10*.35+funding*(3.+i*.005)+noise
        for j in range(n):
            rows.append((f"SEC{i:02d}",days[j],float(response[j]),
                *(float(z) for z in x[j]),j in (10,95),0))
    fits=q.parent_method.compute_all(rows)
    evidence=[tuple(f[k] for k in q.PARENT_METRICS)+(0,) for f in fits]
    return rows,fits,evidence


class PairedDailyForecastLossReconstruction(unittest.TestCase):
    def test_parent_provenance_and_reconstructed_daily_loss_mse(self):
        rows,fits,evidence=synthetic_parent()
        one=[r for r in rows if r[0]=="SEC00"]
        fit=next(f for f in fits if f["ticker"]=="SEC00" and
                 f["variant"]=="full_training")
        q.check_parent_record(
            next(r for r in evidence if r[:2]==("SEC00","full_training")),fit)
        pairs=q.reconstruct_one(one,fit)
        self.assertEqual(len(pairs),fit["n_holdout"])
        self.assertEqual(pairs[0][2],fit["holdout_first"])
        self.assertEqual(pairs[-1][2],fit["last"])
        self.assertTrue(all(r[3]<r[2] for r in pairs))
        self.assertAlmostEqual(np.mean([r[7] for r in pairs]),
                               fit["baseline_mse"],places=5)
        self.assertAlmostEqual(np.mean([r[8] for r in pairs]),
                               fit["joint_mse"],places=5)

    def test_complete_48_asset_date_panel_feeds_two_shared_date_bootstraps(self):
        rows,fits,evidence=synthetic_parent()
        paired,reports=q.reconstruct(rows,evidence)
        self.assertEqual(len(paired),48*2*186)
        self.assertEqual(set(reports),set(q.parent_method.VARIANTS))
        self.assertEqual({r["independent_date_count"] for r in reports.values()},{186})
        self.assertEqual({r["security_count"] for r in reports.values()},{48})
        self.assertEqual(len({(r[0],r[1],r[2]) for r in paired}),len(paired))
        self.assertTrue(all(r["institutional_risk_model_released"] is False
                            for r in reports.values()))

    def test_parent_source_coefficient_or_release_drift_fails_closed(self):
        rows,fits,evidence=synthetic_parent()
        fit=fits[0]
        correct=list(evidence[0])
        for change,expected in (
            ({q.PARENT_METRICS.index("funding_beta"):fit["funding_beta"]+.10},
             "coefficient"),
            ({q.PARENT_METRICS.index("funding_hac_se"):-1}, "coefficient"),
            ({q.PARENT_METRICS.index("market_beta"):fit["market_beta"]+.25},
             "coefficient"),
            ({q.PARENT_METRICS.index("dgs2_beta"):fit["dgs2_beta"]+.25},
             "coefficient"),
            ({q.PARENT_METRICS.index("dgs10_beta"):fit["dgs10_beta"]+.25},
             "coefficient"),
            ({q.PARENT_METRICS.index("first_half_beta"):
                 fit["first_half_beta"]+.25}, "coefficient"),
            ({q.PARENT_METRICS.index("second_half_beta"):
                 fit["second_half_beta"]+.25}, "coefficient"),
            ({q.PARENT_METRICS.index("sign_stable"):
                 not fit["sign_stable"]}, "coefficient"),
            ({q.PARENT_METRICS.index("condition"):
                 fit["condition"]+.25}, "coefficient"),
            ({q.PARENT_METRICS.index("ci_low"):
                 fit["ci_low"]+.25}, "coefficient"),
            ({q.PARENT_METRICS.index("excluded_train"):
                 fit["excluded_train"]+1}, "chronology"),
            ({q.PARENT_METRICS.index("research_status"):"APPROVED"},
             "chronology"),
            ({q.PARENT_METRICS.index("first"):date(2020,1,1)},
             "chronology"),
            ({len(q.PARENT_METRICS):1},"release"),
        ):
            test=correct.copy()
            for k,v in change.items():test[k]=v
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,expected):
                q.check_parent_record(tuple(test),fit)

    def test_original_parent_source_code_bytes_sha_must_match_exactly(self):
        class ReplayRow:
            def __init__(self, sha):
                self.sha=sha
            def fetchone(self):
                return (self.sha,)
        class FakeSource:
            def __init__(self, sha):
                self.sha=sha
                self.queries=[]
            def execute(self,sql,params):
                self.queries.append((sql,params))
                return ReplayRow(self.sha)
        path=Path(q.parent_method.__file__)
        correct=hashlib.sha256(path.read_bytes()).hexdigest()
        source=FakeSource(correct)
        self.assertEqual(q.check_original_method_hash(source,"parent-build"),correct)
        self.assertEqual(source.queries[0][1],["parent-build"])
        with self.assertRaisesRegex(ValueError,"implementation SHA256 changed"):
            q.check_original_method_hash(FakeSource("0"*64),"parent-build")

    def test_every_original_model_metric_including_rate_betas_is_reconciled(self):
        rows,fits,evidence=synthetic_parent()
        self.assertEqual(len(q.PARENT_METRICS),27)
        self.assertEqual(len(evidence[0]),28)
        self.assertTrue(all(q.check_parent_record(src,fit) is None
                            for src,fit in zip(evidence,fits)))

    def test_parent_identity_missing_or_colliding_fails(self):
        rows,_,evidence=synthetic_parent()
        with self.assertRaisesRegex(ValueError,"Incomplete parent"):
            q.reconstruct(rows,evidence[:-1])
        bad=list(evidence)
        bad[-1]=bad[0]
        with self.assertRaisesRegex(ValueError,"Duplicate parent"):
            q.reconstruct(rows,bad)

    def test_parent_retrospective_training_exclusion_population_is_reproduced(self):
        rows,fits,_=synthetic_parent()
        one=[r for r in rows if r[0]=="SEC00"]
        trimmed=next(f for f in fits if f["ticker"]=="SEC00" and
                     f["variant"]=="training_tail_exclusion")
        changed=list(one)
        for i,r in enumerate(changed):
            if r[1]==trimmed["first"]:
                x=list(r);x[7]=True;changed[i]=tuple(x)
        with self.assertRaisesRegex(ValueError,"training-exclusion"):
            q.reconstruct_one(changed,trimmed)

    def test_parent_training_holdout_days_refused_if_new_data_reordered(self):
        rows,fits,_=synthetic_parent()
        one=[r for r in rows if r[0]=="SEC00"]
        fit=next(f for f in fits if f["ticker"]=="SEC00" and
                 f["variant"]=="full_training")
        swapped=list(one)
        cut=fit["n_train"]
        swapped[cut-1],swapped[cut]=swapped[cut],swapped[cut-1]
        # Source is sorted before estimation: mere order-of-input changes
        # are harmless, but *changed boundary dates or missing rows* are not.
        self.assertEqual(len(q.reconstruct_one(swapped,fit)),fit["n_holdout"])
        removed=one[:cut-1]+one[cut:]
        with self.assertRaisesRegex(ValueError,"Duplicated, missing"):
            q.reconstruct_one(removed,fit)

    def test_local_in_memory_append_is_atomic_and_never_approves_pit(self):
        rows,_,evidence=synthetic_parent()
        daily,reports=q.reconstruct(rows,evidence)
        previous=q.P
        q.P="main."
        try:
            with duckdb.connect(":memory:") as con:
                q.append_research(con,"offline-synthetic-not-real","a"*40,
                                  "b"*64,"parent-fixture",daily,reports)
                total=con.execute(
                    "SELECT count(*),count(*) FILTER(WHERE "
                    "institutional_beta_released OR original_factor_publication_asof_verified)"
                    " FROM main.lab_joint_funding_daily_paired_losses_v1"
                ).fetchone()
                self.assertEqual(total,(48*2*186,0))
                summary=con.execute(
                    "SELECT count(*),max(securities),max(shared_holdout_dates),"
                    "bool_or(institutional_beta_release) FROM "
                    "main.lab_joint_funding_daily_loss_builds_v1"
                ).fetchone()
                self.assertEqual(summary,(1,48,186,False))
                boot=con.execute(
                    "SELECT count(*),sum(CAST(institutional_beta_released AS INTEGER))"
                    " FROM main.lab_joint_funding_shared_date_builds_v1"
                ).fetchone()
                self.assertEqual(boot,(2,0))
        finally:
            q.P=previous

    def test_producer_requires_research_authorization_and_no_source_fabrication(self):
        code=(LAB/"phase1_joint_daily_paired_loss_research.py").read_text()
        for s in ("--append-research","LAB_RESEARCH_WRITE_ACK",
                  "source_rows_sha256","source_sha!=parent_build[2]",
                  "check_original_method_hash(con,parent_build[0])",
                  "parent_method.sql_inputs(con)","check_parent_record",
                  "shared_date.assess","RETROSPECTIVE_PAIRED_PREDICTION"):
            self.assertIn(s,code)
        self.assertNotIn("requests.get",code)
        self.assertNotIn("urllib.request",code)
        self.assertNotIn("institutional_beta_release=True",code)


if __name__=="__main__":
    unittest.main()
