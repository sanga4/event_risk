"""BEA original economic release: actual reported values != first-release PIT."""
from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock,patch
import hashlib
from io import StringIO
from contextlib import redirect_stdout
import json

LAB=Path(__file__).resolve().parents[1]/"lab"
spec=importlib.util.spec_from_file_location("phase1_bea_original_economic_release_value_receipt",
  LAB/"phase1_bea_original_economic_release_value_receipt.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)
RECEIVED=datetime(2026,10,26,3,15,tzinfo=timezone.utc)
PCE={
 "Current-dollar personal income":("0.3","0.2"),
 "Current-dollar DPI":("0.4","0.3"),
 "Real DPI":("0.3","0.0"),
 "Current-dollar PCE":("0.1","0.9"),
 "Real PCE":("0.1","0.6"),
 "PCE price index":("0.1","0.3"),
 "PCE price index excluding food and energy":("0.1","0.2")
}
TRADES={"Deficit:":"$105.6 Billion","Exports:":"$315.2 Billion","Imports:":"$420.8 Billion"}

def source(kind,values=None):
    if kind==m.SOURCES[0][0]:
        vals=PCE if values is None else values
        trs="".join(f"<tr><td>{k}</td><td>{v[0]}</td><td>{v[1]}</td></tr>"
                    for k,v in vals.items())
        table="<table class='table-md'><tr><th>Personal Income and Related Measures</th></tr>"+trs+"</table>"
        name=m.SOURCES[0][2]
    else:
        vals=TRADES if values is None else values
        trs="".join(f"<tr><td>{k}</td><td>{v}</td><td>+3.5%</td></tr>"
                    for k,v in vals.items())
        table="<table class='table-release-trade'>"+trs+"</table>"
        name=m.SOURCES[1][2]
    raw=("<html><h1>News Release</h1><h1>"+name+"</h1>"+table+"</html>").encode()
    src=next(s for s in m.SOURCES if s[0]==kind)
    return {"kind":kind,"url":src[1],"raw_html":raw,"sha256":hashlib.sha256(raw).hexdigest(),
            "received_at":RECEIVED}

class OriginalBeaEconomicReleaseEvidence(unittest.TestCase):
    def test_actual_pce_monthly_percent_rows(self):
        rows=m.parse(source(m.SOURCES[0][0]))
        self.assertEqual(len(rows),7)
        self.assertEqual({x["metric"] for x in rows},set(PCE))
        self.assertEqual(next(x["reported_value"] for x in rows if x["metric"]=="Real PCE"),0.6)
        self.assertEqual(next(x["reported_value"] for x in rows if x["metric"]=="PCE price index excluding food and energy"),0.2)
        self.assertTrue(all(x["unit"]=="percent_change_from_previous_month" for x in rows))
    def test_actual_trade_amount_rows_are_billion_dollar_magnitudes(self):
        rows=m.parse(source(m.SOURCES[1][0]))
        self.assertEqual(len(rows),3)
        self.assertEqual({x["metric"]:x["reported_value"] for x in rows},{
            "deficit_reported_magnitude":105.6,"exports_reported_magnitude":315.2,
            "imports_reported_magnitude":420.8})
        self.assertTrue(all(x["unit"]=="usd_billions" for x in rows))
    def test_missing_pce_measure_fails_closed(self):
        vals=dict(PCE);del vals["Real PCE"]
        with self.assertRaisesRegex(ValueError,"seven"):
            m.parse(source(m.SOURCES[0][0],vals))
    def test_modified_source_sha_fails_closed(self):
        p=source(m.SOURCES[0][0]);p["sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"packet"):
            m.parse(p)
    def test_wrong_issuer_release_title_fails_closed(self):
        p=source(m.SOURCES[1][0])
        p["raw_html"]=p["raw_html"].replace(b"U.S. International Trade",b"Revised National Accounts")
        p["sha256"]=hashlib.sha256(p["raw_html"]).hexdigest()
        with self.assertRaisesRegex(ValueError,"headline"):
            m.parse(p)
    def test_duplicate_pce_measure_fails_closed(self):
        p=source(m.SOURCES[0][0])
        p["raw_html"]=p["raw_html"].replace(
            b"</table>",b"<tr><td>Real PCE</td><td>0.1</td><td>0.6</td></tr></table>")
        p["sha256"]=hashlib.sha256(p["raw_html"]).hexdigest()
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            m.parse(p)
    def test_bad_trade_units_fails_closed(self):
        vals=dict(TRADES);vals["Exports:"]="$315.2 Million"
        with self.assertRaisesRegex(ValueError,"dollar billions"):
            m.parse(source(m.SOURCES[1][0],vals))
    def test_unauthorized_url_http_redirect_content_rejected(self):
        session=MagicMock()
        response=session.get.return_value
        response.status_code=200
        response.url=m.SOURCES[0][1];response.is_redirect=False
        response.headers={"Content-Type":"text/html"}
        response.content=b"x"*15000
        with self.assertRaisesRegex(ValueError,"Unapproved"):
            m.fetch(session,m.SOURCES[0][0],"https://other.example.invalid/")
        response.status_code=403
        with self.assertRaisesRegex(ValueError,"exact URL"):
            m.fetch(session,m.SOURCES[0][0],m.SOURCES[0][1])
        response.status_code=200;response.url="https://imposter.example.invalid/"
        with self.assertRaisesRegex(ValueError,"exact URL"):
            m.fetch(session,m.SOURCES[0][0],m.SOURCES[0][1])
        response.url=m.SOURCES[0][1];response.headers={"Content-Type":"application/json"}
        with self.assertRaisesRegex(ValueError,"not HTML"):
            m.fetch(session,m.SOURCES[0][0],m.SOURCES[0][1])
    def test_research_writer_disabled_without_deliberate_ack(self):
        with patch.dict(m.os.environ,{"LAB_RESEARCH_WRITE_ACK":"disabled"}):
            with self.assertRaisesRegex(RuntimeError,"acknowledgment"):
                m.archive(None,[],{},"")
    def test_default_preview_does_not_write_or_claim_historical_first_known(self):
        original=[source(k) for k,_,_ in m.SOURCES]
        with patch.object(m.requests,"Session"),\
             patch.object(m,"fetch",side_effect=original),\
             patch.object(sys,"argv",["source_preview"]),\
             patch.dict(m.os.environ,{"LAB_RESEARCH_SCOPE":"internal-only",
                                      "LAB_PIPELINE_COMMIT":"a"*40}):
            f=StringIO()
            with redirect_stdout(f):m.main()
        data=json.loads(f.getvalue())
        self.assertEqual(data["mode"],"READ_ONLY_PREVIEW")
        self.assertEqual(data["source_reported_value_count"],10)
        for key in ("first_publisher_release_time_verified",
                    "historical_as_first_known_pit_approved",
                    "original_survey_consensus_verified",
                    "contractual_downstream_use_approved",
                    "institutional_event_beta_approved"):
            self.assertIs(data[key],False)
    def test_not_impersonating_institutional_source_release_calendar(self):
        s=(LAB/"phase1_bea_original_economic_release_value_receipt.py").read_text()
        self.assertNotIn("CREATE TABLE IF NOT EXISTS eventrisk_factor_lab.main.lab_source_release_vintages_v1",s)
        self.assertIn("publisher_first_known_at TIMESTAMPTZ",s)
        self.assertIn("verified_announcement_surprise DOUBLE",s)
        self.assertIn("FALSE,FALSE,FALSE,FALSE",s)

if __name__=="__main__":
    unittest.main()
