"""Offline source-packet, time, input and append safety tests for Treasury XML.

All date/value fixtures are synthetic and MUST NOT be described as official
Treasury yields or historically original provider publication timestamps.
"""
from datetime import date, datetime, timedelta, timezone
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch
import json
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

import duckdb

LAB=Path(__file__).resolve().parents[1]/"lab"
spec=importlib.util.spec_from_file_location(
    "phase1_treasury_current_xml_refresh",
    LAB/"phase1_treasury_current_xml_refresh.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

RECEIPT=datetime(2026,10,25,17,23,4,tzinfo=timezone.utc)
NAMESPACES='xmlns="http://www.w3.org/2005/Atom" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"'

def xml_feed(days,category,missing=None,duplicate=False,bad=None):
    fields=m.NOMINAL if category=="nominal" else m.REAL
    result=[f'<feed {NAMESPACES}>']
    for day in days+([days[0]] if duplicate else []):
        props=[f'<d:NEW_DATE>{day.isoformat()}T00:00:00</d:NEW_DATE>']
        for i,field in enumerate(dict.fromkeys(fields.values())):
            if field==missing:
                props.append(f'<d:{field}></d:{field}>')
                continue
            value=bad if field==bad else str(round(4.0+i*.2+(day.day-22)*.1,4))
            props.append(f'<d:{field}>{value}</d:{field}>')
        result.append('<entry><content><m:properties>'+
                      "".join(props)+'</m:properties></content></entry>')
    result.append('</feed>')
    return "".join(result).encode("utf-8")

def packets(days,missing_nominal=None,missing_real=None):
    values=[]
    for key in ("nominal","real"):
        raw=xml_feed(days,key,missing=(
            missing_nominal if key=="nominal" else missing_real))
        values.append({"category":key,"url":m.make_url(key,"202610"),
            "received":RECEIPT,"bytes":raw,
            "sha256":hashlib.sha256(raw).hexdigest()})
    return values

def example(packets=None,existing=None):
    return m.prepare(packets or
        globals()["packets"]([date(2026,10,23)]),
        existing or [],"unit-test-run",now=RECEIPT)


class OfficialCurrentTreasuryRefreshTests(unittest.TestCase):
    def test_source_real_curve_uses_independent_treasury_tc_tags_not_nominal_bc(self):
        self.assertEqual(set(m.REAL.values()),
                         {"TC_5YEAR","TC_7YEAR","TC_10YEAR",
                          "TC_20YEAR","TC_30YEAR"})
        self.assertEqual(set(m.REAL.values()) & set(m.NOMINAL.values()),set())
        recent=date(2026,10,23)
        original=xml_feed([recent],"real")
        for key in m.REAL.values():
            self.assertIn(("<d:"+key+">").encode(),original)
        values=m.parse_xml(original,m.REAL)
        self.assertEqual(set(values[recent]),set(m.REAL.values()))
        # A feed with ONLY nominal BC tenor tags must not be interpreted
        # as an authentic real-par-yield source.
        wrong=original
        for tenor in ("5","7","10","20","30"):
            wrong=wrong.replace(f"TC_{tenor}YEAR".encode(),
                                f"BC_{tenor}YEAR".encode())
        self.assertFalse(m.parse_xml(wrong,m.REAL)[recent])
        with self.assertRaisesRegex(ValueError,"Incomplete official"):
            original_p=packets([recent])
            original_p[1]["bytes"]=wrong
            original_p[1]["sha256"]=hashlib.sha256(wrong).hexdigest()
            example(original_p)

    def test_live_style_fetch_longer_than_30_seconds_uses_post_response_clock(self):
        # Regression from the actual MotherDuck read-only Treasury preview:
        # source GETs succeeded, but 30+ seconds of network fetch caused
        # the producer to reject its later HTTP received-at as 'future'.
        # This test executes the real main() and real source XML parser while
        # mocking only network and DuckDB. No external writes or HTTP access.
        start=datetime(2026,10,25,17,0,tzinfo=timezone.utc)
        finish=datetime(2026,10,25,17,30,tzinfo=timezone.utc)
        live=packets([date(2026,10,23)])
        fake_con=MagicMock()
        fake_con.__enter__.return_value=fake_con
        with patch.object(m,"datetime") as clock, \
             patch.object(m.requests,"Session"), \
             patch.object(m,"bounded_fetch",side_effect=live) as fetched, \
             patch.object(m.duckdb,"connect",return_value=fake_con), \
             patch.object(m,"existing_inventory",return_value=[]), \
             patch.object(m.sys,"argv",["phase1_treasury_current_xml_refresh.py"]), \
             patch.dict(m.os.environ,{"LAB_PIPELINE_COMMIT":"a"*40,
                                    "LAB_RESEARCH_SCOPE":"internal-only"}):
            clock.now.side_effect=[start,finish]
            stream=StringIO()
            with redirect_stdout(stream):
                m.main()
        result=json.loads(stream.getvalue())
        self.assertEqual(result["mode"],"READ_ONLY_PREVIEW")
        self.assertEqual(result["proposed_new_research_factor_records"],18)
        self.assertFalse(result["institutional_beta_release"])
        self.assertEqual(fetched.call_count,2)
        self.assertEqual(clock.now.call_count,2)

    def test_month_boundary_source_request_fail_closed_instead_of_mixing_months(self):
        start=datetime(2026,10,31,23,59,40,tzinfo=timezone.utc)
        finish=datetime(2026,11,1,0,0,50,tzinfo=timezone.utc)
        with patch.object(m,"datetime") as clock, \
             patch.object(m.requests,"Session"), \
             patch.object(m,"bounded_fetch",return_value={}), \
             patch.object(m.sys,"argv",["phase1_treasury_current_xml_refresh.py"]), \
             patch.dict(m.os.environ,{"LAB_PIPELINE_COMMIT":"a"*40,
                                    "LAB_RESEARCH_SCOPE":"internal-only"}):
            clock.now.side_effect=[start,finish]
            with self.assertRaisesRegex(ValueError,"crossed a UTC calendar month"):
                m.main()

    def test_exact_eighteen_factor_codes_and_derived_curve_units(self):
        self.assertEqual(len(m.ALL_FACTORS),18)
        self.assertEqual(len(m.NOMINAL),11)
        self.assertEqual(len(m.REAL),5)
        rows,dates=example()
        self.assertEqual(len(rows),18)
        self.assertEqual(len(dates),1)
        self.assertTrue(all(x["date"]==date(2026,10,23) for x in rows))
        values={x["factor_id"]:x["value"] for x in rows}
        self.assertAlmostEqual(
            values["PAR_NOMINAL_REAL_GAP_5Y"],
            values["DGS5"]-values["DGS5R"])
        self.assertAlmostEqual(
            values["PAR_NOMINAL_REAL_GAP_10Y"],
            values["DGS10"]-values["DGS10R"])
        self.assertFalse("T10YIE" in values)
        self.assertTrue(all(len(x["digest"])==64 for x in rows))
        self.assertTrue(all(x["received"]==RECEIPT for x in rows))

    def test_replay_same_factor_levels_is_true_noop(self):
        rows,_=example()
        inventory=[(x["factor_id"],x["date"],x["value"]) for x in rows]
        proposed,_=example(existing=inventory)
        self.assertEqual(proposed,[])

    def test_legacy_retrospective_equal_rates_do_not_suppress_first_xml_receipt(self):
        # Data value identity is not source-packet evidence identity.
        # The old archive may hold numerically identical Treasury CSV curves,
        # but the FIRST real original XML receipt must still be versioned.
        values,_=example()
        old=m.P
        m.P="main."
        try:
            with duckdb.connect(":memory:") as con:
                con.execute("""CREATE TABLE main.lab_factor_observations (
                  factor_id VARCHAR,observed_date DATE,value DOUBLE,
                  unit VARCHAR,ingested_at TIMESTAMPTZ,
                  availability_at TIMESTAMPTZ,availability_basis VARCHAR,
                  provider VARCHAR,source_url VARCHAR,
                  record_sha256 VARCHAR,run_id VARCHAR)""")
                con.executemany("""INSERT INTO main.lab_factor_observations
                  VALUES (?,?,?,'percent',?,?,?,?,?,?,?)""",
                  [(v["factor_id"],v["date"],v["value"],RECEIPT,RECEIPT,
                    "retrospective_archive_retrieval_only","US_TREASURY_CSV",
                    "https://home.treasury.gov/","a"*64,"old-archive")
                   for v in values])
                before=m.existing_inventory(con,RECEIPT)
                self.assertEqual(before,[])
                proposed,_=m.prepare(packets([date(2026,10,23)]),
                                     before,"first-xml",now=RECEIPT)
                self.assertEqual(len(proposed),18)
        finally:
            m.P=old

    def test_revised_real_source_value_appends_exactly_one_and_derived_rates(self):
        rows,_=example()
        existing=[(x["factor_id"],x["date"],x["value"]) for x in rows]
        changed=packets([date(2026,10,23)])
        new_real=xml_feed([date(2026,10,23)],"real").replace(
            b'<d:TC_5YEAR>4.1</d:TC_5YEAR>',
            b'<d:TC_5YEAR>4.25</d:TC_5YEAR>')
        changed[1]["bytes"]=new_real
        changed[1]["sha256"]=hashlib.sha256(new_real).hexdigest()
        self.assertNotEqual(new_real,packets([date(2026,10,23)])[1]["bytes"])
        proposed,_=example(changed,existing)
        self.assertEqual({x["factor_id"] for x in proposed},{
            "DGS5R","PAR_NOMINAL_REAL_GAP_5Y"})

    def test_duplicate_or_unmatched_nominal_real_days_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            m.parse_xml(xml_feed([date(2026,10,23)],"nominal",duplicate=True),m.NOMINAL)
        mismatch=packets([date(2026,10,23)])
        raw=xml_feed([date(2026,10,22)],"real")
        mismatch[1]["bytes"]=raw
        mismatch[1]["sha256"]=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError,"source-day mismatch"):
            example(mismatch)

    def test_no_null_tenor_silently_carried_to_new_rate_day(self):
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            example(packets([date(2026,10,23)],missing_nominal="BC_2YEAR"))
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            example(packets([date(2026,10,23)],missing_real="TC_5YEAR"))

    def test_malformed_xml_html_invalid_numbers_and_nan_fail(self):
        for raw in (b"<html></html>",b"<feed/>",b"junk",
                    xml_feed([date(2026,10,23)],"nominal").replace(
                      b'<d:BC_2YEAR>4.9</d:BC_2YEAR>',
                      b'<d:BC_2YEAR>NaN</d:BC_2YEAR>')):
            with self.subTest(raw=raw[:20]),self.assertRaises(ValueError):
                m.parse_xml(raw,m.NOMINAL)

    def test_bad_packet_digest_wrong_month_or_future_receipt_denied(self):
        for mutation,pattern in (
            (lambda x: x[0].update(sha256="0"*64),"SHA256"),
            (lambda x: x[0].update(url=m.make_url("nominal","202609")),"URL"),
            (lambda x: x[0].update(received=RECEIPT+timedelta(hours=1)),"chronology"),
        ):
            p=packets([date(2026,10,23)])
            mutation(p)
            with self.subTest(pattern=pattern),self.assertRaisesRegex(ValueError,pattern):
                example(p)

    def test_future_and_old_source_dates_never_backdated_as_new_captures(self):
        for day in (date(2026,10,1),date(2026,10,24)):
            p=packets([day])
            proposed,days=example(p)
            self.assertEqual(len(proposed),0 if day.day==1 else 18)
        # A source claiming a future observed day must be filtered, not
        # introduced as a prepublished active market factor.
        p=packets([date(2026,10,26)])
        proposed,_=example(p)
        self.assertEqual(len(proposed),0)

    def test_real_original_receipt_and_immutable_source_packet_sha_on_append(self):
        rows,covered=example()
        prev=m.P
        m.P="main."
        try:
            with duckdb.connect(":memory:") as con:
                con.execute("""CREATE TABLE main.lab_factor_observations(
                    factor_id VARCHAR,observed_date DATE,value DOUBLE,
                    unit VARCHAR,ingested_at TIMESTAMPTZ,
                    availability_at TIMESTAMPTZ,availability_basis VARCHAR,
                    provider VARCHAR,source_url VARCHAR,
                    record_sha256 VARCHAR,run_id VARCHAR)""")
                m.append(con,rows,packets([date(2026,10,23)]),
                         "unit-test-run","a"*40,"b"*64,len(covered))
                v=con.execute("""SELECT COUNT(*),
                    COUNT(*) FILTER(WHERE availability_at != ingested_at),
                    COUNT(*) FILTER(WHERE factor_id LIKE 'PAR_%'),
                    COUNT(*) FILTER(WHERE availability_basis
                       != 'official_xml_http_receipt_not_original_publication')
                    FROM main.lab_factor_observations""").fetchone()
                self.assertEqual(v,(18,0,2,0))
                clocks=con.execute("""SELECT min(ingested_at),
                    max(availability_at) FROM main.lab_factor_observations
                """).fetchone()
                self.assertGreater(clocks[0],RECEIPT)
                self.assertEqual(clocks[0],clocks[1])
                finished=con.execute("""SELECT finished_at
                   FROM main.lab_treasury_current_xml_runs_v1""").fetchone()[0]
                self.assertLessEqual(clocks[1],finished)
                raw=con.execute("""SELECT original_payload_bytes,
                   original_payload_sha256,original_publisher_first_release_verified,
                   licensed_institutional_risk_use_approved
                   FROM main.lab_treasury_current_xml_packets_v1
                   ORDER BY source_category""").fetchall()
                self.assertEqual(len(raw),2)
                self.assertTrue(all(hashlib.sha256(bytes(r[0])).hexdigest()==r[1] and
                                    r[2] is False and r[3] is False for r in raw))
                manifest=con.execute("""SELECT new_factor_vintages,
                  original_publication_pit_verified,
                  licensed_distribution_approved,institutional_beta_release
                  FROM main.lab_treasury_current_xml_runs_v1""").fetchone()
                self.assertEqual(manifest,(18,False,False,False))
        finally:
            m.P=prev

    def test_external_source_url_is_strict_month_and_domain_allowlist(self):
        self.assertTrue(m.make_url("nominal","202610").startswith(
            "https://home.treasury.gov/"))
        for args in (("other","202610"),("nominal","2026111"),
                     ("real","2026-10"),("real","190001")):
            with self.subTest(args=args),self.assertRaises(ValueError):
                m.make_url(*args)

    def test_invalid_or_dup_inventory_and_unsupported_source_class_fail(self):
        p=packets([date(2026,10,23)])
        with self.assertRaises(ValueError):
            example(p,[("BAD",date(2026,10,23),4.0)])
        with self.assertRaises(ValueError):
            example(p,[("DGS2",date(2026,10,23),4.0)]*2)
        p[0]["category"]="derived"
        with self.assertRaises(ValueError):
            example(p)

    def test_no_source_pit_approval_and_no_scheduled_automation(self):
        code=(LAB/"phase1_treasury_current_xml_refresh.py").read_text()
        self.assertIn("LAB_SOURCE_REFRESH_WRITE_ACK",code)
        self.assertIn("READ_ONLY_PREVIEW",code)
        self.assertIn("first_release_verified BOOLEAN",code)
        self.assertIn("licensed_institutional_risk_use_approved BOOLEAN",code)
        self.assertIn("MAX_RECENT_SOURCE_DAYS=10",code)
        self.assertNotIn("historical_pit_verified=True",code)
        self.assertNotIn("first_published_at=observed_date",code)


if __name__=="__main__":
    unittest.main()
