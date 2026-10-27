"""Directional reference pathway graph.

The additional contract is an explicitly artificial UI illustration: not a
Kalshi/Polymarket listing, not priced, no event occurrence verified. Links are
unreviewed thematic hypotheses; never model coefficients or issuer PIT facts.
"""
from __future__ import annotations
from copy import deepcopy

DEMO_CONTRACT="contract:illustrative:data_center_power"
DEMO_EVENT="event:data_center_demand"
DEMO_ENTITY="entity:theme:data_center_infrastructure"
FACTOR_PROPOSALS=[
 ("POWER.US.REGIONAL_LMP","Regional U.S. nodal electricity spot pricing","power"),
 ("POWER.US.FORWARD_CURVE","Regional wholesale electricity forward curve","power"),
 ("POWER.US.CAPACITY","U.S. regional generation capacity clearing price","power"),
 ("POWER.US.GRID_CONGESTION","Power transmission congestion basis","power"),
 ("POWER.US.LOAD_GROWTH","Regional grid peak-load forecast","power"),
 ("POWER.US.PPA","Long-dated corporate power purchase agreement pricing","power"),
 ("COMMODITY.US.NATGAS_POWER_BASIS","Regional gas-to-power generation basis","commodity"),
 ("TECH.GPU_CAPACITY","AI compute accelerator supply capacity proxy","technology"),
 ("TECH.DATA_CENTER_UTILIZATION","Data center occupied rack / megawatt utilization","technology"),
 ("TECH.AI_CLOUD_CAPEX","Hyperscaler AI infrastructure capex proxy","technology"),
 ("INFRA.TRANSFORMER_LEAD_TIMES","High-voltage transformer delivery lead-time proxy","industry"),
 ("INFRA.DATA_CENTER_COOLING","Data center cooling infrastructure order growth proxy","industry"),
 ("REAL_ESTATE.DC_REIT","Data center real estate investment trust index","real_estate"),
 ("WATER.DC_RESOURCE_STRESS","Regional cooling water availability stress proxy","environment"),
 ("CREDIT.UTILITIES_SPREAD","Utility issuer credit spread proxy","credit"),
 ("CARBON.GRID_INTENSITY","Regional marginal electricity emissions intensity proxy","environment"),
]
# Publicly known US-traded reference tickers: relevance is a proposed thematic
# watchlist, never a fitted security event beta or assertion of realized impact.
SECURITY_TO_FACTOR={
 "EQIX":["REAL_ESTATE.DC_REIT","TECH.DATA_CENTER_UTILIZATION"],
 "DLR":["REAL_ESTATE.DC_REIT","TECH.DATA_CENTER_UTILIZATION"],
 "VRT":["INFRA.DATA_CENTER_COOLING","TECH.AI_CLOUD_CAPEX"],
 "MSFT":["TECH.AI_CLOUD_CAPEX","POWER.US.PPA"],
 "AMZN":["TECH.AI_CLOUD_CAPEX","POWER.US.PPA"],
 "GOOGL":["TECH.AI_CLOUD_CAPEX","POWER.US.PPA"],
 "NVDA":["TECH.GPU_CAPACITY","TECH.AI_CLOUD_CAPEX"],
 "AMD":["TECH.GPU_CAPACITY"],
 "AVGO":["TECH.GPU_CAPACITY"],
 "ETN":["INFRA.TRANSFORMER_LEAD_TIMES","POWER.US.GRID_CONGESTION"],
 "PWR":["INFRA.TRANSFORMER_LEAD_TIMES","POWER.US.LOAD_GROWTH"],
 "CEG":["POWER.US.FORWARD_CURVE","POWER.US.PPA"],
 "VST":["POWER.US.FORWARD_CURVE","POWER.US.CAPACITY"],
 "NEE":["POWER.US.PPA","POWER.US.CAPACITY"],
 "TSM":["TECH.GPU_CAPACITY"],
}
def graph_paths(reference_graph):
    result=deepcopy(reference_graph)
    nodes=result["nodes"];edges=result["edges"]
    ids={n["id"] for n in nodes}
    synthetic=[
      {"id":DEMO_CONTRACT,"type":"contract",
       "name":"DEMO contract · U.S. data-center electricity demand",
       "provider":"ILLUSTRATIVE_ONLY_NOT_KALSHI_OR_POLYMARKET",
       "review_status":"SYNTHETIC_VISUALIZATION_NOT_AN_ACTUAL_LISTING",
       "description":"Example contract for validating graph navigation. No exchange ID, market price or resolution rules."},
      {"id":DEMO_EVENT,"type":"event","name":"Data-center electricity demand acceleration",
       "review_status":"HYPOTHETICAL_NOT_OBSERVED",
       "description":"Proposed canonical event scenario; no independent event record or market settlement."},
      {"id":DEMO_ENTITY,"type":"entity","name":"U.S. data-center / power infrastructure ecosystem",
       "review_status":"THEMATIC_WATCHLIST_NOT_VERIFIED_CONTRACT_MAPPING",
       "description":"Thematic entity group, not a single legal issuer."},
    ]
    for id_,label,family in FACTOR_PROPOSALS:
      synthetic.append({"id":"factor:PROPOSED."+id_,"type":"factor",
                        "name":label,"subtitle":family,
                        "review_status":"PROPOSED_FACTOR_DEFINITION_NO_VERIFIED_SERIES",
                        "historical_series_validated":False})
    for n in synthetic:
      if n["id"] not in ids:
        nodes.append(n);ids.add(n["id"])
    def edge(src,dst,typ):
      if src in ids and dst in ids:
        edges.append({"src":src,"dst":dst,"type":typ,
          "review_status":"RESEARCH_ONLY_NOT_APPROVED",
          "causal_effect_estimated":False,
          "source_kind":"EXPLICIT_ILLUSTRATIVE_HYPOTHESIS"})
    edge(DEMO_CONTRACT,DEMO_EVENT,"illustrative_contract_hypothesizes")
    edge(DEMO_EVENT,DEMO_ENTITY,"illustrative_event_involves")
    for ticker,factors in SECURITY_TO_FACTOR.items():
      node="security:"+ticker
      if node not in ids:continue
      edge(DEMO_ENTITY,node,"proposed_thematic_relevance")
      for factor in factors:
        edge(node,"factor:PROPOSED."+factor,"proposed_security_factor_exposure")
    result["mode"]="PUBLIC_REFERENCE_PLUS_EXPLICIT_SYNTHETIC_PATH_EXAMPLE"
    result["contract_count_verified"]=0
    result["contract_demo_count"]=1
    result["proposed_factor_definitions"]=len(FACTOR_PROPOSALS)
    result["contract_source_note"]="No Kalshi or Polymarket contract is represented as verified by this demonstration."
    return result
