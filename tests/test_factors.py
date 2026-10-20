"""Institutional-review regression fixtures for qualitative Factors mapping.

No MotherDuck, market prices, coefficient estimation or third-party packages.
Run with: python -m unittest discover -s tests -p 'test_factors.py' -v
"""
import json
import unittest
from unittest.mock import patch
from pathlib import Path

from factors import (
    CATALOG, RULE_VERSION, catalog, context, factor_coverage, factor_index,
    list_factors, map_question,
)

ROOT = Path(__file__).resolve().parents[1]

TW = {"id": "wd:Q865", "name": "Taiwan", "entity_type": "country"}
CN = {"id": "wd:Q148", "name": "China", "entity_type": "country"}
US = {"id": "wd:Q30", "name": "United States", "entity_type": "country"}

def mapped(title, action=None, entities=(), qid="q:fixture"):
    return map_question({"id": qid, "name": title}, list(entities), action)

def keys(output, collection="factors"):
    return {x["factor_id"] for x in output[collection]}


class FactorCatalogTests(unittest.TestCase):
    def test_catalog_is_comprehensive_and_unique(self):
        data = catalog()
        self.assertGreaterEqual(len(data["factors"]), 100)
        self.assertEqual(len(data["factors"]), len(factor_index()))
        for f in data["factors"]:
            self.assertTrue(f["model"])
            self.assertTrue(f["definition"])
            self.assertTrue(f["reference"].startswith("https://"))

    def test_fama_french_styles_and_cross_asset_families_present(self):
        ids = factor_index()
        for key in ("MKT_RF", "SMB", "HML", "RMW", "CMA"):
            self.assertIn("FF5.US." + key, ids)
        for name in ("STYLE.US.UMD", "STYLE.GLOBAL.QUALITY",
                     "XASSET.CARRY", "XASSET.TREND", "EQUITY.COUNTRY.TW",
                     "EQUITY.INDUSTRY.SEMICONDUCTORS", "RATES.US_10Y",
                     "CREDIT.US_HY", "FX.USD_TWD", "COMMODITY.BRENT",
                     "INFLATION.US_5Y_BE", "VOL.US_EQUITY_VOL",
                     "LIQUIDITY.USD_FUNDING"):
            self.assertIn(name, ids)

    def test_model_specific_factor_identities_remain_distinct(self):
        a = factor_index()["FF5.US.HML"]
        b = factor_index()["STYLE.GLOBAL.GROWTH"]
        self.assertNotEqual(a["model"], b["model"])
        self.assertNotEqual(a["id"], b["id"])

    def test_no_numerical_risk_fields_in_factor_catalog(self):
        for f in catalog()["factors"]:
            self.assertFalse(set(f) & {"beta", "weight", "coefficient", "loading", "sign"})

    def test_catalog_filters_work(self):
        rows = list_factors(family="commodity", query="Brent")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "COMMODITY.BRENT")

    def test_rule_version_pinned(self):
        self.assertTrue(RULE_VERSION.startswith("2026-"))
        self.assertEqual(catalog()["schema_version"], 1)


