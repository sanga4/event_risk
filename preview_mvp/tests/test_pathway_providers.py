import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app, pathways, market_providers, factor_universe

class PathwayGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=pathways.graph_paths(app.public_graph())
    def test_full_five_stage_demonstration_is_connected(self):
        g=self.g
        nodes={x["id"]:x for x in g["nodes"]}
        edges={(e["src"],e["dst"]):e for e in g["edges"]}
        a=pathways.DEMO_CONTRACT
        b=pathways.DEMO_EVENT
        c=pathways.DEMO_ENTITY
        d="security:EQIX"
        e="factor:PROPOSED.REAL_ESTATE.DC_REIT"
        for node in (a,b,c,d,e):self.assertIn(node,nodes)
        for pair in ((a,b),(b,c),(c,d),(d,e)):
            self.assertIn(pair,edges)
            self.assertEqual(edges[pair]["review_status"],"RESEARCH_ONLY_NOT_APPROVED")
            self.assertFalse(edges[pair]["causal_effect_estimated"])
        self.assertEqual(nodes[a]["provider"],"ILLUSTRATIVE_ONLY_NOT_KALSHI_OR_POLYMARKET")
        self.assertFalse(nodes[e]["historical_series_validated"])
        self.assertEqual(g["contract_count_verified"],0)
    def test_original_public_catalog_untouched(self):
        raw=app.public_graph()
        self.assertEqual(raw["mode"],"PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE")
        self.assertFalse(any(n["type"]=="contract" for n in raw["nodes"]))
        original_ids={n["id"] for n in raw["nodes"]}
        revised_ids={n["id"] for n in self.g["nodes"]}
        self.assertTrue(original_ids.issubset(revised_ids))
        self.assertEqual(len(revised_ids),len(self.g["nodes"]))
        self.assertTrue(all(e["src"] in revised_ids and e["dst"] in revised_ids for e in self.g["edges"]))
        self.assertEqual(len(pathways.FACTOR_PROPOSALS),16)
    def test_no_real_contract_or_priced_market_claims(self):
        self.assertEqual(self.g["contract_demo_count"],1)
        demo=[n for n in self.g["nodes"] if n["type"]=="contract"]
        self.assertEqual(len(demo),1)
        self.assertIn("SYNTHETIC",demo[0]["review_status"])
        self.assertFalse(any("yes_bid" in node or "implied_probability" in node for node in demo))

class ExpandedFactorUniverseTests(unittest.TestCase):
    def test_cross_asset_taxonomy_is_proposed_only(self):
        factors=factor_universe.factor_proposals()
        ids=[f["factor_id"] for f in factors]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(ids),140)
        families={f["family"] for f in factors}
        for fam in ("electricity","credit","rates","fx","volatility","macro_growth",
                    "funding","supply_chain","climate_water","semiconductors"):
            self.assertIn(fam,families)
        self.assertTrue(all(f["validated_observation_series"] is False for f in factors))
        self.assertTrue(all(f["market_data_rights_verified"] is False for f in factors))

class ProviderCatalogTests(unittest.TestCase):
    def test_kalshi_cursor_and_stable_native_ids(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            if "cursor=" in url:return {"events":[{"event_ticker":"KXDCCAPEX-27",
               "markets":[{"ticker":"KXDCCAPEX-27-B","title":"Data center second outcome","status":"open"}]}],"cursor":""}
            return {"events":[{"event_ticker":"KXDCCAPEX-27",
              "markets":[{"ticker":"KXDCCAPEX-27-A","title":"Data center first outcome","status":"open"}]}],
              "cursor":"page2"}
        items=list(market_providers.catalog_pages("kalshi",fetch,max_pages=4))
        self.assertEqual(len(items),2)
        self.assertIn("cursor=page2",urls[1])
        self.assertEqual(items[0]["id"],"contract:kalshi:KXDCCAPEX-27-A")
        self.assertIsNone(items[0]["canonical_real_world_event_id"])
        self.assertTrue(items[0]["licensing_review_required"])
    def test_polymarket_offset_and_duplicate_id_dedup(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            if "offset=0" in url:
                return [{"id":"299","slug":"sample-center-demand",
                  "markets":[{"id":"101","question":"Will load increase?","active":True,"closed":False}]}]
            return []
        records=list(market_providers.catalog_pages("polymarket",fetch,max_pages=5,page_size=1))
        self.assertEqual(len(records),1)
        self.assertIn("offset=1",urls[1])
        self.assertEqual(records[0]["id"],"contract:polymarket:101")
        self.assertEqual(records[0]["native_event_id"],"299")
        self.assertTrue(records[0]["price_not_fetched"])
    def test_coverage_not_falsely_complete(self):
        record=market_providers.contract_record("kalshi",
             {"ticker":"KXTEST-1","event_ticker":"KXTEST","title":"Test","status":"settled"})
        m=market_providers.coverage_manifest("kalshi",[record,record],"2026-10-27T00:00:00Z")
        self.assertEqual(m["distinct_contracts"],1)
        self.assertFalse(m["all_provider_contracts_included"])
        self.assertFalse(m["rights_approved_for_redisplay"])
    def test_provider_limits(self):
        with self.assertRaises(ValueError):
            list(market_providers.catalog_pages("polymarket",lambda u:[],max_pages=500))
