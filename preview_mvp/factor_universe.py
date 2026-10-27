"""Extended qualitative factor taxonomy, not a measurement database.

Canonical 108 repository factor references remain untouched. These proposals
are deliberately separate until a licensed, source-observed, properly vintaged
series is validated. Do not treat labels as fitted factors or security betas.
"""
from __future__ import annotations
from pathways import FACTOR_PROPOSALS

TAXONOMY={
 "electricity":["PJM LMP day ahead","ERCOT real time hub price",
    "CAISO nodal congestion","MISO LMP","NYISO locational price",
    "ISO NE electricity forward","ERCOT reserve margin","PJM capacity auction",
    "Hourly load forecast surprise","Power grid connection wait time",
    "Transmission build cost","Corporate PPA price"],
 "generation":["Natural gas spark spread","Nuclear generation output",
    "Wind capacity factor","Solar capacity factor","Coal power marginal cost",
    "Battery storage wholesale arbitrage","Grid interconnection queue capacity"],
 "cloud_ai":["GPU lease spot price","GPU rental forward commitments",
    "AI training accelerator backlog","AI inference unit cost",
    "Server rack installed MW","Data center power usage effectiveness",
    "Cloud capex growth","GPU memory bandwidth supply","Optical networking capacity",
    "Cooling energy per compute unit","Regional data center vacancy"],
 "semiconductors":["HBM capacity utilization","Advanced logic foundry utilization",
    "Semiconductor equipment orders","DRAM contract pricing",
    "High speed networking ASIC shipments","CoWoS packaging availability",
    "Advanced process yield trend"],
 "metals":["Copper physical premium","Aluminum Midwest premium","Uranium spot",
    "Lithium carbonate spot","Rare earth oxide index",
    "Silicon wafer inputs","Transformer grain oriented steel price"],
 "energy":["Henry Hub basis","AECO natural gas basis","European TTF gas",
    "Japan Korea marker LNG","Brent WTI spread","U.S. oil refinery crack spread",
    "Coal Newcastle benchmark","Diesel middle distillate spread"],
 "rates":["Treasury 1Y OIS basis","SOFR term structure","10Y swap spread",
    "30Y swap spread","UST term premium","TIPS real curve slope",
    "Eurozone OIS forward","UK gilt 10Y","JPY 10Y JGB yield",
    "Cross currency basis USDJPY"],
 "credit":["BBB industrial OAS","U.S. high yield CCC spread",
    "Utility sector IG spread","Financial senior CDS index",
    "Commercial MBS spread","Data center ABS spread",
    "Private credit spread proxy","Corporate default expectation proxy"],
 "equity":["AI infrastructure equity basket","Data center REIT basket",
    "Utility generation equity basket","Semiconductor fab equipment basket",
    "Cloud hyperscaler equity basket","Emerging markets equity beta",
    "Small cap quality spread","Growth minus value spread"],
 "fx":["USD broad dollar index","EURUSD basis","USDJPY spot",
    "USDCNY onshore","USDTWD spot","USDKRW spot",
    "USDINR spot","USD trade weighted real effective exchange rate"],
 "volatility":["SPX implied volatility term structure","MOVE index term structure",
    "WTI implied volatility","EURUSD implied volatility",
    "Tail correlation stress proxy","Credit option skew"],
 "macro_growth":["Real GDP nowcast","Industrial production surprise",
    "Global PMI diffusion","Consumer confidence change",
    "Productivity surprise","Inventory to sales ratio",
    "Capex intentions index"],
 "inflation":["PCE headline first release","Core CPI first release",
    "Services CPI ex shelter first release","Wage inflation first release",
    "Inflation swap 1Y","Consumer inflation expectations"],
 "labor":["Unemployment rate first release","Nonfarm payroll surprise",
    "Initial claims revision adjusted","Average hourly earnings surprise",
    "Job opening ratio","Employment cost index"],
 "housing":["U.S. mortgage 30Y rate","Housing starts first release",
    "Multifamily construction index","Commercial real estate cap rate",
    "Residential rent growth","Commercial property vacancy"],
 "policy_regulation":["Tariff rate by product category","Export control intensity proxy",
    "Central bank policy path surprise","Fiscal expenditure revision",
    "AI safety regulatory burden proxy","Infrastructure permit delay"],
 "climate_water":["Data center water scarcity","Water withdrawal pricing",
    "Drought intensity weighted industrial output","Carbon allowance forward",
    "Grid emissions intensity","Extreme weather risk premium"],
 "supply_chain":["Shipping container cost","Air cargo freight cost",
    "Critical semiconductor lead time","High voltage transformer lead time",
    "Data center construction lead time","Global supplier delivery time"],
 "geopolitics":["Trade restriction index","Sovereign CDS geopolitical factor",
    "Sanctions regime intensity","Conflict supply disruption risk",
    "Political event implied uncertainty proxy"],
 "funding":["SOFR EFFR spread","Tri party repo rate","Treasury specialness spread",
    "Money market fund flows","Commercial paper spread",
    "Dealer balance sheet capacity proxy"],
}
def factor_proposals():
    out=[]
    seen=set()
    for native_id,label,family in FACTOR_PROPOSALS:
        key="PROPOSED."+native_id
        seen.add(key)
        out.append({"factor_id":key,"name":label,"family":family,
          "validated_observation_series":False,
          "original_publication_pit_verified":False,
          "market_data_rights_verified":False,
          "release_status":"PROPOSED_DEFINITION_ONLY"})
    for family,names in TAXONOMY.items():
        for name in names:
            slug="".join(c if c.isalnum() else "_" for c in name.upper()).strip("_")
            while "__" in slug:slug=slug.replace("__","_")
            key="PROPOSED."+family.upper()+"."+slug
            if key in seen:continue
            seen.add(key)
            out.append({"factor_id":key,"name":name,"family":family,
                "validated_observation_series":False,
                "original_publication_pit_verified":False,
                "market_data_rights_verified":False,
                "release_status":"PROPOSED_DEFINITION_ONLY"})
    return out
