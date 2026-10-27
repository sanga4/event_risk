"use strict";
/* Excel-host only: live, rights-safe MotherDuck totals, no warehouse rows or token. */
(function(){
 const button=()=>document.getElementById("live-coverage-import");
 const status=()=>document.getElementById("status");
 async function importLive(){
   const b=button();if(b)b.disabled=true;
   try{
     const response=await fetch("/api/v1/live-coverage",{cache:"no-store"});
     if(!response.ok)throw Error("Live aggregate HTTP "+response.status);
     const source=await response.json();
     if(source.mode!=="LIVE_AGGREGATE_MOTHERDUCK_NO_SOURCE_REDISPLAY"||
        source.coverage_claim!=="CAPTURED_WAREHOUSE_SAMPLE_NOT_ALL_PROVIDER_CONTRACTS"||
        source.market_quotes_included!==false||source.raw_contracts_included!==false)
       throw Error("Unexpected warehouse provenance");
     const m=source.metrics;
     const rows=[
       ["MOTHERDUCK LIVE AGGREGATE","Value"],
       ["Observed / verified API snapshot time",source.as_of_utc],
       ["Kalshi captured market IDs (subset)",m.captured_kalshi_market_ids],
       ["Polymarket captured market IDs (subset)",m.captured_polymarket_market_ids],
       ["Versioned source question IDs",m.question_node_ids],
       ["Versioned source entity IDs",m.entity_node_ids],
       ["Factor IDs with observed history",m.observed_factor_series],
       ["Warehouse factor catalog definitions",m.warehouse_factor_definitions],
       ["Securities with funding models",m.securities_with_funding_models],
       ["Latest captured market observed date",m.latest_captured_observed_date],
       ["Data scope","CAPTURED_WAREHOUSE_SAMPLE_NOT_ALL_MARKETS"],
       ["Source quote contents included","NO"],
       ["Underlying database privileges","Token may have read/write; API restricts SQL"],
       ["Model approval","NO_EVENT_CAUSAL_BETA_APPROVAL"],
     ];
     await Excel.run(async ctx=>{
       const sheets=ctx.workbook.worksheets;
       let sh=sheets.getItemOrNullObject("ER_LiveCoverage");
       await ctx.sync();
       if(sh.isNullObject)sh=sheets.add("ER_LiveCoverage");
       const range=sh.getRangeByIndexes(0,0,rows.length,2);
       range.values=rows;
       sh.getRange("A1:B1").format.font.bold=true;
       sh.getRange("A1:B1").format.fill.color="#E9EDF3";
       range.format.autofitColumns();
       await ctx.sync();
     });
     status().textContent="Imported live MotherDuck aggregate coverage into ER_LiveCoverage. Counts do not imply all exchange markets or approved source redisplay.";
   }catch(e){
     status().textContent="Live warehouse aggregate import unavailable: "+e.message;
   }finally{if(b)b.disabled=false;}
 }
 document.addEventListener("DOMContentLoaded",()=>{
   const b=button();if(!b)return;
   b.addEventListener("click",importLive);
   if(typeof Office!=="undefined")
     Office.onReady(info=>{if(info.host===Office.HostType.Excel)b.disabled=false;});
 });
})();
