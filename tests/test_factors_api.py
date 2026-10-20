"""FastAPI Factors routes under a pure in-memory graph, without MotherDuck.

Requires the existing requirements.txt and pinned httpx test dependency. This
checks actual HTTP routing, JSON serialization, API-key protection and bitemporal
parameter propagation, without starting database connections.
"""
import asyncio
import unittest
from datetime import datetime
from unittest.mock import patch

import httpx
import api

TW = "wd:Q865"
CN = "wd:Q148"
Q = "q:taiwan"
P = "prop:2027"


class FakeGraph:
    def __init__(self):
        self.nodes = {
            Q: dict(id=Q, name="Will China invade Taiwan?", type="question",
                    attrs={"kind":"deadlines","n_rungs":2,"venues":["kalshi"]},valid_from=None),
            P: dict(id=P, name="Will China invade Taiwan by 2027?",type="proposition",
                    attrs={"n_markets":1,"venues":["kalshi"]},valid_from=None),
            TW: dict(id=TW,name="Taiwan",type="entity",
                     attrs={"entity_type":"country"},valid_from=None),
            CN: dict(id=CN,name="China",type="entity",
                     attrs={"entity_type":"country"},valid_from=None),
        }
        self.out = {id: [] for id in self.nodes}
        self.inc = {id: [] for id in self.nodes}
        for edge in [
            dict(src=Q,dst=TW,type="involves",attrs={"action":"invade","role":"target"},
                 weight=.8,confidence=.8,sign=-1,provenance="wikipedia_link",note=None),
            dict(src=Q,dst=CN,type="involves",attrs={"action":"invade","role":"actor"},
                 weight=.4,confidence=.8,sign=-.6,provenance="wikipedia_link",note=None),
            dict(src=P,dst=Q,type="rung_of",attrs={},weight=1,
                 confidence=1,sign=None,provenance="rule",note=None),
        ]:
            self.out[edge["src"]].append(edge)
            self.inc[edge["dst"]].append(edge)

    def get(self,id,type):
        n = self.nodes.get(id)
        if not n or n["type"]!=type:
            raise api.HTTPException(404, "not found")
        return n

    def ref(self,id):
        n=self.nodes[id]
        return dict(id=id,name=n["name"],type=n["type"])

    def question_of(self,id):
        return Q if id==P else None

    def rungs(self,id):
        return [(P, ["2026-01-01", "2027-12-31"],None)]

    def markets(self,id):
        return []


