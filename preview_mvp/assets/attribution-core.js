"use strict";
/* Pure manual-holdings relevance attribution.
 * No DOM, no network, no persistence, no security return forecasts.
 * Exposes a browser namespace and Node/CommonJS for deterministic CI tests.
 */
(function(root){
  function numberOrInvalid(v,blankOk){
    const str=String(v??"").replace(/[$,\s]/g,"");
    if(!str)return blankOk?null:NaN;
    const value=Number(str);
    return Number.isFinite(value)&&Math.abs(value)<=1e12?value:NaN;
  }

  // Screening rules are transparent qualitative watchlist tags only.
  // They NEVER create a prior weight, security beta, return direction or P&L.
  const CHANNEL_WATCH_RULES={
    inflation:{sectors:["Consumer Staples","Energy","Materials","Utilities","Financials"]},
    growth:{sectors:["Industrials","Consumer Discretionary","Financials","Information Technology"]},
    policy:{sectors:["Financials","Real Estate","Utilities"]},
    treasury:{sectors:["Financials","Real Estate","Utilities"]},
    credit:{sectors:["Financials","Real Estate","Consumer Discretionary"]},
    funding:{sectors:["Financials","Real Estate"]},
    risk_appetite:{sectors:["Financials","Consumer Discretionary","Information Technology"]},
    supply:{sectors:["Information Technology","Industrials","Materials"]},
    trade:{sectors:["Industrials","Information Technology","Materials","Consumer Discretionary"],
      countries:["CN","TW","KR","JP"]},
    fx:{countries:["CN","TW","KR","JP","NL"]},
    earnings:{sectors:["Information Technology","Consumer Discretionary","Industrials"]},
    energy:{sectors:["Energy","Utilities","Industrials","Materials"]},
    agriculture:{sectors:["Consumer Staples","Materials"]},
    labor:{sectors:["Industrials","Consumer Discretionary","Consumer Staples"]},
    housing:{sectors:["Real Estate","Financials","Utilities"]},
    fiscal:{sectors:["Industrials","Financials","Utilities"]},
    regulation:{sectors:["Health Care","Information Technology","Financials","Utilities"]},
    volatility:{sectors:["Financials","Consumer Discretionary"]},
    liquidity:{sectors:["Financials","Real Estate"]},
    technology:{sectors:["Information Technology","Industrials"]},
    commodities:{sectors:["Materials","Energy","Consumer Staples"]},
    cross_asset:{sectors:["Financials"]}
  };
  function screenHolding(security,channelIds){
    const matches=[];
    for(const nodeId of channelIds){
      const channel=String(nodeId).startsWith("channel:")?
        String(nodeId).slice("channel:".length):String(nodeId);
      const rule=CHANNEL_WATCH_RULES[channel];
      if(!rule)continue;
      const sector=String(security.description||security.sector||"").trim();
      const country=String(security.subtitle||security.country||"").trim();
      if((rule.sectors||[]).includes(sector)||(rule.countries||[]).includes(country))
        matches.push(channel);
    }
    return matches;
  }
  function calculate({holdings,scenarioId,graph}){
    if(!graph||!Array.isArray(graph.nodes)||!Array.isArray(graph.edges))
      throw Error("Missing approved research graph source");
    const validTickers=new Set(graph.nodes.filter(n=>n.type==="security"&&n.ticker)
      .map(n=>String(n.ticker).toUpperCase()));
    const entities=new Set(graph.edges.filter(e=>e.src===scenarioId&&
      e.type==="hypothetical_involves"&&e.review_status==="RESEARCH_ONLY_NOT_APPROVED").map(e=>e.dst));
    const channels=graph.edges.filter(e=>e.src===scenarioId&&
      e.type==="hypothetical_transmission"&&e.review_status==="RESEARCH_ONLY_NOT_APPROVED")
      .map(e=>e.dst);
    const byTicker=new Map(graph.nodes.filter(n=>n.type==="security"&&n.ticker)
      .map(n=>[String(n.ticker).toUpperCase(),n]));
    const priors=new Map();
    for(const e of graph.edges){
      if(e.type!=="research_exposure_prior"||!entities.has(e.src)||
         e.review_status!=="RESEARCH_ONLY_NOT_APPROVED")continue;
      const weight=Number(e.weight);
      if(!Number.isFinite(weight)||weight<=0||weight>1)continue;
      const current=priors.get(e.dst);
      if(!current||weight>current.weight)priors.set(e.dst,{weight,reason:e.summary||"Original source seed analyst prior"});
    }
    const errors=[],rows=[];
    if(!Array.isArray(holdings)||holdings.length>100)
      return {errors:["Maximum 100 manually entered holdings."],rows:[]};
    for(const h of holdings){
      const ticker=String(h.ticker||"").trim().toUpperCase();
      if(!ticker&&!String(h.value||"").trim()&&!String(h.shock||"").trim())continue;
      if(!/^[A-Z0-9.=_-]{1,25}$/.test(ticker)||!validTickers.has(ticker)){
        errors.push("Unknown/unlisted ticker "+(ticker||"(blank)")+".");continue;
      }
      const value=numberOrInvalid(h.value,false);
      if(!Number.isFinite(value)||value===0){
        errors.push(ticker+": enter a finite nonzero signed position value.");continue;
      }
      const shock=numberOrInvalid(h.shock,true);
      if(shock!==null&&(!Number.isFinite(shock)||Math.abs(shock)>1000)){
        errors.push(ticker+": manually assumed return must be within −1000% to +1000%.");continue;
      }
      const prior=priors.get("security:"+ticker);
      const channelFlags=screenHolding(byTicker.get(ticker),channels);
      rows.push({ticker,value,absValue:Math.abs(value),
        relevance:prior?.weight??null,reason:prior?.reason||"",
        watchlistChannels:channelFlags,
        shock,pnl:shock===null?null:value*shock/100,
        status:prior?"Source prior mapped":channelFlags.length?
          "Unweighted channel watchlist only":"No source-prior mapping"});
    }
    if(errors.length)return {errors,rows:[]};
    const gross=rows.reduce((sum,row)=>sum+row.absValue,0);
    let score=0,covered=0,pnl=0,provided=0;
    for(const row of rows){
      row.grossShare=gross?row.absValue/gross:0;
      row.contribution=row.relevance===null?null:row.grossShare*row.relevance;
      if(row.contribution!==null){score+=row.contribution;covered+=row.absValue;}
      if(row.pnl!==null){pnl+=row.pnl;provided++;}
    }
    return {errors:[],rows,gross,score,coveredFraction:gross?covered/gross:0,
      mapped:rows.filter(r=>r.relevance!==null).length,
      watchlistCount:rows.filter(r=>r.watchlistChannels.length>0).length,
      pnl,provided,scenarioId,
      screenSource:"SECTOR_COUNTRY_MATCHED_UNVALIDATED_WATCHLIST_TAGS_ONLY",
      returnSource:"USER_ENTERED_ASSUMPTIONS_ONLY",
      priorSource:"PUBLIC_EDITABLE_ANALYST_PRIORS_NOT_BETA"};
  }
  const publicAPI={calculate,numberOrInvalid,screenHolding,CHANNEL_WATCH_RULES};
  if(typeof module!=="undefined"&&module.exports)module.exports=publicAPI;
  if(root)root.EventRiskAttribution=publicAPI;
})(typeof window!=="undefined"?window:null);
