"use strict";
/* Marco-style companion tabs. API remains authoritative; browser stores no database token.
   Session-scoped analyst key is reused by Explore, Attribution, Factor Research.
*/
(()=>{
const $=id=>document.getElementById(id);
const KEY="eventriskResearchAnalystKey";
const page=document.body.dataset.researchPage;
const state={catalog:null,nodes:[],selected:null};
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined&&text!==null)x.textContent=String(text);if(cls)x.className=cls;return x;};
const analyst=()=>{try{return sessionStorage.getItem(KEY)||""}catch(_){return ""}};
const fmt=v=>typeof v==="number"&&Number.isFinite(v)?(100*v).toFixed(1)+"%":"Not captured";
const num=v=>typeof v==="number"&&Number.isFinite(v)?v.toFixed(3):"—";
async function call(path,auth=false){
 const headers={};if(auth&&analyst())headers["X-Analyst-Key"]=analyst();
 const r=await fetch(path,{headers,cache:"no-store"});
 let json;try{json=await r.json()}catch(_){throw Error("Non-JSON response")}
 if(!r.ok)throw Error(json.error||"HTTP "+r.status);
 return json;
}
function access(){
 if(!$("access-status"))return;
 const key=analyst();
 $("access-status").textContent=key?"Analyst key available for this tab session. Data rights are checked on each request.":"Public reference mode; observed market/factor research requires an issued key and source authorization.";
}
function wireAccess(){
 $("save-key")?.addEventListener("click",()=>{
   const value=$("research-key").value.trim();
   if(value){try{sessionStorage.setItem(KEY,value)}catch(_){$("access-status").textContent="Session storage blocked";return}}
   $("research-key").value="";access();
 });
 $("clear-key")?.addEventListener("click",()=>{
   try{sessionStorage.removeItem(KEY)}catch(_){}
   $("research-key").value="";access();
 });
 access();
}
function renderQuotes(host,rows){
 if(!rows.length){host.append(el("p","No captured contracts connected to this reference in the current entitled graph.","subtle"));return;}
 for(const r of rows){
   const box=el("div",undefined,"result"),h=el("strong",r.contract_question||r.proposition_id);
   box.append(h);
   const m=el("p",(r.venue? r.venue+" · "+r.market_id+" · ":"")+
     "YES "+fmt(r.probability)+
     (typeof r.probability_delta_pp==="number"?
       " · "+(r.probability_delta_pp>=0?"+":"")+r.probability_delta_pp.toFixed(2)+" pp from previous capture":"")+
     " · observed "+(r.observed_at||"unknown"),"subtle");
   box.append(m);
   box.append(el("p",(r.question_name||"")+" · "+
     (r.relation_provenance||"research link")+" · source quote freshness unverified","subtle"));
   host.append(box);
 }
}
async function runLookup(){
 const id=$("node-select").value, host=$("exposure-results");
 host.replaceChildren();
 if(!id){host.append(el("p","Select a listed security, entity or factor.","subtle"));return}
 $("lookup-status").textContent="Finding event pathways…";
 try{
   const data=await call("/api/v1/reference/reverse?node_id="+encodeURIComponent(id));
   const h=el("h3",data.node.name);host.append(h);
   if(data.events.length){
     for(const e of data.events){
       const b=el("div",undefined,"result");b.append(el("strong",e.name));
       b.append(el("p","Path: "+e.path.join(" → "),"subtle"));
       b.append(el("p","Illustrative scenario; no verified captured event probability.","subtle"));
       host.append(b);
     }
   }else host.append(el("p","No reviewed event scenario is connected in the public reference graph.","subtle"));
   if(analyst()){
     const kind=data.node.type, mapped=kind==="security"?"sec:"+data.node.ticker:
       kind==="entity"&&id.startsWith("entity:Q")?"wd:"+id.slice(7):id;
     try{
       const real=await call("/api/v1/research/reverse?kind="+encodeURIComponent(kind)+
           "&node_id="+encodeURIComponent(mapped)+"&limit=40",true);
       host.prepend(el("h3","Entitled captured market contracts ("+real.rows.length+" returned)"));
       const section=el("div");renderQuotes(section,real.rows);host.prepend(section);
       $("lookup-status").textContent="Source quote snapshots loaded. No original venue-freshness or causal validation.";
     }catch(e){
       host.prepend(el("p","Recorded contract quotes restricted: "+e.message+
        ". A session key does not override provider rights.","subtle"));
       $("lookup-status").textContent="Public reference pathways loaded; contract quotes unavailable.";
     }
   }else{
      host.prepend(el("p","Enter an issued analyst key to request entitled captured contract quotes. Public hypotheses are not market predictions.","subtle"));
      $("lookup-status").textContent="Reference results loaded.";
   }
 }catch(e){host.append(el("p","Event lookup unavailable: "+e.message,"subtle"));$("lookup-status").textContent="Lookup failed";}
}
function setScenario(){
 const get=id=>Number($(id).value),p0=get("initial-prob"),p1=get("ending-prob"),yes=get("yes-value"),no=get("no-value");
 const out=$("scenario-result");
 if([p0,p1,yes,no].some(x=>!Number.isFinite(x))||p0<0||p0>100||p1<0||p1>100){
   out.textContent="Enter valid probabilities (0–100) and numeric valuations.";return;
 }
 const initial=p0/100*yes+(1-p0/100)*no,dV=(p1-p0)/100*(yes-no),change=initial!==0?dV/initial*100:NaN;
 out.textContent=(dV>=0?"+":"")+"$"+dV.toFixed(2)+" scenario value · "+
   (Number.isFinite(change)?(change>=0?"+":"")+change.toFixed(2)+"% vs initial value":"initial value zero");
}
async function attribution(){
 const d=await call("/api/v1/catalog");state.catalog=d;
 const a=d.securities.map(s=>({...s,type:"security",label:s.ticker+" · "+s.name})),
       b=d.factors.map(f=>({...f,type:"factor",label:f.name+" · "+f.factor_id})),
       c=(d.channels||[]).map(n=>({...n,type:"channel",label:n.name}));
 state.nodes=[...a,...b,...c];
 const dropdown=$("node-select");dropdown.replaceChildren();
 const list=$("exposure-list");
 for(const n of state.nodes){
   const opt=el("option",n.label);opt.value=n.id;dropdown.append(opt);
   const dat=el("option");dat.value=n.label;list.append(dat);
 }
 const choose=()=>{
   const text=$("lookup").value.toLowerCase().trim();
   if(!text)return;
   const best=state.nodes.find(x=>x.label.toLowerCase()===text)||
      state.nodes.find(x=>x.label.toLowerCase().startsWith(text))||
      state.nodes.find(x=>x.label.toLowerCase().includes(text));
   if(best)dropdown.value=best.id;
 };
 $("lookup").addEventListener("change",choose);
 $("lookup").addEventListener("keydown",e=>{if(e.key==="Enter"){choose();runLookup()}});
 $("lookup-run").addEventListener("click",runLookup);
 for(const id of ["initial-prob","ending-prob","yes-value","no-value"])
   $(id).addEventListener("input",setScenario);
 setScenario();
 const query=new URLSearchParams(location.search);
 if(query.get("node_id")){dropdown.value=query.get("node_id");runLookup();}
}
function buildTable(columns,rows){
 const tbl=el("table"),header=el("tr");
 for(const col of columns)header.append(el("th",col[1]));
 const thead=el("thead");thead.append(header);tbl.append(thead);
 const body=el("tbody");for(const row of rows){
   const tr=el("tr");for(const [key] of columns)tr.append(el("td",row[key]??"—"));body.append(tr);
 }tbl.append(body);return tbl;
}
function chart(host,rows){
 if(rows.length<2)return;
 const values=rows.map(r=>Number(r.value)).filter(Number.isFinite);
 if(values.length<2)return;
 const min=Math.min(...values),max=Math.max(...values),range=max-min||1;
 const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");
 svg.setAttribute("viewBox","0 0 760 260");svg.setAttribute("class","series-plot");
 svg.setAttribute("role","img");svg.setAttribute("aria-label","Source observed factor history");
 const points=rows.map((r,i)=>[30+i*700/Math.max(1,rows.length-1),230-(Number(r.value)-min)*190/range])
   .filter(p=>p.every(Number.isFinite));
 const poly=document.createElementNS(ns,"polyline");
 poly.setAttribute("points",points.map(p=>p.join(",")).join(" "));
 poly.setAttribute("fill","none");poly.setAttribute("stroke","currentColor");
 poly.setAttribute("stroke-width","2");svg.append(poly);host.append(svg);
 host.append(el("p","First: "+rows[0].observed_date+" · last: "+rows[rows.length-1].observed_date+
 " · range "+min.toFixed(3)+" to "+max.toFixed(3),"subtle"));
}
async function loadFactor(){
 const id=$("factor-id").value,host=$("factor-results");
 host.replaceChildren();$("series-status").textContent="Requesting source factor observations…";
 if(!analyst()){$("series-status").textContent="Enter an analyst key first; reference definitions remain public.";return}
 try{
   const d=await call("/api/v1/research/factor-series?factor_id="+encodeURIComponent(id)+"&limit=180",true);
   const rows=d.rows||[];
   $("series-status").textContent=rows.length+" observed dates returned · publisher-first-known timestamps NOT established.";
   chart(host,rows);
   host.append(buildTable([["observed_date","Observed date"],["value","Observed value"],["unit","Unit"],["available_at","Warehouse available at"]],rows.slice(-20).reverse()));
 }catch(e){$("series-status").textContent="Observed series unavailable: "+e.message+". No example numbers substituted."}
}
async function loadModel(){
 const ticker=$("ticker").value.trim().toUpperCase(),host=$("model-results");
 host.replaceChildren();
 if(!/^[A-Z0-9.=_-]{1,25}$/.test(ticker)){$("model-status").textContent="Invalid ticker";return}
 if(!analyst()){$("model-status").textContent="Enter an analyst key first.";return}
 $("model-status").textContent="Requesting independently audited regression diagnostics…";
 try{
   const d=await call("/api/v1/research/funding-diagnostics?ticker="+encodeURIComponent(ticker),true);
   const fits=d.fits||[];
   $("model-status").textContent=fits.length?fits.length+" source model variants; noncausal, unapproved.":"No recorded fitted model for "+ticker+".";
   host.append(buildTable([
      ["variant","Variant"],["market_spy_beta","SPY beta"],["dgs2_yield_change_beta","DGS2 beta"],
      ["dgs10_yield_change_beta","DGS10 beta"],["funding_basis_beta","Funding beta"],
      ["incremental_heldout_skill","Heldout skill"],["institutional_beta_released","Approved"]
   ],fits.map(f=>({...f,institutional_beta_released:f.institutional_beta_released?"Yes":"No"}))));
   for(const fit of fits)host.append(el("p",fit.variant+
     " · Holm adjusted p: "+num(fit.familywise?.holm_familywise_p)+
     " · issuer point-in-time verified: "+String(fit.issuer_pit_verified),"subtle"));
 }catch(e){$("model-status").textContent="Regression unavailable: "+e.message+". No estimated coefficients substituted."}
}
async function factorResearch(){
 const select=$("factor-id");
 const pre=[["DGS2","2Y U.S. Treasury yield"],["DGS10","10Y U.S. Treasury yield"],
   ["DGS5","5Y U.S. Treasury yield"],["DGS10R","10Y real rate"],
   ["PAR_NOMINAL_REAL_GAP_10Y","10Y nominal-real yield gap"],["T10YIE","10Y breakeven inflation"]];
 const setOpts=items=>{select.replaceChildren();for(const [id,name] of items){
   const x=el("option",id+" · "+name);x.value=id;select.append(x);
 }};
 setOpts(pre);
 $("catalog-note").textContent="Public starter list · the full warehouse catalog requires analyst access.";
 if(analyst()){try{
    const d=await call("/api/v1/research/factor-catalog",true);
    const items=(d.rows||[]).map(r=>[r.factor_id,r.name+(r.active?"":" · series inactive")]);
    if(items.length){setOpts(items);$("catalog-note").textContent=items.length+" source warehouse factor definitions (not all observed)."}
 }catch(e){$("catalog-note").textContent="Warehouse catalog restricted: "+e.message}}
 $("load-factor").addEventListener("click",loadFactor);
 $("load-model").addEventListener("click",loadModel);
 $("ticker").addEventListener("keydown",e=>{if(e.key==="Enter")loadModel()});
}
document.addEventListener("DOMContentLoaded",async()=>{
 wireAccess();
 try{if(page==="attribution")await attribution();else if(page==="factors")await factorResearch();}
 catch(e){if($("lookup-status"))$("lookup-status").textContent=e.message;
          if($("catalog-note"))$("catalog-note").textContent="Catalog could not load: "+e.message;}
});
})();