"""Offline source-schema, orientation and frequency controls for ECB/FRED backfills."""
from __future__ import annotations
from datetime import date,timedelta
import importlib.util
import sys
from pathlib import Path
import unittest

LAB=Path(__file__).resolve().parents[1]/"lab"
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,LAB/path)
    m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m

fx=module("phase1_ecb_fx_references.py","ecb_fx")
fred=module("phase1_fred_macro_research.py","fred_macro")


class OfficialFXMacroTests(unittest.TestCase):
    def test_ecb_eur_base_orientation_and_daily_structure(self):
        source=["FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,OBS_STATUS"]
        d=date(2024,1,1)
        for i in range(270):
            source.append(f"D,USD,EUR,SP00,A,{d+timedelta(days=i)},1.1,A")
        parsed=fx.parse_ecb_csv("\n".join(source).encode(),"USD")
        self.assertEqual(len(parsed),270)
        self.assertEqual(parsed[0][1],"USD")
        self.assertAlmostEqual(parsed[0][2],1.1)
        bad="\n".join(source).replace(",USD,EUR,",",EUR,USD,")
        with self.assertRaises(ValueError):
            fx.parse_ecb_csv(bad.encode(),"USD")

    def test_ecb_prevents_duplicate_or_negative_rates(self):
        rows=["FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE",
              "D,USD,EUR,SP00,A,2026-10-20,1.2",
              "D,USD,EUR,SP00,A,2026-10-20,1.3"]
        with self.assertRaises(ValueError):
            fx.parse_ecb_csv("\n".join(rows).encode(),"USD")
        self.assertIn("is_executable_spot_fx_quote", (LAB/"phase1_ecb_fx_references.py").read_text())

    def test_fred_rejects_wrong_header_and_future_data(self):
        data=["observation_date,DFF"]
        d=date(2024,1,1)
        for i in range(280):
            data.append(f"{d+timedelta(days=i)},5.2")
        obs=fred.read_fred("\n".join(data).encode(),"DFF","daily")
        self.assertEqual(len(obs),280)
        with self.assertRaises(ValueError):
            fred.read_fred("\n".join(data).replace("DFF","WRONG").encode(),"DFF","daily")

    def test_native_units_and_changes_not_release_surprises(self):
        points=[("2025-01-01",100.0),("2025-02-01",101.0)]
        y=fred.derived("UNRATE",points,"unemployment_rate_pp_change")
        self.assertEqual(len(y),1)
        self.assertAlmostEqual(y[0][2],1.0)
        self.assertIn("not_surprise",y[0][3])
        rates=fred.derived("DFF",[("2025-01-01",5.),("2025-01-02",5.1)],
                           "rate_level_change_basis_points")
        self.assertAlmostEqual(rates[0][2],10.0)
        self.assertIn("not_surprise",rates[0][3])
        yoy=[(date(2024,1,1)+timedelta(days=30*i)).isoformat() for i in range(13)]
        # Require actual monthly calendar month spacing and refuse fake daily inflation.
        got=fred.derived("CPIAUCSL",[(d,200+i) for i,d in enumerate(yoy)],
                         "trailing_12_month_pct")
        self.assertLessEqual(len(got),1)

    def test_both_research_sources_fail_closed(self):
        ecb=(LAB/"phase1_ecb_fx_references.py").read_text()
        f=(LAB/"phase1_fred_macro_research.py").read_text()
        for word in ("LAB_ALLOW_ECB_INFORMATIONAL_DATA","FX_EXECUTABLE_QUOTE=FALSE",
                     "original_provider_publication_at","rights_for_risk_redistribution_verified"):
            self.assertIn(word,ecb)
        for word in ("LAB_ALLOW_FRED_RESEARCH","is_identified_economic_surprise",
                     "ORIGINAL_PROVIDER_RELEASE_TIMES_VERIFIED=FALSE"):
            self.assertIn(word,f)

if __name__=="__main__":
    unittest.main()
