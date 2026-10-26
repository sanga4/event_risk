"""Source receipt only: official BEA schedule cannot certify actual releases."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock,patch

LAB=Path(__file__).resolve().parents[1]/"lab"
spec=importlib.util.spec_from_file_location(
    "phase1_bea_official_release_schedule_receipt",
    LAB/"phase1_bea_official_release_schedule_receipt.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)
RECEIVED=datetime(2026,10,26,2,33,tzinfo=timezone.utc)
SHA="a"*40

def html(rows=None,year=2026):
    if rows is None:
        rows=[
            ("October 29 8:30 AM","News","GDP (Advance Estimate), 3rd Quarter 2026"),
            ("November 25 8:30 AM","News","Personal Income and Outlays, October 2026"),
            ("December 23 8:30 AM","News","U.S. International Trade in Goods and Services")
        ]
    parts="".join("<tr><td>"+a+"</td><td>"+b+"</td><td>"+c+"</td></tr>"
                  for a,b,c in rows)
    return (f"<html><body><table id='release-schedule-table'>"
            f"<thead><tr><th>Year {year}</th><th></th><th>Release</th></tr></thead>"
            f"<tbody>{parts}</tbody></table></body></html>").encode()

class OfficialCalendarSourceLimits(unittest.TestCase):
    def test_scheduled_et_is_converted_by_zone_and_not_declared_published(self):
        rows,tba,year=m.parse(html(),RECEIVED)
        self.assertEqual((len(rows),tba,year),(3,0,2026))
        self.assertEqual(rows[0]["scheduled_at_utc"].isoformat(),
                         "2026-10-29T12:30:00+00:00")  # EDT
        self.assertEqual(rows[1]["scheduled_at_utc"].isoformat(),
                         "2026-11-25T13:30:00+00:00")  # EST
        self.assertEqual(len({x["source_key_sha256"] for x in rows}),3)
        self.assertTrue(all(x["scheduled_at_utc"].tzinfo for x in rows))

    def test_announcements_without_a_clock_are_not_assumed_published(self):
        rows=[
            ("October 29 8:30 AM","News","GDP"),
            ("November 25 8:30 AM","News","PCE"),
            ("December 23 8:30 AM","News","Trade"),
            ("To Be Announced","News","Unspecified Release")]
        result,tba,_=m.parse(html(rows),RECEIVED)
        self.assertEqual(len(result),3)
        self.assertEqual(tba,1)

    def test_duplicate_scheduled_source_identity_rejected(self):
        line=("October 29 8:30 AM","News","GDP")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            m.parse(html([line,line,line]),RECEIVED)

    def test_fake_release_year_rejected(self):
        with self.assertRaisesRegex(ValueError,"receipt window"):
            m.parse(html(year=2005),RECEIVED)

    def test_layout_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"table missing"):
            m.parse(b"<html><h1>releases</h1></html>",RECEIVED)
        wrong=b"<table id='release-schedule-table'><tbody><tr><td>GDP</td></tr></tbody></table>"
        with self.assertRaisesRegex(ValueError,"heading"):
            m.parse(wrong,RECEIVED)

    def test_malformed_source_time_or_untimed_row_is_rejected(self):
        h=html([
            ("Oct. 29, 2026","News","GDP"),
            ("November 25 8:30 AM","News","PCE"),
            ("December 23 8:30 AM","News","Trade")])
        with self.assertRaisesRegex(ValueError,"UTC time"):
            m.parse(h,RECEIVED)

    def test_official_source_http_authentication_and_size_controls(self):
        fake=MagicMock()
        fake.status_code=403
        fake.url=m.URL
        fake.is_redirect=False
        fake.headers={"Content-Type":"text/html"}
        fake.content=html()*9
        sess=MagicMock()
        sess.get.return_value=fake
        with self.assertRaisesRegex(ValueError,"not authorized"):
            m.fetch(sess)
        fake.status_code=200
        fake.url="https://imposter.example.org/"
        with self.assertRaisesRegex(ValueError,"not authorized"):
            m.fetch(sess)
        fake.url=m.URL
        fake.headers={"Content-Type":"application/json"}
        with self.assertRaisesRegex(ValueError,"text/html"):
            m.fetch(sess)
        fake.headers={"Content-Type":"text/html; charset=UTF-8"}
        data,timestamp=m.fetch(sess)
        self.assertEqual(data,fake.content)
        self.assertIsNotNone(timestamp.tzinfo)

    def test_preview_runs_without_writing_and_never_sets_release_approvals(self):
        fake=MagicMock()
        fake.__enter__.return_value=fake
        payload=html()*9
        with patch.object(m.requests,"Session",return_value=fake),\
             patch.object(m,"fetch",return_value=(payload,RECEIVED)),\
             patch.object(m,"parse",return_value=(*m.parse(html(),RECEIVED)[:2],2026)),\
             patch.object(sys,"argv",["bea_release.py"]),\
             patch.dict(m.os.environ,{"LAB_RESEARCH_SCOPE":"internal-only",
                                      "LAB_PIPELINE_COMMIT":SHA}):
            capture=StringIO()
            with redirect_stdout(capture):
                m.main()
        info=json.loads(capture.getvalue())
        self.assertEqual(info["mode"],"READ_ONLY_PREVIEW")
        self.assertEqual(info["valid_scheduled_entries"],3)
        for key in ("actual_publication_verified",
                    "reported_economic_value_verified",
                    "pre_event_consensus_verified","source_rights_approved",
                    "institutional_event_beta_approved"):
            self.assertIs(info[key],False)

    def test_append_requires_active_owner_research_ack(self):
        with patch.dict(m.os.environ,{"LAB_RESEARCH_WRITE_ACK":"disabled"}):
            with self.assertRaisesRegex(RuntimeError,"acknowledgement"):
                m.append(None,"x","y",b"abc",RECEIVED,[],0,2026)

    def test_no_source_schedule_claims_to_populate_original_release_vintages(self):
        source=(LAB/"phase1_bea_official_release_schedule_receipt.py").read_text()
        self.assertNotIn("CREATE TABLE IF NOT EXISTS eventrisk_factor_lab.main.lab_source_release_vintages_v1",source)
        self.assertIn("actual_published_at TIMESTAMPTZ",source)
        self.assertIn("pre_event_consensus_verified BOOLEAN",source)
        self.assertIn("FALSE,FALSE,FALSE,FALSE,FALSE",source)

if __name__=="__main__":
    unittest.main()