class FactorsAPITests(unittest.TestCase):
    def setUp(self):
        self.graph=FakeGraph()
        api.app.dependency_overrides[api.db] = lambda: None

    def tearDown(self):
        api.app.dependency_overrides.clear()

    def get(self,path,headers=None):
        async def request():
            transport=httpx.ASGITransport(app=api.app)
            async with httpx.AsyncClient(transport=transport,
                                         base_url="http://factor.test") as client:
                return await client.get(path,headers=headers)
        with patch.object(api,"graph",return_value=self.graph):
            return asyncio.run(request())

    def test_factor_catalog_http_has_no_database_or_exposure_fields(self):
        with patch.object(api,"connection",side_effect=AssertionError("Factors catalog queried the database")):
            res=self.get("/factors?family=equity_style")
        self.assertEqual(res.status_code,200,res.text)
        data=res.json()
        self.assertGreater(len(data["factors"]),10)
        self.assertTrue(all(x["family"]=="equity_style" for x in data["factors"]))
        self.assertTrue(all("beta" not in x and "weight" not in x for x in data["factors"]))

    def test_factor_catalog_query_filters(self):
        res=self.get("/factors?q=HML")
        self.assertEqual(res.status_code,200,res.text)
        self.assertIn("FF5.US.HML",{x["id"] for x in res.json()["factors"]})

    def test_factor_detail_and_404(self):
        ok=self.get("/factors/FF5.US.HML")
        self.assertEqual(ok.status_code,200,ok.text)
        self.assertEqual(ok.json()["model"],"Fama–French research portfolios")
        self.assertEqual(self.get("/factors/NOT_REAL").status_code,404)

    def test_question_factor_mapping_http_with_exact_names_and_trace(self):
        res=self.get("/questions/q:taiwan/factors")
        self.assertEqual(res.status_code,200,res.text)
        body=res.json()
        ids={x["factor_id"] for x in body["factors"]}
        self.assertIn("EQUITY.COUNTRY.TW",ids)
        self.assertIn("FX.USD_TWD",ids)
        self.assertFalse(any(x.startswith("FF5.") for x in ids))
        self.assertEqual(body["question_id"],Q)
        self.assertTrue(all(x["evidence"] and x["rule_id"] for x in body["factors"]))
        self.assertNotIn("beta",body)
        self.assertNotIn("coefficient",body)

    def test_proposition_inherits_question_mapping_http(self):
        res=self.get("/propositions/prop:2027/factors")
        self.assertEqual(res.status_code,200,res.text)
        data=res.json()
        self.assertTrue(data["inherited_from_question"])
        self.assertEqual(data["question_id"],Q)
        self.assertEqual(data["proposition_id"],P)
        self.assertIn("EQUITY.COUNTRY.TW",{x["factor_id"] for x in data["factors"]})

    def test_invalid_question_and_proposition_http_are_404(self):
        self.assertEqual(self.get("/questions/q:missing/factors").status_code,404)
        self.assertEqual(self.get("/propositions/prop:missing/factors").status_code,404)

    def test_reverse_lookup_http_only_mapped_by_default(self):
        res=self.get("/factors/EQUITY.COUNTRY.TW/questions")
        self.assertEqual(res.status_code,200,res.text)
        result=res.json()
        self.assertEqual(result["count"],1)
        self.assertEqual(result["questions"][0]["question_id"],Q)
        self.assertEqual(result["questions"][0]["status"],"mapped")
        excluded=self.get("/factors/EQUITY.INDUSTRY.SEMICONDUCTORS/questions")
        self.assertEqual(excluded.json()["count"],0)
        included=self.get("/factors/EQUITY.INDUSTRY.SEMICONDUCTORS/questions?include_review=true")
        self.assertEqual(included.json()["count"],1)
        self.assertEqual(included.json()["questions"][0]["status"],"review_required")

    def test_reverse_lookup_limit_validated(self):
        self.assertEqual(self.get("/factors/EQUITY.COUNTRY.TW/questions?limit=0").status_code,422)
        self.assertEqual(self.get("/factors/UNKNOWN/questions").status_code,404)

    def test_as_of_and_known_as_of_are_returned(self):
        res=self.get("/questions/q:taiwan/factors?as_of=2026-09-01T00%3A00%3A00Z&known_as_of=2026-09-01T00%3A00%3A00Z")
        self.assertEqual(res.status_code,200,res.text)
        self.assertTrue(res.json()["as_of"].startswith("2026-09-01"))
        self.assertTrue(res.json()["known_as_of"].startswith("2026-09-01"))
        self.assertIn("Current versioned rules",res.json()["time_travel_caveat"])

    def test_security_boundary_requires_api_key_when_configured(self):
        with patch.object(api,"API_KEYS",{"very-secret"}):
            blocked=self.get("/factors")
            self.assertEqual(blocked.status_code,401)
            allowed=self.get("/factors",headers={"X-API-Key":"very-secret"})
            self.assertEqual(allowed.status_code,200)

    def test_existing_graph_unmodified_when_opt_in_is_false(self):
        with patch.object(api,"question_probs",return_value={Q:{
            "prob":.3,"change_24h":.01,"status":"live","volume_24h":150}}),\
             patch.object(api,"prop_probs",return_value={P:{
            "prob":.3,"change_24h":.01,"status":"live"}}):
            res=self.get("/graph/q:taiwan?depth=1&fanout=20")
        self.assertEqual(res.status_code,200,res.text)
        data=res.json()
        self.assertFalse(any(n["type"]=="factor" for n in data["nodes"]))
        self.assertFalse(any(e["type"]=="factor_link" for e in data["edges"]))

    def test_opt_in_graph_has_virtual_factor_nodes_without_weights(self):
        with patch.object(api,"question_probs",return_value={Q:{
            "prob":.3,"change_24h":.01,"status":"live","volume_24h":150}}),\
             patch.object(api,"prop_probs",return_value={P:{
            "prob":.3,"change_24h":.01,"status":"live"}}):
            res=self.get("/graph/q:taiwan?depth=1&fanout=20&include_factors=true")
        self.assertEqual(res.status_code,200,res.text)
        data=res.json()
        virtual=[n for n in data["nodes"] if n["type"]=="factor"]
        self.assertTrue(virtual)
        edges=[e for e in data["edges"] if e["type"]=="factor_link"]
        self.assertTrue(edges)
        for e in edges:
            self.assertFalse(set(e) & {"weight","confidence","sign","beta","coefficient"})
            self.assertTrue(e["rule_id"] and e["reason"])
            self.assertEqual(e["src"],Q)

    def test_unknown_graph_id_is_still_404(self):
        self.assertEqual(self.get("/graph/q:missing?include_factors=true").status_code,404)


if __name__=="__main__":
    unittest.main()
