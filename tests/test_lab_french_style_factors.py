"""Offline fixtures for official French-style DAILY archives and rights/PIT gating."""
from __future__ import annotations
from datetime import date
import importlib.util
import io
from pathlib import Path
import sys
import unittest
import zipfile

PATH=Path(__file__).resolve().parents[1]/"lab"/"phase1_french_style_factor_backfill.py"
sp=importlib.util.spec_from_file_location("french_loader",PATH)
mod=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=mod
sp.loader.exec_module(mod)


def archive(text):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("test.csv",text)
    return b.getvalue()


def sample(n,header,values):
    out=["Provider Data Library source metadata","",header]
    d=date(2010,1,1)
    from datetime import timedelta
    for i in range(n):
        day=d+timedelta(days=i)
        out.append(day.strftime("%Y%m%d")+","+values)
    out.extend(["","Annual Factors:","201001,1,2,3,4,5,6"])
    return "\n".join(out)


class FrenchArchiveTests(unittest.TestCase):
    def test_ff5_converts_provider_percent_to_decimal_daily(self):
        csv=sample(1002,",Mkt-RF,SMB,HML,RMW,CMA,RF","1.00,-0.50,0.20,0.10,0.15,0.01")
        rows,dates,start,end=mod.parse_daily_archive(
            archive(csv),("Mkt-RF","SMB","HML","RMW","CMA","RF"))
        self.assertEqual(dates,1002)
        self.assertEqual(len(rows),6*1002)
        self.assertEqual(rows[0][1],"FF_US_MKT_RF")
        self.assertAlmostEqual(rows[0][2],0.01)
        self.assertAlmostEqual(rows[1][2],-.005)
        self.assertEqual(start,date(2010,1,1))
        self.assertEqual(end,date(2012,9,28))

    def test_momentum_sentinel_is_missing_not_zero(self):
        from datetime import timedelta
        first=date(2019,1,1)
        ls=["Kenneth French research returns",",Mom"]
        for i in range(1005):
            d=first+timedelta(days=i)
            value="-99.99" if i==11 else "2.50"
            ls.append(d.strftime("%Y%m%d")+","+value)
        ls.extend(["","196307, 0.4"])
        rows,days,_,_=mod.parse_daily_archive(archive("\n".join(ls)),("Mom",))
        self.assertEqual(days,1005)
        self.assertEqual(len(rows),1004)
        self.assertAlmostEqual(rows[0][2],.025)

    def test_monthly_or_mismatched_file_is_refused(self):
        with self.assertRaises(ValueError):
            mod.parse_daily_archive(
                archive("Date,Mkt-RF,SMB,HML,RMW,CMA,RF\n202601,1,2,3,4,5,6"),
                ("Mkt-RF","SMB","HML","RMW","CMA","RF"))

    def test_oversize_or_multiple_csv_members_rejected(self):
        a=io.BytesIO()
        with zipfile.ZipFile(a,"w") as z:
            z.writestr("a.csv","x")
            z.writestr("b.csv","x")
        with self.assertRaises(ValueError):
            mod.parse_daily_archive(a.getvalue(),("Mom",))

    def test_only_research_origin_and_no_approval(self):
        src=PATH.read_text()
        for s in (
            "LAB_ALLOW_FRENCH_INTERNAL_RESEARCH",
            "EX_POST_RESEARCH_SNAPSHOT_NOT_PIT_OR_LICENSED",
            "FALSE,FALSE,FALSE,FALSE",
            "licensed_for_distribution",
            "historical_point_in_time_verified",
            "source_zip_sha256",
            "first_retrieved_at",
            "redistribution_rights_verified",
        ):
            self.assertIn(s,src)


if __name__=="__main__":
    unittest.main()
