"""No-database governance checks for source-controlled analyst factor decisions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import factors

TW={"id":"wd:Q865","name":"Taiwan","entity_type":"country"}
CN={"id":"wd:Q148","name":"China","entity_type":"country"}
Q={"id":"q:taiwan","name":"Will China invade Taiwan?"}
STAMP="2026-10-20T12:00:00Z"


def reviewed(decision,factor_id,proposition_id=None):
    entry=dict(id="DECISION-0001",question_id=Q["id"],factor_id=factor_id,
               decision=decision,mechanism="documented_case_review",
               rationale="Approved after independent review of event clauses and factor definition.",
               evidence="Research memo EXAMPLE-001 and applicable contract terms",
               reviewer="risk-reviewer-1",reviewed_at=STAMP)
    if proposition_id:
        entry["proposition_id"]=proposition_id
    return dict(schema_version=1,review_version="2026-10-20.review",
                entries=[entry])


def evaluate(decisions, proposition_id=None):
    with patch.object(factors,"overrides",return_value=decisions):
        return factors.map_question(Q,[TW,CN],"invade",proposition_id)


def ids(mapping,key):
    return {link["factor_id"] for link in mapping[key]}


class ReviewSemanticsTests(unittest.TestCase):
    def test_base_mapping_has_no_pretend_human_review(self):
        result=factors.map_question(Q,[TW,CN],"invade")
        self.assertEqual(result["applied_review_ids"],[])
        self.assertEqual(result["exclusions"],[])
        self.assertNotIn("reviewer",result["factors"][0])

    def test_approved_review_candidate_becomes_accepted_with_review_trace(self):
        r=evaluate(reviewed("approve","EQUITY.INDUSTRY.SEMICONDUCTORS"))
        self.assertIn("EQUITY.INDUSTRY.SEMICONDUCTORS",ids(r,"factors"))
        self.assertNotIn("EQUITY.INDUSTRY.SEMICONDUCTORS",ids(r,"review_candidates"))
        link=next(x for x in r["factors"] if x["factor_id"]=="EQUITY.INDUSTRY.SEMICONDUCTORS")
        self.assertEqual(link["provenance"],"source_controlled_analyst_review")
        self.assertEqual(link["reviewer"],"risk-reviewer-1")
        self.assertTrue(link["rule_id"].startswith("CURATED:"))
        self.assertFalse(set(link)&{"beta","coefficient","weight","sign","score"})

    def test_rejected_automatic_link_removed_with_audit(self):
        r=evaluate(reviewed("reject","FX.USD_TWD"))
        self.assertNotIn("FX.USD_TWD",ids(r,"factors"))
        self.assertEqual(r["exclusions"][0]["factor_id"],"FX.USD_TWD")
        self.assertEqual(r["exclusions"][0]["reviewer"],"risk-reviewer-1")

    def test_downgrade_mapped_link_to_review(self):
        r=evaluate(reviewed("review","EQUITY.COUNTRY.TW"))
        self.assertNotIn("EQUITY.COUNTRY.TW",ids(r,"factors"))
        self.assertIn("EQUITY.COUNTRY.TW",ids(r,"review_candidates"))

    def test_proposition_specific_override_not_applied_to_parent(self):
        data=reviewed("reject","FX.USD_TWD","prop:2027")
        parent=evaluate(data)
        child=evaluate(data,"prop:2027")
        other=evaluate(data,"prop:2028")
        self.assertIn("FX.USD_TWD",ids(parent,"factors"))
        self.assertNotIn("FX.USD_TWD",ids(child,"factors"))
        self.assertIn("FX.USD_TWD",ids(other,"factors"))

    def test_review_version_and_audit_ids_exposed(self):
        r=evaluate(reviewed("approve","EQUITY.INDUSTRY.SEMICONDUCTORS"))
        self.assertEqual(r["review_version"],"2026-10-20.review")
        self.assertEqual(r["applied_review_ids"],["DECISION-0001"])

    def test_empty_default_review_register(self):
        self.assertEqual(factors.overrides()["entries"],[])

    def test_review_file_validation_rejects_duplicates_unknown_factors_and_missing_evidence(self):
        for transform in (
            lambda e:[e,e],
            lambda e:[e|{"factor_id":"UNKNOWN.FACTOR"}],
            lambda e:[e|{"evidence":""}],
            lambda e:[e|{"reviewed_at":"2026-10-20"}],
            lambda e:[e|{"beta":2}],
            lambda e:[e|{"decision":"whatever"}],
        ):
            data=reviewed("approve","EQUITY.COUNTRY.TW")
            data["entries"]=transform(data["entries"][0])
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp)/"reviews.json"
                p.write_text(json.dumps(data),encoding="utf-8")
                factors.overrides.cache_clear()
                with patch.object(factors,"OVERRIDES",p):
                    with self.assertRaises((ValueError,TypeError)):
                        factors.overrides()
                factors.overrides.cache_clear()


if __name__ == "__main__":
    unittest.main()
