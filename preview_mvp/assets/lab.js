"use strict";
/* Analyst Research Desk — public qualitative case paths, restricted quantitative evidence.
   NEVER fill missing source betas, p-values or factor observations with examples. */
(function(){
  const $=id=>document.getElementById(id);
  const element=(tag,text,klass)=>{
    const n=document.createElement(tag);
    if(text!==undefined&&text!==null)n.textContent=String(text);
    if(klass)n.className=klass;
    return n;
  };
  const state={graph:null,catalog:null,runtime:null,
    key:window.sessionStorage.getItem("eventrisk_analyst_key")||"",
    caseId:"inflation",loadedModels:[],loadedSeries:[],loadedFactor:null,
    fetchedModelTicker:null};
  const CASES={
    inflation:{event:"event:inflation",headline:"Inflation release & monetary policy",
      description:"Potential interpretation of inflation data through expectations, the policy curve and the equity discount rate. There is no verified actual-minus-consensus economic surprise in this case."},
    funding:{event:"event:funding",headline:"Money-market funding stress",
      description:"Funding basis and dealer balance-sheet liquidity may correlate with Treasury returns and equity risk appetite. The available 48-security funding-model family is historical and noncausal."},
    taiwan:{event:"event:taiwan",headline:"Taiwan semiconductor supply-chain disruption",
      description:"Hypothetical Taiwan scenario connecting production capacity, trade costs and capital-market discount rates. Source security links describe analyst prior relevance, not forecastable event returns."},
    trade:{event:"event:trade",headline:"Cross-border trade restrictions",
      description:"Potential tariff pass-through, corporate costs, bilateral currencies and sector demand. Actual event announcements are not verified by this illustrative scenario."},
    oil:{event:"event:oil",headline:"Oil supply disruption",
      description:"Potential commodity price pass-through into inflation, the energy sector and credit conditions. No realized event probability or modeled event shock."},
    rates:{event:"event:rates",headline:"Monetary-policy repricing",
      description:"Possible shift in expected central-bank rate path and Treasury curve, with credit and housing financing implications."},
    chips:{event:"event:chips",headline:"Semiconductor export restrictions",
      description:"Potential chip sales, supplier restrictions and national industrial-policy exposure. Hypothetical scenario; source security priors are unreviewed."},
    defense:{event:"event:defense",headline:"Regional conflict escalation",
      description:"Potential risk appetite, government expenditure, energy disruption and funding response. No verified war-event probability, contemporaneous identification or sign-validated coefficient."}
  };
  const fmtNum=(v,d=3)=>{
    if(v===null||v===undefined||v===""||!Number.isFinite(Number(v)))return "—";
    return Number(v).toLocaleString("en-US",{maximumFractionDigits:d,minimumFractionDigits:0});
  };
  const errText=e=>e instanceof Error?e.message:String(e);
  async function request(path){
    const r=await fetch(path,{cache:"no-store",headers:{"X-Analyst-Key":state.key}});
    let data;
    try{data=await r.json();}catch(_){throw Error("Invalid source response");}
    if(!r.ok)throw Error(data.error||"Research API HTTP "+r.status);
    return data;
  }
  function displayStatus(id,msg){
    const box=$(id);box.textContent=msg;box.hidden=false;
  }
  function card(tag,caption,children){
    const c=element("div",undefined,"pathway");
    c.append(element("small",tag),element("b",caption));
    if(children?.length){
      const list=element("div",undefined,"factor-list");
      for(const v of children.slice(0,8))list.append(element("span",v));
      if(children.length>8)list.append(element("span","+"+(children.length-8)+" more related definitions"));
      c.append(list);
    }
    return c;
  }
  function renderCase(){
    const def=CASES[state.caseId],g=state.graph;
    if(!g||!def)return;
    $("case-title").textContent=def.headline;
    $("case-description").textContent=def.description;
    const edgeTypes=g.edges.filter(e=>e.src===def.event);
    const channelIds=edgeTypes.filter(e=>e.type==="hypothetical_transmission").map(e=>e.dst);
    const entityIds=edgeTypes.filter(e=>e.type==="hypothetical_involves").map(e=>e.dst);
    const byId=new Map(g.nodes.map(n=>[n.id,n]));
    const flows=$("pathways");flows.replaceChildren();
    flows.append(card("01 · ILLUSTRATIVE SCENARIO",def.headline));
    const allFactors=new Map();
    for(const channelId of channelIds){
      const channel=byId.get(channelId);if(!channel)continue;
      const factors=g.edges.filter(e=>e.src===channelId&&e.type==="hypothetical_factor_channel")
        .map(e=>byId.get(e.dst)).filter(Boolean);
      for(const f of factors)allFactors.set(f.id,f.name);
      flows.append(card("02 · UNREVIEWED ECONOMIC CHANNEL",channel.name,
        factors.slice(0,4).map(f=>f.name)));
    }
    flows.append(card("03 · QUALITATIVE FACTOR DEFINITIONS",
      allFactors.size+" relevant factor definitions",
      [...allFactors.values()].slice(0,9)));
    const securityEdges=g.edges.filter(e=>entityIds.includes(e.src)&&e.type==="research_exposure_prior")
      .sort((a,b)=>(b.weight||0)-(a.weight||0));
    const securityList=$("related-securities");securityList.replaceChildren();
    const visited=new Set();
    for(const e of securityEdges){
      const sec=byId.get(e.dst);
      if(!sec||visited.has(sec.id))continue;
      visited.add(sec.id);
      const b=element("button",sec.ticker+" · "+fmtNum(e.weight,2)+" prior");
      b.title="Analyst-prior source relevance, NOT an expected return sensitivity";
      b.type="button";
      b.addEventListener("click",()=>{
        $("ticker").value=sec.ticker;
        document.getElementById("model-panel").scrollIntoView({behavior:"smooth",block:"start"});
      });
      securityList.append(b);
      if(visited.size>=40)break;
    }
    if(!securityList.childNodes.length){
      securityList.append(element("p","No direct source seed security exposure for this case; its factor links are illustrative only.","helper"));
    }
  }
  function numberCell(tr,v,d=3){
    const td=element("td",fmtNum(v,d));
    tr.append(td);
    return td;
  }
  function renderModels(doc){
    const fits=doc.fits||[];
    const body=$("model-body");body.replaceChildren();
    $("model-data").hidden=false;
    $("model-status").hidden=true;
    state.loadedModels=fits;
    state.fetchedModelTicker=doc.ticker;
    $("model-headline").textContent=fits.length?
      "Observed historical model: "+doc.ticker+" · "+fits.length+
      " source variant(s) · No approved event-impact beta":
      "No source regression fitted for "+doc.ticker+". Unfitted companies are not imputed.";
    for(const fit of fits){
      const family=fit.familywise||{};
      const tr=element("tr");
      tr.append(element("td",fit.variant||"Unknown model variant"));
      numberCell(tr,fit.market_spy_beta,4);
      numberCell(tr,fit.dgs2_yield_change_beta,4);
      numberCell(tr,fit.dgs10_yield_change_beta,4);
      numberCell(tr,fit.funding_basis_beta,4);
      tr.append(element("td","["+fmtNum(fit.funding_ci95_low,4)+", "+fmtNum(fit.funding_ci95_high,4)+"]"));
      numberCell(tr,family.holm_familywise_p,4);
      numberCell(tr,fit.incremental_heldout_skill,4);
      const release=element("td",fit.institutional_beta_released===true?"APPROVED":"RESEARCH ONLY",
                            fit.institutional_beta_released===true?"":"warning");
      tr.append(release);body.append(tr);
    }
    $("model-foot").textContent=doc.research_warning+" Latest observed model builds are source versioned. "+
      "Full sample and chronological holdout windows are shown in the JSON; the latest global familywise adjustment applies to 96 related fits. "+
      "A nominal p-value is not independent causal validation or source rights.";
  }
  function drawSeries(doc){
    const data=(doc.rows||[]).filter(x=>x.observed_date&&Number.isFinite(Number(x.value)));
    const canvas=$("factor-chart"),ctx=canvas.getContext("2d");
    if(!ctx)return;
    const w=canvas.width,h=canvas.height;
    ctx.clearRect(0,0,w,h);
    ctx.fillStyle="#fafcfc";ctx.fillRect(0,0,w,h);
    if(data.length<2){ctx.fillStyle="#506367";ctx.font="14px system-ui";ctx.fillText("Not enough observed points to plot.",20,35);return;}
    const xs=data.map(x=>String(x.observed_date));
    const vs=data.map(x=>Number(x.value));
    const min=Math.min(...vs),max=Math.max(...vs),pad=Math.max((max-min)*.14,.001);
    const lo=min-pad,hi=max+pad,x0=65,x1=w-25,y0=25,y1=h-43;
    ctx.strokeStyle="#d5dfe0";ctx.lineWidth=1;ctx.font="12px system-ui";ctx.fillStyle="#6c8288";ctx.textAlign="right";
    for(let i=0;i<=4;i++){
      const y=y1-(y1-y0)*i/4,value=lo+(hi-lo)*i/4;
      ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.stroke();
      ctx.fillText(fmtNum(value,3),x0-9,y+4);
    }
    ctx.textAlign="center";ctx.fillText(xs[0],x0,y1+25);ctx.fillText(xs[Math.floor(xs.length/2)],(x0+x1)/2,y1+25);ctx.fillText(xs[xs.length-1],x1,y1+25);
    ctx.strokeStyle="#247b75";ctx.lineWidth=2;ctx.beginPath();
    vs.forEach((v,i)=>{
      const x=x0+(x1-x0)*(i/Math.max(1,vs.length-1));
      const y=y1-(y1-y0)*(v-lo)/(hi-lo);
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
    });
    ctx.stroke();
    ctx.fillStyle="#247b75";ctx.beginPath();
    const last=vs[vs.length-1],lastY=y1-(y1-y0)*(last-lo)/(hi-lo);
    ctx.arc(x1,lastY,4,0,Math.PI*2);ctx.fill();
  }
  function renderSeries(doc){
    state.loadedSeries=doc.rows||[];state.loadedFactor=doc.factor_id;
    $("factor-data").hidden=false;$("factor-status").hidden=true;
    const data=state.loadedSeries;
    $("chart-meta").textContent=doc.factor_id+" · "+data.length+
      " observations · "+(data.length?data[0].observed_date+" to "+data[data.length-1].observed_date:"no dates")+
      " · Source availability is NOT original provider first release";
    drawSeries(doc);
  }
  async function runModels(){
    const ticker=$("ticker").value.trim().toUpperCase();
    if(!/^[A-Z0-9.=_-]{1,25}$/.test(ticker)){displayStatus("model-status","Enter a valid security ticker.");return;}
    $("model-data").hidden=true;
    displayStatus("model-status","Requesting source regressions for "+ticker+"...");
    try{
      const data=await request("/api/v1/research/funding-diagnostics?ticker="+encodeURIComponent(ticker));
      if(data.mode!=="NONCAUSAL_FUNDING_REGRESSION_DIAGNOSTICS"||data.approved_event_impact!==false)
        throw Error("Unexpected or unauthorized regression approval status");
      renderModels(data);
    }catch(e){
      state.loadedModels=[];state.fetchedModelTicker=null;
      displayStatus("model-status","Regression unavailable: "+errText(e)+
        ". A scoped server-side MotherDuck credential, an analyst key, and derived research rights are required.");
    }
  }
  async function loadFactor(){
    const id=$("factor").value;
    $("factor-data").hidden=true;
    displayStatus("factor-status","Requesting source-observed factor series for "+id+"...");
    try{
      const data=await request("/api/v1/research/factor-series?factor_id="+encodeURIComponent(id)+"&limit=250");
      if(data.mode!=="SOURCE_OBSERVED_DATE_RESEARCH_NOT_PROVIDER_ORIGINAL_PIT"||data.no_first_publication_claim!==true)
        throw Error("Unexpected source publication status");
      renderSeries(data);
    }catch(e){
      state.loadedSeries=[];state.loadedFactor=null;
      displayStatus("factor-status","Factor history unavailable: "+errText(e)+
        ". The warehouse connection and derived-data entitlement must be enabled.");
    }
  }
  function csvQuote(s){
    const v=String(s===null||s===undefined?"":s);
    return /[,"\n\r]/.test(v)?'"'+v.replaceAll('"','""')+'"':v;
  }
  function exportLoaded(){
    const lines=[["record_type","case","id","field","value","source_status"]];
    for(const [id,model] of state.loadedModels.entries())
      for(const [field,value] of Object.entries(model)){
        if(field==="familywise"){
          for(const [key,v] of Object.entries(value))
            lines.push(["funding_familywise",state.caseId,state.fetchedModelTicker+"/"+id,key,v,"NONCAUSAL_RESEARCH_ONLY"]);
        }else lines.push(["funding_regression",state.caseId,state.fetchedModelTicker+"/"+id,field,value,"NONCAUSAL_RESEARCH_ONLY"]);
      }
    for(const point of state.loadedSeries)
      lines.push(["factor_observation",state.caseId,state.loadedFactor,point.observed_date,point.value,"SOURCE_DATE_NOT_ORIGINAL_FIRST_RELEASE"]);
    if(lines.length===1){
      $("auth-message").textContent="No source results loaded. Export is disabled until a permitted regression or factor series is retrieved.";
      return;
    }
    const file=new Blob([lines.map(row=>row.map(csvQuote).join(",")).join("\r\n")+"\r\n"],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(file);
    const a=element("a");a.href=url;a.download="eventrisk-preview-mvp-research-"+state.caseId+".csv";
    document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
  }
  async function init(){
    $("case").addEventListener("change",e=>{state.caseId=e.target.value;renderCase();});
    $("run-regression").addEventListener("click",runModels);
    $("load-series").addEventListener("click",loadFactor);
    $("set-key").addEventListener("click",()=>{
      const value=$("key").value.trim();
      if(!value){$("auth-message").textContent="No key entered; source queries remain locked.";return;}
      state.key=value;window.sessionStorage.setItem("eventrisk_analyst_key",value);
      $("key").value="";$("auth-message").textContent="Key saved only for this browser tab. No database credential is exposed; source permission remains independent.";
    });
    $("export").addEventListener("click",exportLoaded);
    $("print").addEventListener("click",()=>window.print());
    try{
      const [catalog,graph,runtime]=await Promise.all([
        request("/api/v1/catalog"),request("/api/v1/graph"),request("/api/v1/runtime")]);
      if(catalog.factors_count!==108||catalog.securities_count<500||
         graph.mode!=="PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE")throw Error("Unexpected catalog source state");
      state.catalog=catalog;state.graph=graph;state.runtime=runtime;
      $("security-count").textContent=catalog.securities_count.toLocaleString("en-US");
      $("factor-count").textContent=catalog.factors_count;
      $("channel-count").textContent=catalog.channels.length;
      $("warehouse-connection").textContent=runtime.direct_database_queries_enabled?"Configured*":"Setup required";
      $("status").textContent=runtime.direct_database_queries_enabled?"WAREHOUSE KEY CONFIGURED*":"WAREHOUSE SETUP REQUIRED";
      for(const sec of catalog.securities){
        const option=element("option");option.value=sec.ticker;
        option.label=sec.name;
        $("ticker-choices").append(option);
      }
      renderCase();
    }catch(e){
      displayStatus("case-description","Public source catalog unavailable: "+errText(e));
      $("status").textContent="SOURCE ERROR";
    }
  }
  document.addEventListener("DOMContentLoaded",init);
})();
