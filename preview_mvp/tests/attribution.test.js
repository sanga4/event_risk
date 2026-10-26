"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const A=require("../assets/attribution-core.js");
const graph={
  nodes:[
    {id:"event:taiwan",type:"event",name:"Taiwan"},
    {id:"event:funding",type:"event",name:"Funding stress"},
    {id:"entity:Q865",type:"entity",name:"Taiwan"},
    {id:"entity:Q2986369",type:"entity",name:"Semiconductor industry"},
    ...["TSM","NVDA","AAPL","FXI"].map(ticker=>({id:"security:"+ticker,ticker,type:"security",name:ticker}))
  ],
  edges:[
    {src:"event:taiwan",dst:"entity:Q865",type:"hypothetical_involves",review_status:"RESEARCH_ONLY_NOT_APPROVED"},
    {src:"event:taiwan",dst:"entity:Q2986369",type:"hypothetical_involves",review_status:"RESEARCH_ONLY_NOT_APPROVED"},
    ...[["Q865","TSM",.9],["Q865","NVDA",.5],["Q865","AAPL",.4],
         ["Q2986369","TSM",.75],["Q2986369","NVDA",.3],["Q2986369","AAPL",.1]]
       .map(([qid,ticker,weight])=>({src:"entity:"+qid,dst:"security:"+ticker,
         type:"research_exposure_prior",weight,
         review_status:"RESEARCH_ONLY_NOT_APPROVED"}))
  ]
};
const holdings=[
  {ticker:"TSM",value:"25,000",shock:"-5"},
  {ticker:"NVDA",value:"15000",shock:"-3"},
  {ticker:"AAPL",value:"10000",shock:"-2"},
  {ticker:"FXI",value:"-5000",shock:"4"}
];
const r=A.calculate({holdings,scenarioId:"event:taiwan",graph});
assert.equal(r.errors.length,0);
assert.equal(r.rows.length,4);
assert.equal(r.gross,55000);
assert.ok(Math.abs(r.score-34000/55000)<1e-10);
assert.ok(Math.abs(r.coveredFraction-50000/55000)<1e-10);
assert.equal(r.mapped,3);
assert.equal(r.provided,4);
assert.equal(r.pnl,-2100);
assert.equal(r.rows[0].relevance,.9,"must use MAX across source entity paths, not add priors");
assert.equal(r.rows[3].relevance,null,"unmapped != zero empirically measured sensitivity");
assert.equal(r.rows[3].pnl,-200,"short position P&L signs must be respected");
assert.equal(r.returnSource,"USER_ENTERED_ASSUMPTIONS_ONLY");
const noShock=A.calculate({holdings:[{ticker:"TSM",value:2000,shock:""}],
  scenarioId:"event:taiwan",graph});
assert.equal(noShock.provided,0);
assert.equal(noShock.rows[0].pnl,null,"no user return assumption cannot silently imply zero");
const unrelated=A.calculate({holdings:[{ticker:"TSM",value:2000,shock:0}],
  scenarioId:"event:funding",graph});
assert.equal(unrelated.score,0);
assert.equal(unrelated.coveredFraction,0);
assert.equal(unrelated.rows[0].relevance,null);
assert.equal(unrelated.provided,1,"explicitly entered 0% is different from missing");
for(const h of [{ticker:"DOESNOTEXIST",value:100},{ticker:"TSM",value:0},
                 {ticker:"TSM",value:100,shock:"hello"},{ticker:"TSM",value:100,shock:1001}]){
  const bad=A.calculate({holdings:[h],scenarioId:"event:taiwan",graph});
  assert.ok(bad.errors.length>0);
  assert.equal(bad.rows.length,0);
}
assert.deepEqual(A.calculate({holdings:[],scenarioId:"event:taiwan",graph}).rows,[]);
assert.ok(A.calculate({holdings:Array.from({length:101},()=>holdings[0]),
  scenarioId:"event:taiwan",graph}).errors.length);
const html=fs.readFileSync(path.join(__dirname,"../marco.html"),"utf8");
const frontend=fs.readFileSync(path.join(__dirname,"../assets/marco.js"),"utf8");
for(const text of ["Event Risk Graph","data-side=\"left\"","data-side=\"right\"",
  "Event Attribution","holdings-body","add-holding","event-choice","attribution-results",
  "assets/attribution-core.js","assets/marco.js","unpkg.com/vis-network@9.1.9"])
  assert.ok(html.includes(text),text);
assert.ok(frontend.includes("window.EventRiskAttribution.calculate"));
assert.ok(!frontend.includes("fetch('/api/v1/attribution"),"holdings must stay inside browser");
console.log("PREVIEW_MVP_MANUAL_HOLDINGS_ATTRIBUTION=PASS","portfolio_relevance",r.score,"what_if_pnl",r.pnl);