class FactorMappingTests(unittest.TestCase):
    def test_taiwan_conflict_has_country_and_currency_links(self):
        r = mapped("Will China invade Taiwan by 2027?", "invade", [TW, CN])
        self.assertIn("EQUITY.COUNTRY.TW", keys(r))
        self.assertIn("FX.USD_TWD", keys(r))
        self.assertIn("EQUITY.COUNTRY.CN", keys(r))
        self.assertIn("FX.USD_CNH", keys(r))
        self.assertEqual(r["status"], "mapped")

    def test_semis_conditional_for_generic_taiwan_conflict(self):
        r = mapped("Will China invade Taiwan?", "invade", [TW, CN])
        self.assertNotIn("EQUITY.INDUSTRY.SEMICONDUCTORS", keys(r))
        self.assertIn("EQUITY.INDUSTRY.SEMICONDUCTORS", keys(r, "review_candidates"))

    def test_semis_mapped_when_explicit_and_eligible(self):
        r = mapped("Will China ban semiconductor exports?", "ban", [CN])
        self.assertIn("EQUITY.INDUSTRY.SEMICONDUCTORS", keys(r))
        self.assertNotIn("EQUITY.INDUSTRY.SEMICONDUCTORS", keys(r, "review_candidates"))

    def test_hormuz_blockade_has_freight_and_oil(self):
        r = mapped("Will the Strait of Hormuz close to ships?", "close")
        self.assertIn("COMMODITY.FREIGHT", keys(r))
        self.assertIn("EQUITY.INDUSTRY.SHIPPING", keys(r))
        self.assertIn("COMMODITY.BRENT", keys(r))

    def test_generic_blockade_does_not_infer_oil(self):
        r = mapped("Will a blockade be ordered?", "blockade")
        self.assertNotIn("COMMODITY.BRENT", keys(r))
        self.assertNotIn("COMMODITY.FREIGHT", keys(r))

    def test_brent_threshold_maps_direct_observable_without_geopolitical_parser(self):
        r = mapped("Will Brent crude oil trade above $100 in December?")
        self.assertIn("COMMODITY.BRENT", keys(r))
        self.assertIn("direct_factor_outcome", r["mechanisms"])

    def test_explicit_fx_threshold_is_factor_observable(self):
        r = mapped("Will USD/TWD close above 33 before December?")
        self.assertIn("FX.USD_TWD", keys(r))
        self.assertNotIn("EQUITY.COUNTRY.TW", keys(r))

    def test_ten_year_yield_threshold_is_factor_observable(self):
        r = mapped("Will the US 10-year Treasury yield exceed 5%?")
        self.assertIn("RATES.US_10Y", keys(r))

    def test_direct_vix_threshold_maps_without_spurious_review_duplicate(self):
        r = mapped("Will VIX close above 30?")
        self.assertIn("VOL.US_EQUITY_VOL", keys(r))
        self.assertNotIn("VOL.US_EQUITY_VOL", keys(r, "review_candidates"))

    def test_direct_breakeven_threshold_bypasses_cpi_review_gate(self):
        r = mapped("Will the US 5-year breakeven exceed 3%?")
        self.assertIn("INFLATION.US_5Y_BE", keys(r))
        self.assertNotIn("INFLATION.US_5Y_BE", keys(r, "review_candidates"))

    def test_incidental_benchmark_name_without_threshold_does_not_create_link(self):
        r = mapped("Will a leader discuss Brent oil?")
        self.assertNotIn("COMMODITY.BRENT", keys(r))
        self.assertNotIn("FX.USD_TWD", keys(r))

    def test_oil_sanctions_connect_directly_to_oil(self):
        r = mapped("Will Iran sanction oil exports?", "sanction")
        self.assertIn("COMMODITY.BRENT", keys(r))
        self.assertIn("EQUITY.INDUSTRY.ENERGY", keys(r))

    def test_generic_sanctions_do_not_infer_oil(self):
        r = mapped("Will sanctions be imposed on Iran?", "sanction")
        self.assertNotIn("COMMODITY.BRENT", keys(r))
        self.assertIn("EQUITY.COUNTRY.IR", keys(r))

    def test_natural_gas_factors_require_explicit_commodity(self):
        a = mapped("Will Russian natural gas exports be banned?", "ban")
        b = mapped("Will Russia ban an opposition party?", "ban")
        self.assertIn("COMMODITY.NATGAS", keys(a))
        self.assertNotIn("COMMODITY.NATGAS", keys(b))

    def test_gas_lng_only_if_named(self):
        a = mapped("Will Asia LNG exports be banned?", "ban")
        self.assertIn("COMMODITY.LNG_ASIA", keys(a))

    def test_wheat_and_copper_get_their_own_factors(self):
        self.assertIn("COMMODITY.WHEAT",
            keys(mapped("Will wheat shipments be blocked?", "blockade")))
        self.assertIn("COMMODITY.COPPER",
            keys(mapped("Will copper exports be banned?", "ban")))

    def test_fed_rate_decision_maps_rate_factors_not_fama(self):
        r = mapped("Will the Federal Reserve cut interest rates?", "cut")
        self.assertIn("RATES.US_POLICY", keys(r))
        self.assertIn("RATES.US_2Y", keys(r))
        self.assertNotIn("FF5.US.HML", keys(r))
        self.assertNotIn("FF5.US.SMB", keys(r))

    def test_ecb_and_boj_have_separate_factors(self):
        r1 = mapped("Will the ECB raise its interest rate?", "raise")
        r2 = mapped("Will the Bank of Japan cut policy rates?", "cut")
        self.assertIn("RATES.ECB_POLICY", keys(r1))
        self.assertNotIn("RATES.US_POLICY", keys(r1))
        self.assertIn("RATES.BOJ_POLICY", keys(r2))

    def test_cpi_does_not_equal_traded_inflation_expectations(self):
        r = mapped("Will US CPI inflation rise?")
        self.assertNotIn("INFLATION.US_5Y_BE", keys(r))
        self.assertIn("INFLATION.US_5Y_BE", keys(r, "review_candidates"))

    def test_style_factors_never_auto_assigned_for_invasion(self):
        r = mapped("Will China invade Taiwan?", "invade", [TW, CN])
        self.assertFalse(any(f.startswith("FF5.") or f.startswith("STYLE.")
            for f in keys(r)))

    def test_explicit_hml_factor_gets_review_not_unearned_beta(self):
        r = mapped("Will the HML factor return beat the equity market this month?")
        self.assertIn("FF5.US.HML", keys(r, "review_candidates"))
        self.assertNotIn("FF5.US.HML", keys(r))

    def test_generic_momentum_word_is_review_candidate_only(self):
        r = mapped("Will stock market momentum persist?")
        self.assertIn("STYLE.US.UMD", keys(r, "review_candidates"))
        self.assertNotIn("STYLE.US.UMD", keys(r))

    def test_generic_quality_and_defensive_style_mentions_are_review_only(self):
        r = mapped("Will high-quality stocks outperform low-volatility defensive stocks?")
        self.assertIn("STYLE.GLOBAL.QUALITY", keys(r, "review_candidates"))
        self.assertIn("STYLE.GLOBAL.LOW_VOL", keys(r, "review_candidates"))
        self.assertNotIn("STYLE.GLOBAL.QUALITY", keys(r))
        self.assertNotIn("STYLE.GLOBAL.LOW_VOL", keys(r))

    def test_cross_asset_carry_explicit_factor_still_requires_review(self):
        r = mapped("Will the cross-asset carry factor outperform this year?")
        self.assertIn("XASSET.CARRY", keys(r, "review_candidates"))
        self.assertNotIn("XASSET.CARRY", keys(r))

    def test_diplomatic_visit_no_automatic_country_factor(self):
        r = mapped("Will China visit Taiwan?", "visit", [TW, CN])
        self.assertNotIn("EQUITY.COUNTRY.TW", keys(r))
        self.assertNotIn("FX.USD_TWD", keys(r))

    def test_unrelated_question_abstains_without_inventing_links(self):
        r = mapped("Will a leader appear in public?", "appear")
        self.assertEqual(r["status"], "unmapped")
        self.assertEqual(r["factors"], [])
        self.assertEqual(r["review_candidates"], [])
        self.assertTrue(r["unmapped_reason"])

    def test_links_carry_auditable_explanations_and_no_numbers(self):
        r = mapped("Will China invade Taiwan?", "invade", [TW, CN])
        for link in r["factors"] + r["review_candidates"]:
            self.assertEqual(link["rule_version"], RULE_VERSION)
            self.assertTrue(link["rule_id"])
            self.assertTrue(link["evidence"])
            self.assertTrue(link["reason"])
            self.assertTrue(link["mechanism"])
            self.assertEqual(link["provenance"], "version_controlled_deterministic_rule")
            self.assertFalse(set(link) & {"weight", "beta", "coefficient", "loading", "sign", "score"})
            self.assertNotIn("prob", link)
        self.assertEqual(r["time_travel_caveat"][:13], "Current versi")

    def test_mapping_deterministic_ignores_prices_and_probabilities(self):
        common = {"id": "q:123", "name": "Will China invade Taiwan?"}
        x = map_question(common | {"prob": 0.03}, [TW, CN], "invade")
        y = map_question(common | {"prob": 0.96, "impact": -4.7}, [CN, TW], "invade")
        self.assertEqual(x["factors"], y["factors"])
        self.assertEqual(x["review_candidates"], y["review_candidates"])

    def test_title_parser_fallback_when_no_graph_action(self):
        r = mapped("Will China invade Taiwan?", None, [TW, CN])
        self.assertEqual(r["action"], "invade")
        self.assertIn("EQUITY.COUNTRY.TW", keys(r))

    def test_country_entity_link_used_when_question_omits_name(self):
        r = mapped("Will the island be blockaded?", "blockade", [TW])
        self.assertIn("EQUITY.COUNTRY.TW", keys(r))
        self.assertIn("FX.USD_TWD", keys(r))

    def test_deterministic_rule_sort_order(self):
        r = mapped("Will China blockade Taiwan?", "blockade", [TW, CN])
        self.assertEqual([x["factor_id"] for x in r["factors"]],
                         sorted(keys(r)))

    def test_proposition_inherits_question_mapping_without_extra_factor_claims(self):
        q = {"id": "q:xyz", "name": "Will China invade Taiwan?"}
        a = map_question(q, [TW,CN], "invade")
        b = map_question(q, [TW,CN], "invade", "prop:2027")
        self.assertEqual(a["factors"], b["factors"])
        self.assertEqual(b["proposition_id"], "prop:2027")

    def test_reverse_lookup_maps_only_accepted_by_default(self):
        qs = [
            ({"id": "q:taiwan", "name": "Will China invade Taiwan?"}, [TW, CN], "invade"),
            ({"id": "q:meeting", "name": "Will China meet Taiwan leaders?"}, [TW,CN], "meet"),
        ]
        hits = factor_coverage("EQUITY.COUNTRY.TW", qs)
        self.assertEqual([x["question_id"] for x in hits], ["q:taiwan"])

    def test_reverse_lookup_includes_review_when_explicitly_requested(self):
        qs = [({"id": "q:taiwan", "name": "Will China invade Taiwan?"}, [TW,CN], "invade")]
        self.assertEqual(factor_coverage("EQUITY.INDUSTRY.SEMICONDUCTORS", qs), [])
        hits = factor_coverage("EQUITY.INDUSTRY.SEMICONDUCTORS", qs, True)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["status"], "review_required")

    def test_unknown_factor_in_reverse_lookup_raises_key_error(self):
        with self.assertRaises(KeyError):
            factor_coverage("FACTOR.DOES_NOT_EXIST", [])

    def test_json_serializable_and_no_api_secrets(self):
        r = mapped("Will China invade Taiwan?", "invade", [TW,CN])
        payload = json.dumps(r)
        self.assertNotIn("MOTHERDUCK_TOKEN", payload)
        self.assertNotIn("X-API-Key", payload)


if __name__ == "__main__":
    unittest.main()
