"""Deterministic, qualitative event-to-Factors mapping (no database access).

This layer is intentionally separate from the existing weighted security-exposure
graph. Factor links are Boolean, reviewable *relevance* hypotheses, not betas,
coefficients, return signs, investment signals, or risk contributions.

Input: a graph question's title, recognized action and linked entity references.
Output: established rule-based links, separate human-review candidates and
mechanism/evidence traces. Static rules are applied to a caller-selected graph
snapshot. Historical replay of a *mapping decision* requires pinning this
module and the catalog version; as_of alone only fixes the event graph.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from matching import find_action

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "seeds" / "factors.json"
OVERRIDES = ROOT / "seeds" / "factor_overrides.json"
RULE_VERSION = "2026-10-20.1"
MAPPING_BASIS = "Boolean contextual rule with review gate; no numeric exposure"

# Country names must refer to the country itself, not arbitrarily to a company
# with a similar token. Prefer typed graph entities; use explicit title mentions.
COUNTRIES = {
    "TW": {"ids": {"wd:Q865"}, "terms": ("taiwan", "taiwanese")},
    "CN": {"ids": {"wd:Q148"}, "terms": ("china", "chinese", "prc", "mainland china")},
    "US": {"ids": {"wd:Q30"}, "terms": ("united states", "u.s.", "u.s.a.", "american")},
    "JP": {"ids": {"wd:Q17"}, "terms": ("japan", "japanese")},
    "KR": {"ids": {"wd:Q884"}, "terms": ("south korea", "korean")},
    "IN": {"ids": {"wd:Q668"}, "terms": ("india", "indian")},
    "GB": {"ids": {"wd:Q145"}, "terms": ("united kingdom", "britain", "british")},
    "RU": {"ids": {"wd:Q159"}, "terms": ("russia", "russian")},
    "IR": {"ids": {"wd:Q794"}, "terms": ("iran", "iranian")},
    "EU": {"ids": {}, "terms": ("european union", "euro area", "eu member states")},
}
COUNTRY_FX = {"TW": "FX.USD_TWD", "CN": "FX.USD_CNH",
              "JP": "FX.USD_JPY", "KR": "FX.USD_KRW",
              "IN": "FX.USD_INR", "GB": "FX.USD_GBP",
              "EU": "FX.EUR_USD"}
CONFLICT = frozenset({"invade", "blockade", "military_clash", "missile_launch",
    "strike", "capture", "enter", "annex", "deploy", "coup", "regime_fall"})
TRADE = frozenset({"tariff_change", "tariff_rate", "ban", "unban", "trade_agreement"})
SANCTION = frozenset({"sanction", "sanction_relief", "list_add", "list_remove"})
SHIPPING = frozenset({"blockade", "close", "reopen", "transit"})
UNREST = frozenset({"coup", "regime_fall", "leave_office", "impeach",
    "election_win", "vote", "purge"})
SUPPLY_ACTIONS = CONFLICT | TRADE | SANCTION | SHIPPING | {"outage"}
_COUNTRY_ELIGIBLE = CONFLICT | TRADE | SANCTION | UNREST | {"outage"}
_SEMI = re.compile(r"\b(semiconductor|semiconductors|microchip|microchips|chips?|foundr(?:y|ies)|tsmc)\b", re.I)
_OIL = re.compile(r"\b(oil|crude|petroleum|refiner(?:y|ies)|opec)\b", re.I)
_GAS = re.compile(r"\b(natural gas|lng|gas pipeline|gas export|gas production)\b", re.I)
_WHEAT = re.compile(r"\b(wheat|grain shipments?|grain exports?)\b", re.I)
_COPPER = re.compile(r"\b(copper|copper mine)\b", re.I)
_SHIPPING = re.compile(r"\b(hormuz|suez|straits?|maritime|shipping|canal|red sea|port closure|shipping lanes?)\b", re.I)
_RATE_VERB = re.compile(r"\b(rais(?:e|es|ing)|hik(?:e|es|ing)|cut|cuts|lower|lowers|rate decision|interest rate|policy rates?)\b", re.I)
_CENTRAL_BANK = re.compile(r"\b(fed|federal reserve|fomc|ecb|european central bank|boj|bank of japan|central bank|people.s bank of china)\b", re.I)
_INFLATION = re.compile(r"\b(cpi|consumer price inflation|inflation rate|inflation expectations|breakeven inflation)\b", re.I)
_SOVEREIGN = re.compile(r"\b(sovereign default|debt default|restructur(?:e|ing) sovereign debt|sovereign credit|bond default)\b", re.I)
_VOL = re.compile(r"\b(vix|equity volatility|implied volatility|volatility index)\b", re.I)
_LEVEL_CONDITION = re.compile(r"\b(above|below|exceed|exceeds|reach|reaches|over|under|less than|more than|hit|hits|trade at|settle|close at)\b", re.I)
_DIRECT_FACTORS = {
    "COMMODITY.BRENT": re.compile(r"\b(brent|brent crude)\b", re.I),
    "COMMODITY.WTI": re.compile(r"\b(wti|west texas intermediate)\b", re.I),
    "COMMODITY.GOLD": re.compile(r"\b(gold (?:price|futures)|gold)\b", re.I),
    "COMMODITY.WHEAT": re.compile(r"\b(wheat (?:price|futures))\b", re.I),
    "FX.USD_TWD": re.compile(r"\bUSD\s*[/\-]\s*TWD\b", re.I),
    "FX.USD_CNH": re.compile(r"\bUSD\s*[/\-]\s*CNH\b", re.I),
    "FX.USD_JPY": re.compile(r"\bUSD\s*[/\-]\s*JPY\b", re.I),
    "RATES.US_10Y": re.compile(r"\b(?:US|U\.S\.)?\s*(?:10[- ]year|10Y)\s+(?:Treasury )?(?:yield|rate)\b", re.I),
    "VOL.US_EQUITY_VOL": re.compile(r"\bVIX\b", re.I),
    "INFLATION.US_5Y_BE": re.compile(r"\b(?:US|U\.S\.)?\s*(?:5[- ]year|5Y)\s+(?:inflation\s+)?breakeven\b", re.I),
}

_FF_DIRECT = {
    "FF5.US.HML": re.compile(r"\b(hml factor|high[- ]minus[- ]low|book[- ]to[- ]market spread|value (?:minus|versus|vs\.?) growth stocks?)\b", re.I),
    "FF5.US.SMB": re.compile(r"\b(smb factor|small[- ]minus[- ]big|small[- ]cap (?:minus|versus|vs\.?) large[- ]cap)\b", re.I),
    "FF5.US.RMW": re.compile(r"\b(rmw factor|robust[- ]minus[- ]weak|high[- ]profitability (?:minus|versus|vs\.?) low[- ]profitability)\b", re.I),
    "FF5.US.CMA": re.compile(r"\b(cma factor|conservative[- ]minus[- ]aggressive investment)\b", re.I),
    "STYLE.US.UMD": re.compile(r"\b(umd factor|winners (?:minus|versus|vs\.?) losers|momentum factor return)\b", re.I),
}
_STYLE_HINTS = {
    "FF5.US.HML": re.compile(r"\b(value stocks?|growth stocks?|book[- ]to[- ]market)\b", re.I),
    "FF5.US.SMB": re.compile(r"\b(small[- ]cap|large[- ]cap|company size)\b", re.I),
    "FF5.US.RMW": re.compile(r"\b(profitability|profit margins?)\b", re.I),
    "FF5.US.CMA": re.compile(r"\b(corporate investment|capital expenditure)\b", re.I),
    "STYLE.US.UMD": re.compile(r"\b(momentum|past winners|past losers)\b", re.I),
}

def _contains(text: str, term: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text, re.I))

@lru_cache(maxsize=1)
def catalog() -> dict[str, Any]:
    """Versioned, read-only static catalog. No MotherDuck or external network."""
    value = json.loads(CATALOG.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not value.get("catalog_version"):
        raise ValueError("Unsupported Factors catalog format")
    ids = set()
    for f in value["factors"]:
        if f["id"] in ids:
            raise ValueError("Duplicate factor id " + f["id"])
        ids.add(f["id"])
        for key in ("name", "family", "model", "universe", "definition", "reference"):
            if not isinstance(f.get(key), str) or not f[key].strip():
                raise ValueError("Incomplete factor: " + f["id"] + "." + key)
        if any(x in f for x in ("beta", "coefficient", "loading", "weight", "sign")):
            raise ValueError("Factor catalog may not contain numeric exposure data")
    return value

@lru_cache(maxsize=1)
def factor_index() -> dict[str, dict]:
    return {f["id"]: f for f in catalog()["factors"]}

@lru_cache(maxsize=1)
def overrides() -> dict[str, Any]:
    """Reviewed additions/exclusions, committed as source; never read from DB."""
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not data.get("review_version"):
        raise ValueError("Unsupported Factors review file format")
    seen = set()
    required = ("id","question_id","factor_id","decision","mechanism",
                "rationale","evidence","reviewer","reviewed_at")
    for entry in data.get("entries", []):
        for key in required:
            if not isinstance(entry.get(key),str) or not entry[key].strip():
                raise ValueError("Missing factor review field " + key)
        if entry["id"] in seen:
            raise ValueError("Duplicate Factors review ID " + entry["id"])
        seen.add(entry["id"])
        if entry["decision"] not in ("approve", "reject", "review"):
            raise ValueError("Invalid factor review decision " + entry["decision"])
        if entry["factor_id"] not in factor_index():
            raise ValueError("Factor review points to unknown factor " + entry["factor_id"])
        if any(x in entry for x in ("beta","coefficient","loading","weight","sign","score")):
            raise ValueError("Factor review must be qualitative")
        from datetime import datetime, timezone
        reviewed = datetime.fromisoformat(entry["reviewed_at"].replace("Z","+00:00"))
        if reviewed.tzinfo is None or reviewed.utcoffset() is None:
            raise ValueError("Review timestamp must be timezone-aware")
    return data

def list_factors(family: str | None = None, query: str | None = None) -> list[dict]:
    q = (query or "").casefold().strip()
    return [dict(f) for f in catalog()["factors"] if
            (not family or f["family"] == family) and
            (not q or q in (f["name"] + " " + f["id"] + " " + f["model"] + " " + f["definition"]).casefold())]

def context(question: dict, entities: list[dict] | None = None,
            action: str | None = None) -> dict:
    title = str(question.get("name") or "").strip()
    entities = list(entities or [])
    inferred = find_action(title, "") if not action else None
    canonical_action = action or (inferred[0] if inferred else None)
    regions: dict[str, str] = {}
    for country, spec in COUNTRIES.items():
        match = next((e for e in entities if e.get("id") in spec["ids"] or
                      (e.get("entity_type") == "country" and
                       str(e.get("name") or "").casefold() in spec["terms"])), None)
        if match:
            regions[country] = "linked entity: " + str(match.get("name") or match.get("id"))
        elif any(_contains(title, t) for t in spec["terms"]):
            regions[country] = "contract wording: " + country
    return {"question_id": str(question.get("id") or ""), "title": title,
            "action": canonical_action, "countries": regions,
            "entities": [{"id": str(e.get("id") or ""), "name": str(e.get("name") or "")}
                         for e in entities]}

def map_question(question: dict, entities: list[dict] | None = None,
                 action: str | None = None,
                 proposition_id: str | None = None) -> dict:
    """Pure, deterministic rules: no database calls, probability inputs or coefficients.

    'mapped' means the declared qualitative channel passes its eligibility gates,
    not that the factor moves. 'review_required' candidates are never promoted
    to established links automatically.
    """
    info = context(question, entities, action)
    title, act, countries = info["title"], info["action"], info["countries"]
    available = factor_index()
    links: dict[str, dict] = {}
    suggestions: dict[str, dict] = {}
    mechanisms: set[str] = set()

    def link(factor_id: str, mechanism: str, rule_id: str, reason: str,
             evidence: str, *, review: bool = False) -> None:
        if factor_id not in available:
            raise ValueError("Rule refers to unknown factor " + factor_id)
        item = {
            "factor_id": factor_id,
            "factor": dict(available[factor_id]),
            "status": "review_required" if review else "mapped",
            "link_type": "conditional" if review else "direct_or_structural",
            "mechanism": mechanism, "reason": reason, "evidence": evidence,
            "rule_id": rule_id, "rule_version": RULE_VERSION,
            "provenance": "version_controlled_deterministic_rule",
        }
        mechanisms.add(mechanism)
        target = suggestions if review else links
        target.setdefault(factor_id, item)

    eligible = act in _COUNTRY_ELIGIBLE
    if eligible:
        for region, evidence in sorted(countries.items()):
            factor_id = "EQUITY.COUNTRY." + region
            if factor_id in available:
                link(factor_id, "country_risk", "COUNTRY_EQUITY_V1",
                     "Event action and named country create a direct country-equity relevance path.",
                     "action=" + str(act) + "; " + evidence)
            if region in COUNTRY_FX:
                link(COUNTRY_FX[region], "currency_country", "COUNTRY_FX_V1",
                     "Event action and named jurisdiction connect to its exchange-rate factor.",
                     "action=" + str(act) + "; " + evidence)
    # When the contract *directly asks about a defined factor level*,
    # the relevant factor is the observable itself; require both its precise
    # identifier and a conditional threshold to avoid incidental references.
    if _LEVEL_CONDITION.search(title):
        for fid, pattern in _DIRECT_FACTORS.items():
            if pattern.search(title):
                link(fid, "direct_factor_outcome", "DIRECT_OBSERVABLE_V1",
                     "The contract directly specifies a threshold for the named factor quantity.",
                     "explicit benchmark identifier and threshold in contract title")
    # Only add explicit industry/commodity paths for material actions in event terms.
    if act in SUPPLY_ACTIONS and _SEMI.search(title):
        link("EQUITY.INDUSTRY.SEMICONDUCTORS", "semiconductor_supply",
             "SEMICONDUCTOR_EXPLICIT_V1",
             "An eligible event action explicitly concerns chip supply or production.",
             "action=" + str(act) + "; title contains semiconductor terminology")
    if act in SUPPLY_ACTIONS and _OIL.search(title):
        for fid in ("COMMODITY.BRENT", "EQUITY.INDUSTRY.ENERGY"):
            link(fid, "oil_supply", "OIL_EXPLICIT_V1",
                 "Explicit oil reference and eligible disruption or policy action.",
                 "action=" + str(act) + "; title explicitly mentions oil or petroleum")
    if act in SUPPLY_ACTIONS and _GAS.search(title):
        link("COMMODITY.NATGAS", "gas_supply", "GAS_EXPLICIT_V1",
             "Explicit natural gas supply or policy exposure.",
             "action=" + str(act) + "; title names natural gas")
        if "asia" in title.casefold() or "lng" in title.casefold():
            link("COMMODITY.LNG_ASIA", "gas_supply", "ASIAN_LNG_V1",
                 "Explicit LNG or Asian natural-gas market relevance.",
                 "action=" + str(act) + "; named LNG or Asia")
    if act in SUPPLY_ACTIONS and _WHEAT.search(title):
        link("COMMODITY.WHEAT", "agriculture_supply", "WHEAT_EXPLICIT_V1",
             "Explicit wheat or grain-supply mechanism.",
             "action=" + str(act) + "; title names wheat or grain shipments")
    if act in SUPPLY_ACTIONS and _COPPER.search(title):
        link("COMMODITY.COPPER", "industrial_metals_supply", "COPPER_EXPLICIT_V1",
             "Explicit copper supply or trade mechanism.",
             "action=" + str(act) + "; title names copper")
    if act in SHIPPING and _SHIPPING.search(title):
        link("COMMODITY.FREIGHT", "marine_transport", "MARITIME_ROUTE_V1",
             "Route closure, blockade or transit question has an explicit maritime transmission path.",
             "action=" + str(act) + "; named shipping route")
        link("EQUITY.INDUSTRY.SHIPPING", "marine_transport", "MARITIME_INDUSTRY_V1",
             "Explicit shipping-route event is relevant to marine transportation industry.",
             "action=" + str(act) + "; named maritime route")
        if _contains(title, "hormuz"):
            link("COMMODITY.BRENT", "oil_shipping", "HORMUZ_OIL_ROUTE_V1",
                 "The Strait of Hormuz is an established crude-oil transit route.",
                 "action=" + str(act) + "; Strait of Hormuz explicitly named")
    if _CENTRAL_BANK.search(title) and _RATE_VERB.search(title):
        if re.search(r"\b(fed|federal reserve|fomc)\b", title, re.I):
            link("RATES.US_POLICY", "monetary_policy", "FED_POLICY_V1",
                 "Explicit Federal Reserve policy-rate question.", "contract names the Fed and a rate action")
            link("RATES.US_2Y", "monetary_policy", "FED_FRONT_END_V1",
                 "Short-dated U.S. government yield is directly connected to Fed policy transmission.",
                 "contract names the Fed and a rate action")
        if re.search(r"\b(ecb|european central bank)\b", title, re.I):
            link("RATES.ECB_POLICY", "monetary_policy", "ECB_POLICY_V1",
                 "Explicit ECB rate-policy question.", "contract names the ECB and a rate action")
        if re.search(r"\b(boj|bank of japan)\b", title, re.I):
            link("RATES.BOJ_POLICY", "monetary_policy", "BOJ_POLICY_V1",
                 "Explicit BOJ rate-policy question.", "contract names the BOJ and a rate action")
    if _INFLATION.search(title):
        # A CPI release is not itself an inflation breakeven expectation.
        fid = "INFLATION.US_5Y_BE" if ("US" in countries or re.search(r"\bUS\b", title) or re.search(r"\b(u\.s\.|united states|american)\b", title, re.I)) else "INFLATION.GLOBAL_INFLATION"
        if fid not in links:
            link(fid, "inflation_expectations", "INFLATION_REVIEW_V1",
                 "Inflation data and traded inflation expectations are distinct; establish the transmission first.",
                 "contract explicitly references inflation or CPI", review=True)
    if _SOVEREIGN.search(title):
        if "CN" in countries:
            fid = "CREDIT.CN_SOVEREIGN"
        elif "TW" in countries:
            fid = "CREDIT.TW_SOVEREIGN"
        else:
            fid = "CREDIT.EM_SOVEREIGN"
        link(fid, "sovereign_credit", "SOVEREIGN_CREDIT_V1",
             "Explicit sovereign credit/default question.",
             "contract explicitly references sovereign credit or default")
    if _VOL.search(title) and "VOL.US_EQUITY_VOL" not in links:
        link("VOL.US_EQUITY_VOL", "equity_volatility", "VOLATILITY_DIRECT_REVIEW_V1",
             "Volatility factor universe and horizon must be explicitly verified.",
             "contract explicitly references volatility", review=True)
    # Style factors are long-short *spreads*. Broad country/sector relevance
    # does not make an event relevant to HML, SMB, RMW, CMA or momentum.
    for fid, pattern in _FF_DIRECT.items():
        if pattern.search(title):
            link(fid, "relative_style_spread", "STYLE_SPREAD_REVIEW_V1",
                 "Explicit factor/relative-style wording, but verify factor definition and geography.",
                 "contract names a style spread", review=True)
    for fid, pattern in _STYLE_HINTS.items():
        if fid not in links and fid not in suggestions and pattern.search(title):
            link(fid, "possible_style_differential", "STYLE_DIFFERENTIAL_REVIEW_V1",
                 "Mentions a style characteristic but does not establish a factor return-spread effect.",
                 "contract contains style-related terminology", review=True)
    if act in CONFLICT and "TW" in countries and "EQUITY.INDUSTRY.SEMICONDUCTORS" not in links:
        link("EQUITY.INDUSTRY.SEMICONDUCTORS", "potential_chip_supply_chain",
             "TAIWAN_CHIP_DEPENDENCY_REVIEW_V1",
             "Taiwan conflict may disrupt chips; verify manufacturing relevance before accepting the link.",
             "conflict action plus Taiwan; no explicit semiconductor contract term", review=True)
    if act in CONFLICT:
        link("EQUITY.INDUSTRY.DEFENSE", "potential_defense_demand",
             "CONFLICT_DEFENSE_REVIEW_V1",
             "Defense-demand effects depend on governments, contractors, and time horizon.",
             "conflict event type without validated contract-level defense-demand mechanism",
             review=True)

    # Analyst review override register. A reviewer may accept a well-supported
    # candidate, explicitly reject a false positive, or downgrade an automatic
    # mapping for further review. Entries are version-controlled, not stored
    # in MotherDuck and never represent numeric sensitivities.
    exclusions = []
    applied = []
    review = overrides()
    for entry in review["entries"]:
        if entry["question_id"] != info["question_id"]:
            continue
        scoped = entry.get("proposition_id")
        if scoped and scoped != proposition_id:
            continue
        fid = entry["factor_id"]
        decision = entry["decision"]
        applied.append(entry["id"])
        if decision == "reject":
            links.pop(fid, None)
            suggestions.pop(fid, None)
            exclusions.append({"factor_id": fid, "decision": "rejected_by_reviewer",
                "rationale": entry["rationale"], "evidence": entry["evidence"],
                "reviewer": entry["reviewer"], "reviewed_at": entry["reviewed_at"],
                "override_id": entry["id"]})
            continue
        row = dict(factor_id=fid, factor=dict(available[fid]),
            status="mapped" if decision == "approve" else "review_required",
            link_type="curated_qualitative" if decision == "approve" else "conditional",
            mechanism=entry["mechanism"], reason=entry["rationale"],
            evidence=entry["evidence"],
            rule_id="CURATED:" + entry["id"], rule_version=RULE_VERSION,
            provenance="source_controlled_analyst_review",
            reviewer=entry["reviewer"], reviewed_at=entry["reviewed_at"],
            override_id=entry["id"])
        links.pop(fid, None)
        suggestions.pop(fid, None)
        (links if decision == "approve" else suggestions)[fid] = row
        mechanisms.add(entry["mechanism"])
    # A review candidate superseded by a mapped link is not returned as a duplicate.
    for fid in links:
        suggestions.pop(fid, None)
    result = {
        "question_id": info["question_id"], "proposition_id": proposition_id,
        "title": title, "action": act,
        "catalog_version": catalog()["catalog_version"],
        "rule_version": RULE_VERSION, "review_version": review["review_version"],
        "applied_review_ids": applied, "exclusions": exclusions,
        "mapping_basis": MAPPING_BASIS,
        "time_travel_caveat": "Current versioned rules are applied to the requested event graph snapshot; this is not a historical record of past analyst approvals.",
        "mechanisms": sorted(mechanisms),
        "factors": sorted(links.values(), key=lambda x: (x["factor"]["family"], x["factor_id"])),
        "review_candidates": sorted(suggestions.values(), key=lambda x: (x["factor"]["family"], x["factor_id"])),
    }
    result["status"] = "mapped" if links else ("review_only" if suggestions else "unmapped")
    result["unmapped_reason"] = None if links or suggestions else (
        "No eligible evidence-backed factor mechanism was identified; no links were inferred.")
    return result

def factor_coverage(factor_id: str, questions: list[tuple[dict, list[dict], str | None]],
                    include_review: bool = False) -> list[dict]:
    """Reverse lookup across caller-supplied graph questions; no price/DB reads."""
    if factor_id not in factor_index():
        raise KeyError(factor_id)
    out = []
    for question, entities, action in questions:
        mapping = map_question(question, entities, action)
        link = next((x for x in mapping["factors"] if x["factor_id"] == factor_id), None)
        if not link and include_review:
            link = next((x for x in mapping["review_candidates"] if x["factor_id"] == factor_id), None)
        if link:
            out.append({"question_id": question.get("id"), "name": question.get("name"),
                        "status": link["status"], "mechanism": link["mechanism"],
                        "reason": link["reason"], "rule_id": link["rule_id"]})
    return sorted(out, key=lambda x: (x["name"] or "", x["question_id"] or ""))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Inspect qualitative Factors catalog with no database.")
    p.add_argument("--query", default="", help="Filter factor names and definitions")
    p.add_argument("--family", default="", help="Factor family")
    p.add_argument("--demo", action="store_true", help="Show deterministic example question mapping")
    a = p.parse_args()
    if a.demo:
        print(json.dumps(map_question({"id":"q:demo", "name":"Will China blockade Taiwan?"},
            [{"id":"wd:Q865","name":"Taiwan","entity_type":"country"},
             {"id":"wd:Q148","name":"China","entity_type":"country"}], "blockade"), indent=2))
    else:
        print(json.dumps({"catalog_version":catalog()["catalog_version"],
            "factors": list_factors(a.family or None, a.query or None)}, indent=2))
