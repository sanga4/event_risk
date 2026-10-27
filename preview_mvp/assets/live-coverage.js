"use strict";
document.addEventListener("DOMContentLoaded",async()=>{
 const output=document.getElementById("warehouse-summary");
 if(!output)return;
 try{
  const r=await fetch("/api/v1/live-coverage",{cache:"no-store"});
  if(!r.ok)throw Error("HTTP "+r.status);
  const d=await r.json();
  if(d.mode!=="LIVE_AGGREGATE_MOTHERDUCK_NO_SOURCE_REDISPLAY"||
     d.coverage_claim!=="CAPTURED_WAREHOUSE_SAMPLE_NOT_ALL_PROVIDER_CONTRACTS")
    throw Error("Unrecognized dataset");
  const m=d.metrics;
  const n=v=>Number.isSafeInteger(v)&&v>=0?v.toLocaleString():"?";
  output.textContent="MotherDuck live sample: Kalshi "+n(m.captured_kalshi_market_ids)+
   ", Polymarket "+n(m.captured_polymarket_market_ids)+
   ", observed factor series "+n(m.observed_factor_series)+
   ". Not the full exchange history or licensed quotes.";
  output.title="Aggregate query "+d.as_of_utc+"; last captured market date "+
   (m.latest_captured_observed_date||"unknown");
 }catch(e){
  output.textContent="Live counts unavailable. Repository reference graph remains usable.";
 }
});
