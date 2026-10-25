"""Adversarial independent acceptance of Treasury raw source bytes and receipt clocks.

All quote and rate values are synthetic. Assertions never certify Treasury
first release, licensed use or institutional event/return risk factors.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
sys.path.insert(0,str(LAB))
sys.path.insert(0,str(LAB.parent/"tests"))
from test_lab_treasury_current_xml_refresh import packets,example,RECEIPT
import phase1_treasury_current_xml_refresh as source

spec=importlib.util.spec_from_file_location(
    "phase1_treasury_receipt_acceptance",LAB/"phase1_treasury_receipt_acceptance.py")
qa=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=qa
spec.loader.exec_module(qa)

COMMIT="a"*40
SOURCE_SHA=hashlib.sha256(
    (LAB/"phase1_treasury_current_xml_refresh.py").read_bytes()).hexdigest()

def fixture():
    con=duckdb.connect(":memory:")
    con.execute("""CREATE TABLE main.lab_factor_observations(
       factor_id VARCHAR,observed_date DATE,value DOUBLE,
       unit VARCHAR,ingested_at TIMESTAMPTZ,availability_at TIMESTAMPTZ,
       availability_basis VARCHAR,provider VARCHAR,source_url VARCHAR,
       record_sha256 VARCHAR,run_id VARCHAR)""")
    src=packets([RECEIPT.date()-timedelta(days=2)])
    candidate,days=source.prepare(src,[], "unit-test-run",now=RECEIPT)
    old=source.P
    source.P="main."
    try:
        source.append(con,candidate,src,"unit-test-run",COMMIT,
                      SOURCE_SHA,len(days))
    finally:
        source.P=old
    return con


class OriginalReceiptAcceptanceTests(unittest.TestCase):
    def test_complete_source_packet_byte_hash_and_all_factor_rows_reconcile(self):
        with fixture() as con:
            data=qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")
        self.assertEqual(data["status"],qa.VERIFIED)
        self.assertEqual(data["new_or_revised_factor_rows"],18)
        self.assertEqual(data["complete_recent_source_observation_days"],1)
        self.assertEqual(set(data["received_xml_categories"]),{"nominal","real"})
        self.assertEqual(len(data["archived_payload_sha256"]),2)
        self.assertFalse(data["official_first_published_at_independently_verified"])
        self.assertFalse(data["commercial_data_redistribution_approved"])
        self.assertFalse(data["institutional_model_beta_approved"])

    def test_wrong_git_or_source_code_hash_is_blocked(self):
        with fixture() as con:
            for changed,expected in (("0"*40,SOURCE_SHA),
                                     (COMMIT,"0"*64)):
                with self.subTest(changed=changed,expected=expected):
                    with self.assertRaisesRegex(ValueError,"producer build"):
                        qa.inspect(con,changed,expected,prefix="main.")

    def test_tampered_source_packet_sha_or_original_bytes_rejected(self):
        with fixture() as con:
            con.execute("""UPDATE main.lab_treasury_current_xml_packets_v1
                SET original_payload_sha256=? WHERE source_category='nominal'""",
                ["0"*64])
            with self.assertRaisesRegex(ValueError,"SHA/URL"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")
        with fixture() as con:
            con.execute("""UPDATE main.lab_treasury_current_xml_packets_v1
                SET original_payload_bytes=? WHERE source_category='nominal'""",
                [b"corrupted"])
            with self.assertRaisesRegex(ValueError,"SHA/URL"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")

    def test_shifted_source_warehouse_availability_and_original_value_rejected(self):
        with fixture() as con:
            con.execute("""UPDATE main.lab_factor_observations
                 SET availability_at=availability_at+INTERVAL '5 minutes'
                 WHERE factor_id='DGS2'""")
            with self.assertRaisesRegex(ValueError,"availability drift"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")
        with fixture() as con:
            con.execute("""UPDATE main.lab_factor_observations
                 SET value=value+.1 WHERE factor_id='DGS2'""")
            with self.assertRaisesRegex(ValueError,"value"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")
        with fixture() as con:
            con.execute("""UPDATE main.lab_factor_observations
                 SET record_sha256=? WHERE factor_id='DGS2'""",["e"*64])
            with self.assertRaisesRegex(ValueError,"digest"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")

    def test_missing_original_rate_rows_rejected(self):
        with fixture() as con:
            con.execute("""DELETE FROM main.lab_factor_observations
                WHERE factor_id='DGS5'""")
            with self.assertRaisesRegex(ValueError,"missing"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")

    def test_duplicate_or_invented_rate_source_identity_rejected(self):
        with fixture() as con:
            con.execute("""INSERT INTO main.lab_factor_observations
                SELECT * FROM main.lab_factor_observations WHERE factor_id='DGS2'""")
            with self.assertRaisesRegex(ValueError,"missing"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")
        with fixture() as con:
            con.execute("""UPDATE main.lab_factor_observations
                SET observed_date='2026-10-12' WHERE factor_id='DGS2'""")
            with self.assertRaisesRegex(ValueError,"invented"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")

    def test_source_provider_rights_or_pit_flags_never_true(self):
        with fixture() as con:
            con.execute("""UPDATE main.lab_treasury_current_xml_runs_v1
                SET institutional_beta_release=TRUE""")
            with self.assertRaisesRegex(ValueError,"approval state"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")
        with fixture() as con:
            con.execute("""UPDATE main.lab_treasury_current_xml_packets_v1
                SET original_publisher_first_release_verified=TRUE
                WHERE source_category='real'""")
            with self.assertRaisesRegex(ValueError,"approval"):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")

    def test_bad_receipt_time_cannot_precede_hypothesized_preexisting_source(self):
        with fixture() as con:
            con.execute("""UPDATE main.lab_treasury_current_xml_packets_v1
                SET source_received_at=source_received_at+INTERVAL '20 hours'
                WHERE source_category='real'""")
            with self.assertRaises(ValueError):
                qa.inspect(con,COMMIT,SOURCE_SHA,prefix="main.")

    def test_zero_append_noop_manifest_keeps_original_packet_evidence(self):
        with fixture() as con:
            # Synthetic extra no-op run reuses original source bytes, not
            # fresh data. No factor rows should be fabricated.
            old=source.P
            source.P="main."
            try:
                src=packets([RECEIPT.date()-timedelta(days=2)])
                source.append(con,[],src,"noop-unit-test",COMMIT,
                              SOURCE_SHA,1)
            finally:
                source.P=old
            r=con.execute("""SELECT new_factor_vintages FROM
                main.lab_treasury_current_xml_runs_v1
                WHERE run_id='noop-unit-test'""").fetchone()
            self.assertEqual(r,(0,))
            # An unbacked zero-row report is NOT a legitimate no-op.
            manifest=con.execute("""SELECT run_id,source_git_sha,source_script_sha256,
                finished_at,source_nominal_sha256,source_real_sha256,
                source_observation_days,new_factor_vintages,
                original_publication_pit_verified,licensed_distribution_approved,
                institutional_beta_release,status
                FROM main.lab_treasury_current_xml_runs_v1
                WHERE run_id='noop-unit-test'""").fetchone()
            packet_rows=con.execute("""SELECT run_id,source_category,source_url,
                source_received_at,original_payload_sha256,original_payload_bytes,
                original_publisher_first_release_verified,
                licensed_institutional_risk_use_approved
                FROM main.lab_treasury_current_xml_packets_v1
                WHERE run_id='noop-unit-test' ORDER BY source_category""").fetchall()
            prior=con.execute("""SELECT factor_id,observed_date,value
                FROM main.lab_factor_observations WHERE run_id='unit-test-run'""").fetchall()
            verified=qa.audit(manifest,packet_rows,[],COMMIT,SOURCE_SHA,
                              prior_source_inventory=prior)
            self.assertEqual(verified["new_or_revised_factor_rows"],0)
            with self.assertRaisesRegex(ValueError,
                                        "does not match actual new/revised"):
                qa.audit(manifest,packet_rows,[],COMMIT,SOURCE_SHA,
                         prior_source_inventory=[])

    def test_read_only_validator_cannot_self_approve(self):
        text=(LAB/"phase1_treasury_receipt_acceptance.py").read_text()
        self.assertIn("source.prepare(raw,[],run",text)
        self.assertIn("official_first_published_at_independently_verified",text)
        self.assertNotIn("INSERT INTO",text)
        self.assertNotIn("UPDATE main.",text)


if __name__=="__main__":
    unittest.main()
