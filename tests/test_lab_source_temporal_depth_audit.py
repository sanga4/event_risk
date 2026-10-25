"""Independent source coverage, PIT-rights and research depth tests; no credentials."""
from datetime import date,datetime,timezone
import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"lab"/"phase1_source_temporal_depth_audit.py"
spec=importlib.util.spec_from_file_location("depth_audit",SCRIPT)
depth=importlib.util.module_from_spec(spec);spec.loader.exec_module(depth)

DOMAINS=("commodities_futures_rolls","ecb_eur_fx_reference","event_evidence_archive",
 "fred_macro_economic","historical_market_snapshots","independent_tradeable_fx",
 "licensed_credit_spreads","macro_release_consensus","nyfed_sofr_effr_reference",
 "options_volatility","portfolio_positions","security_corporate_actions",
 "treasury_par_yields","us_equity_style_factors","usd_security_prices",
 "venue_prospective_receipts")

def fixture():
    counts={"ecb_eur_fx_reference":39088,"historical_market_snapshots":11101967,
            "nyfed_sofr_effr_reference":500,"treasury_par_yields":12656,
            "us_equity_style_factors":121598,"usd_security_prices":107157,
            "venue_prospective_receipts":39890}
    first=date(2025,1,1);last=date(2026,10,24)
    domains=[(name,n>0,n,first if n else None,last if n else None,
            datetime(2026,10,25,tzinfo=timezone.utc) if n else None,
            False,False,False,"daily","Independent original publication and license")
            for name in DOMAINS for n in [counts.get(name,0)]]
    rate=[("EFFR",250,250,date(2025,10,24),date(2026,10,22),0),
          ("SOFR",250,250,date(2025,10,22),date(2026,10,22),0)]
    return ("inventory",domains,(39890,10,3,0),rate,
            (718020,3,0,0),(233442,5,0))

class SourceDepthTests(unittest.TestCase):
    def test_empty_domains_not_conflated_with_large_research_counts(self):
        out=depth.assess(*fixture())
        self.assertEqual(out["families"],16)
        self.assertEqual(out["loaded"],7)
        self.assertEqual(out["missing"],9)
        self.assertEqual(out["venue_rows"],39890)
        self.assertEqual(out["capture_days"],3)
        self.assertEqual(out["paired_event_days"],5)
        self.assertFalse(out["nyfed_history_sufficient"])

    def test_history_threshold_does_not_grant_rights(self):
        p=list(fixture())
        p[3]=[("EFFR",1600,1600,date(2018,4,2),date(2026,10,22),0),
              ("SOFR",1600,1600,date(2018,4,2),date(2026,10,22),0)]
        p[1]=[(*r[:2],3200,*r[3:]) if r[0]=="nyfed_sofr_effr_reference" else r
              for r in p[1]]
        result=depth.assess(*p)
        self.assertTrue(result["nyfed_history_sufficient"])
        self.assertTrue(all(x[-3:]==(False,False,False) for x in result["details"]))

    def test_insufficient_provider_depth_is_reported(self):
        out=depth.assess(*fixture())
        states={r[0]:r[6] for r in out["details"]}
        self.assertIn("HISTORY_INCOMPLETE",states["nyfed_sofr_effr_reference"])
        self.assertIn("CAPTURE_DAYS_BELOW",states["venue_prospective_receipts"])
        self.assertTrue(states["fred_macro_economic"].startswith("MISSING_SOURCE"))

    def test_missing_history_date_metadata_remains_visible(self):
        p=list(fixture());a=list(p[1])
        i=DOMAINS.index("historical_market_snapshots")
        r=list(a[i]);r[3]=r[4]=None;a[i]=tuple(r);p[1]=a
        out=depth.assess(*p)
        states={r[0]:r[6] for r in out["details"]}
        self.assertIn("OBSERVATION_DATES_MISSING",states["historical_market_snapshots"])

    def test_any_incorrect_venue_grid_model_approval_fails_closed(self):
        for index,col in ((2,3),(4,2),(4,3),(5,2)):
            p=list(fixture());item=list(p[index]);item[col]=1;p[index]=tuple(item)
            with self.subTest(index=index,col=col),self.assertRaises(ValueError):
                depth.assess(*p)

    def test_missing_official_rates_or_false_license_rejected(self):
        p=list(fixture());p[3]=p[3][:1]
        with self.assertRaisesRegex(ValueError,"NYFed"):
            depth.assess(*p)
        p=list(fixture());r=list(p[3][0]);r[-1]=1;p[3][0]=tuple(r)
        with self.assertRaisesRegex(ValueError,"rate"):
            depth.assess(*p)

    def test_source_native_inventory_totals_must_match(self):
        for name,idx,val in (("nyfed_sofr_effr_reference",2,501),
                             ("venue_prospective_receipts",2,39889)):
            p=list(fixture());a=list(p[1]);pos=DOMAINS.index(name)
            row=list(a[pos]);row[idx]=val;a[pos]=tuple(row);p[1]=a
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,"count disagrees"):
                depth.assess(*p)

    def test_source_family_duplicate_and_future_reversal_rejected(self):
        p=list(fixture());p[1][-1]=p[1][0]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            depth.assess(*p)
        p=list(fixture());a=list(p[1]);j=DOMAINS.index("treasury_par_yields")
        row=list(a[j]);row[3],row[4]=row[4],row[3];a[j]=tuple(row);p[1]=a
        with self.assertRaisesRegex(ValueError,"Malformed"):
            depth.assess(*p)

    def test_asserted_external_approval_is_not_automatically_certified(self):
        p=list(fixture());a=list(p[1]);j=DOMAINS.index("ecb_eur_fx_reference")
        row=list(a[j]);row[7]=True;a[j]=tuple(row);p[1]=a
        o=depth.assess(*p)
        relevant=next(x for x in o["details"] if x[0]=="ecb_eur_fx_reference")
        self.assertIn("HUMAN_EVIDENCE_REVIEW",relevant[6])
        self.assertEqual(relevant[-3:],(False,False,False))

if __name__=="__main__":
    unittest.main()
