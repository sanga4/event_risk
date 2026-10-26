"use strict";
/* Marco original UI layout + EventRisk Research source contracts.
 * All holding inputs and scenario return assumptions remain in this tab.
 * Scores = gross weights x source analyst-prior relevance, NOT causal impact.
 */
(function () {
  const $=q=>document.querySelector(q);
  const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const fmt=new Intl.NumberFormat("en-US",{maximumFractionDigits:2});
  const usd=new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:2});
  const TYPES={event:"question",question:"question",entity:"entity",security:"security",
              factor:"factor",channel:"channel"};
  const COLORS={event:"--question",question:"--question",entity:"--entity",security:"--security",
                factor:"--factor",channel:"--channel"};
  const SHAPES={event:"dot",question:"dot",entity:"diamond",security:"square",
                factor:"hexagon",channel:"box"};
  const state={catalog:null,graph:null,byId:new Map(),adj:new Map(),selected:null,
               tab:"questions",key:"",sourceQuestions:[],sourceOffset:0,
               holdings:[],nextHoldingId:1,lastAttribution:[],network:null,expanded:false};
  const CASES={
    "event:inflation":"Potential interpretation of macro inflation data through inflation expectations and monetary policy. No original verified surprise or return-effect estimate.",
    "event:funding":"Funding basis, liquidity and credit channels. Funding coefficients in the separate lab are historical associations, not event-response magnitudes.",
    "event:taiwan":"Hypothetical Taiwan supply-chain disruption, with original repository analyst-prior security relationships.",
    "event:trade":"Illustrative cross-border restrictions, revenues, tariffs, currencies and financial conditions.",
    "event:oil":"Hypothetical energy supply disruption and commodity pass-through; not a recorded current event.",
    "event:rates":"Illustrative policy-path and Treasury repricing; no verified announcement vintage.",
    "event:chips":"Hypothetical export controls and semiconductor supply; no direct identified security-return effect.",
    "event:defense":"Hypothetical conflict escalation; no estimated probability, event price shock or security beta."
  };
  const el=(tag,text,klass)=>{
    const n=document.createElement(tag);if(klass)n.className=klass;
    if(text!==undefined&&text!==null)n.textContent=String(text);return n;
  };
  const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const cleanTicker=x=>String(x||"").trim().toUpperCase();
  function setMessage(q,message){$(q).textContent=message;}
  function neighbors(id){
    return (state.adj.get(id)||[]).map(e=>({
      edge:e,other:e.src===id?e.dst:e.src
    }));
  }
  function rebuildGraphIndex(){
    state.byId=new Map(state.graph.nodes.map(n=>[n.id,n]));
    state.adj=new Map();
    for(const e of state.graph.edges){
      if(!state.byId.has(e.src)||!state.byId.has(e.dst)||
         e.review_status!=="RESEARCH_ONLY_NOT_APPROVED")
        throw Error("Graph endpoints or research status invalid");
      for(const id of [e.src,e.dst]){
        if(!state.adj.has(id))state.adj.set(id,[]);
        state.adj.get(id).push(e);
      }
    }
  }
  function getView(){return document.body.className.replace("view-","");}
  function changeView(view){
    if(!["explore","attribution","about","api"].includes(view))return;
    document.body.className="view-"+view;
    document.querySelectorAll("nav [data-view]").forEach(b=>b.setAttribute("aria-selected",String(b.dataset.view===view)));
    if(view==="attribution")calculate();
    if(view==="explore" && state.network)requestAnimationFrame(()=>state.network.redraw());
    window.scrollTo(0,0);
  }
  function filterList(){
    const q=$("#search").value.trim().toLowerCase();
    const type={questions:"event",markets:"question",entities:"entity",
               securities:"security",factors:"factor",channels:"channel"}[state.tab]||"event";
    let matches=state.graph.nodes.filter(n=>n.type===type);
    if(type==="question")matches=state.sourceQuestions;
    if(q)matches=matches.filter(n=>[n.name,n.ticker,n.subtitle,n.description].some(s=>String(s||"").toLowerCase().includes(q)));
    if(type==="security")matches.sort((a,b)=>(a.ticker||"").localeCompare(b.ticker||""));
    if(type==="factor")matches.sort((a,b)=>(a.subtitle||"").localeCompare(b.subtitle||"")||a.name.localeCompare(b.name));
    const list=$("#list");list.replaceChildren();
    if(!matches.length){
      const li=el("li",type==="question"?
        "Live research questions require separately authorized MotherDuck source access. Enter an issued analyst key below; protected sources may still be unavailable.":"No matching references.");
      li.style.display="block";li.style.cursor="default";list.append(li);
    }
    for(const n of matches.slice(0,400)){
      const li=el("li");li.dataset.id=n.id;li.tabIndex=0;
      if(state.selected===n.id)li.setAttribute("aria-current","true");
      li.append(el("i",null,"swatch "+(TYPES[n.type]||"entity")));
      li.append(el("span",(n.ticker?n.ticker+" · ":"")+n.name,"name"));
      li.append(el("span",n.type==="factor"?(n.subtitle||"catalog"):
        n.type==="security"?(n.subtitle||""):(n.type==="event"?"scenario":"research"),"num"));
      li.addEventListener("click",()=>select(n.id));
      li.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();select(n.id);}});
      list.append(li);
    }
    let caption=(q?matches.length+" matching":"Showing "+Math.min(400,matches.length)+" of "+matches.length)+
      " "+state.tab+" in local reference catalog.";
    if(type==="question")caption="Live source question access gated. "+matches.length+
      " source questions loaded in this session; no publisher-original PIT certification.";
    $("#list-status").firstChild.textContent=caption+" ";
  }
  function viewNodeType(n){return n.type==="question"?"Source question":n.type==="event"?"Scenario":n.type==="security"?"Security":n.type==="channel"?"Economic channel":n.type==="factor"?"Factor definition":"Reference entity";}
  function graphNeighborhood(root,depth){
    const seen=new Map([[root,0]]);let frontier=[root];
    for(let d=1;d<=depth&&frontier.length;d++){
      const following=[];
      for(const id of frontier)for(const edge of neighbors(id)){
        if(!seen.has(edge.other)){seen.set(edge.other,d);following.push(edge.other);}
      }
      frontier=following;
    }
    const limits=state.expanded?
      {event:4,question:8,entity:7,security:22,channel:8,factor:18}:
      {event:3,question:4,entity:3,security:6,channel:4,factor:5};
    const strength=id=>Math.max(0,...neighbors(id).map(x=>Number(x.edge.weight)||0));
    const selected=new Map([[root,0]]);
    for(const [type,max] of Object.entries(limits)){
      const candidates=[...seen].filter(([id])=>id!==root&&state.byId.get(id)?.type===type);
      candidates.sort((a,b)=>a[1]-b[1]||strength(b[0])-strength(a[0])||a[0].localeCompare(b[0]));
      for(const [id,d] of candidates.slice(0,max))selected.set(id,d);
    }
    return selected;
  }
  function renderNetwork(id){
    const network=state.network;
    if(!network)return;
    const depth=Number($("#depth").value)||2;
    const distances=graphNeighborhood(id,depth);
    const showFactors=$("#show-factors").checked;
    for(const key of distances.keys()){
      if(!showFactors&&state.byId.get(key)?.type==="factor"&&key!==id)distances.delete(key);
    }
    const nodes=[...distances].map(([key,d])=>{
      const n=state.byId.get(key),typ=n.type;
      const display=typ==="security"?(n.ticker||n.name):n.name;
      const label=display.length>26?display.slice(0,25)+"…":display;
      const tinted=typ==="channel"||typ==="factor";
      const color=css(COLORS[typ]||"--muted");
      return {id:key,label,level:d,shape:tinted?"box":(SHAPES[typ]||"dot"),
        size:key===id?19:typ==="security"?12:9,
        margin:tinted?8:4,
        color:{background:tinted?css("--surface"):color,
          border:key===id?css("--ink"):color},
        borderWidth:key===id?2:1.4,
        font:{size:typ==="security"?13:11,color:css("--ink"),
              strokeWidth:tinted?0:3,strokeColor:css("--surface")},
        title:n.name+"\n"+viewNodeType(n)+"\n"+(n.review_status||"")};
    });
    const links=state.graph.edges.filter(e=>distances.has(e.src)&&distances.has(e.dst)).map((e,i)=>({
      id:"e"+i,from:e.src,to:e.dst,width:0.5+Math.min(Number(e.weight)||.3,1),
      dashes:e.type!=="research_exposure_prior",
      color:{color:css("--axis"),opacity:.55,highlight:css("--ink-2")},
      title:e.type+(e.weight!==undefined?" · "+fmt.format(e.weight)+" analyst-prior relevance":"")+
        "\n"+(e.summary||"Unreviewed connection")
    }));
    network.setOptions({physics:false,layout:{hierarchical:{
      enabled:true,direction:"LR",sortMethod:"directed",levelSeparation:170,
      nodeSpacing:82,treeSpacing:90,blockShifting:true,edgeMinimization:true}},
      edges:{smooth:{enabled:true,type:"cubicBezier",forceDirection:"horizontal",roundness:.4}}});
    network.setData({nodes,edges:links});
    $("#empty").hidden=true;
    $("#caption").hidden=false;
    $("#caption").textContent=nodes.length+" nodes · "+links.length+
      " research links · dashed = illustrative, not validated causal impact";
  }
  function detail(id){
    const n=state.byId.get(id),host=$("#detail");host.replaceChildren();
    if(window.innerWidth<=650){
      const close=el("button","Close details ↓","mobile-detail-dismiss");
      close.type="button";
      close.addEventListener("click",()=>document.body.classList.remove("mobile-detail-open"));
      host.append(close);
    }
    if(!n)return;
    host.append(el("div",viewNodeType(n),"kind"),el("h2",n.name));
    if(n.subtitle)host.append(el("p",n.subtitle,"note"));
    const note=n.description||CASES[n.id]||
      "Source-reference research relationship; no quantitative event effect is estimated.";
    host.append(el("p",note,"row"));
    const status=el("p","Source / research status: "+(n.review_status||"Unreviewed"),"note");
    host.append(status);
    if(n.type==="event"){
      const b=el("button","Analyze holdings for this event","mini-btn");b.type="button";
      b.addEventListener("click",()=>{$("#event-choice").value=id;changeView("attribution");});host.append(b);
    }
    if(n.type==="security"){
      const b=el("button","Add to Event Attribution","mini-btn");b.type="button";
      b.addEventListener("click",()=>{addHolding(n.ticker||id.slice("security:".length),"","");changeView("attribution");});
      const a=el("a","Historical regression research →");a.href="/lab?ticker="+encodeURIComponent(n.ticker||"");a.className="detail-link";
      host.append(b,a);
    }
    if(n.type==="factor"){
      const a=el("a","Explore source-observed factor history →");a.href="/lab";a.className="detail-link";host.append(a);
    }
    const ns=neighbors(id).slice().sort((a,b)=>(b.edge.weight||0)-(a.edge.weight||0));
    if(n.type!=="event"){
    host.append(el("h3","Related nodes ("+ns.length+")"));
    if(!ns.length)host.append(el("p","No directly linked source references. This does not prove zero actual financial exposure.","note"));
    for(const {edge,other} of ns.slice(0,35)){
      const dest=state.byId.get(other);if(!dest)continue;
      const b=el("button",dest.name,"detail-link");b.type="button";
      const m=el("div",edge.type.replaceAll("_"," ")+
        (edge.weight!=null?" · "+fmt.format(edge.weight)+" source prior":"")+
        " · unapproved research","meta");
      b.append(m);b.addEventListener("click",()=>select(other));host.append(b);
    }
    if(ns.length>35)host.append(el("p","+"+(ns.length-35)+" other links; use graph API for research topology.","note"));
    }
    if(n.type==="event"){
      const entityIds=new Set(scenarioEntities(id));
      const candidates=state.graph.edges.filter(e=>
        e.type==="research_exposure_prior"&&entityIds.has(e.src)&&
        e.review_status==="RESEARCH_ONLY_NOT_APPROVED"
      ).sort((a,b)=>(b.weight||0)-(a.weight||0));
      const seen=new Set(),companies=[];
      for(const edge of candidates){
        if(seen.has(edge.dst))continue;
        seen.add(edge.dst);
        const sec=state.byId.get(edge.dst);
        if(sec?.type==="security")companies.push({edge,sec});
      }
      host.append(el("h3","Related securities · source priors ("+companies.length+")"));
      if(!companies.length)host.append(el("p",
        "No direct source-entity prior for this scenario. Open Event Attribution for unweighted sector/country watchlist screening.","note"));
      for(const {edge,sec} of companies.slice(0,6)){
        const b=el("button",(sec.ticker||"")+" · "+sec.name,"detail-link");
        b.type="button";
        b.append(el("div",fmt.format(edge.weight)+" qualitative analyst prior; NOT a return beta","meta"));
        b.addEventListener("click",()=>select(sec.id));
        host.append(b);
      }
      if(companies.length>6)host.append(el("p","+"+(companies.length-6)+" more source-linked securities. Filter by company or open Event Attribution.","note"));
      const relatedFactors=scenarioPaths(id).factors.map(fid=>state.byId.get(fid)).filter(Boolean);
      host.append(el("h3","Related financial factor definitions ("+relatedFactors.length+")"));
      for(const factor of relatedFactors.slice(0,4)){
        const b=el("button",factor.name,"detail-link");b.type="button";
        b.append(el("div",factor.subtitle||"Catalog definition; historical coverage varies","meta"));
        b.addEventListener("click",()=>select(factor.id));host.append(b);
      }
      if(relatedFactors.length>4)host.append(el("p","+"+(relatedFactors.length-4)+" additional factors in the research catalog.","note"));
      const expand=el("button","Show securities & factors in graph (depth 2)","mini-btn");expand.type="button";
      expand.addEventListener("click",()=>{
        state.expanded=true;$("#graph-toggle").textContent="Focus graph";$("#graph-toggle").setAttribute("aria-pressed","true");
        $("#depth").value="2";renderNetwork(id);
        if(window.innerWidth<=650)document.body.classList.remove("mobile-detail-open");
      });
      host.append(expand);
    }
    const meta=el("details");meta.append(el("summary","Evidence & methodology"));
    meta.append(el("p",n.source||"Published reference catalog · unreviewed research hypothesis","detail-source"));
    meta.append(el("p","Connections are hypotheses or analyst priors, never causal event impact, return direction or approved security beta.","note"));
    host.append(meta);
  }
  async function select(id,openMobile=true){
    if(!state.byId.has(id))return;
    state.selected=id;
    filterList();renderNetwork(id);detail(id);
    if(openMobile&&window.innerWidth<=650){
      document.body.classList.remove("mobile-list-open");
      document.body.classList.add("mobile-detail-open");
      $("#browse-mobile").setAttribute("aria-expanded","false");
    }
    const n=state.byId.get(id);
    if(n.liveWarehouse&&n.type==="question")await fetchNeighbors(id);
  }
  function insertLiveNode(x){
    if(!x?.node_id||state.byId.has(x.node_id))return;
    const srcType=x.node_type||"question";
    const type=["question","security","factor","entity"].includes(srcType)?srcType:"question";
    const n={id:String(x.node_id),name:String(x.name||x.node_id),type,
      description:"Source-recorded warehouse question or reference; original provider event publication/PIT and legal rights not independently certified.",
      review_status:"LIVE_SOURCE_RESEARCH_NOT_APPROVED",liveWarehouse:true};
    state.byId.set(n.id,n);state.graph.nodes.push(n);
  }
  function researchHeaders(){return {"X-Analyst-Key":state.key};}
  async function fetchNeighbors(id){
    setMessage("#access-status","Checking permissioned live question neighbors…");
    try{
      const r=await fetch("/api/v1/research/graph-neighbors?node_id="+encodeURIComponent(id),
        {headers:researchHeaders(),cache:"no-store"});
      const d=await r.json();if(!r.ok)throw Error(d.error||"HTTP "+r.status);
      for(const n of d.nodes||[])insertLiveNode(n);
      const signatures=new Set(state.graph.edges.map(e=>e.src+"|"+e.dst+"|"+e.type));
      for(const e of d.edges||[]){
        if(!state.byId.has(e.src_id)||!state.byId.has(e.dst_id))continue;
        const k=e.src_id+"|"+e.dst_id+"|"+e.edge_type;
        if(signatures.has(k))continue;signatures.add(k);
        state.graph.edges.push({src:e.src_id,dst:e.dst_id,type:e.edge_type,
          weight:e.weight,summary:e.note||e.provenance||"",
          review_status:"RESEARCH_ONLY_NOT_APPROVED"});
      }
      rebuildGraphIndex();renderNetwork(id);detail(id);
      setMessage("#access-status",(d.edges||[]).length+" live source research relations loaded (not approved impacts).");
    }catch(e){setMessage("#access-status","Source graph remains restricted: "+e.message);}
  }
  async function searchSourceQuestions(reset=true){
    if(reset){state.sourceQuestions=[];state.sourceOffset=0;}
    const q=$("#search").value.trim();
    setMessage("#access-status","Requesting warehouse source questions…");
    try{
      const url="/api/v1/research/events?q="+encodeURIComponent(q)+"&offset="+state.sourceOffset+"&limit=50";
      const r=await fetch(url,{headers:researchHeaders(),cache:"no-store"});
      const d=await r.json();if(!r.ok)throw Error(d.error||"HTTP "+r.status);
      for(const row of d.rows||[]){
        insertLiveNode({...row,node_type:"question"});
        const n=state.byId.get(row.node_id);
        if(n&&!state.sourceQuestions.some(x=>x.id===n.id))state.sourceQuestions.push(n);
      }
      state.sourceOffset+=(d.rows||[]).length;
      rebuildGraphIndex();filterList();
      setMessage("#access-status",state.sourceQuestions.length+
        " permitted source questions loaded; not independently point-in-time certified.");
    }catch(e){
      setMessage("#access-status","Source questions unavailable: "+e.message+
        ". Separate issuer key, MotherDuck SELECT access and venue redisplay rights required.");
      filterList();
    }
  }

  // ── MANUALLY ENTERED HOLDINGS / RESEARCH-ONLY EVENT ATTRIBUTION ─────────
  function newPosition(ticker="",value="",shock=""){
    return {id:state.nextHoldingId++,ticker:String(ticker),value:String(value),shock:String(shock)};
  }
  function addHolding(ticker="",value="",shock=""){
    if(state.holdings.length>=100){
      setMessage("#portfolio-privacy","Maximum 100 manually entered positions per browser tab.");return;
    }
    state.holdings.push(newPosition(ticker,value,shock));renderHoldings();calculate();
  }
  function renderHoldings(){
    const body=$("#holdings-body");body.replaceChildren();
    if(!state.holdings.length){const tr=el("tr");const td=el("td","No holdings entered. Add a row or load clearly marked demo holdings.");td.colSpan=4;tr.append(td);body.append(tr);return;}
    for(const h of state.holdings){
      const tr=el("tr");
      for(const [key,cls,placeholder] of [
        ["ticker","ticker-input","e.g. TSM"],["value","money-input","e.g. 25000"],["shock","shock-input","Optional ± %"]]){
        const td=el("td"),input=el("input");input.className=cls;input.value=h[key];input.placeholder=placeholder;
        input.setAttribute("aria-label",key==="ticker"?"Ticker":key==="value"?"Signed position value USD":"Your own assumed scenario return percent");
        input.autocomplete="off";input.inputMode=key==="ticker"?"text":"decimal";
        input.addEventListener("input",()=>{h[key]=input.value;calculate();});
        td.append(input);tr.append(td);
      }
      const cell=el("td"),remove=el("button","×","del");remove.type="button";remove.title="Remove this holding";
      remove.addEventListener("click",()=>{state.holdings=state.holdings.filter(x=>x.id!==h.id);renderHoldings();calculate();});
      cell.append(remove);tr.append(cell);body.append(tr);
    }
  }
  function numeric(v,allowBlank=false){
    const s=String(v??"").replace(/[$,\s]/g,"");
    if(!s)return allowBlank?null:NaN;
    const n=Number(s);
    return Number.isFinite(n)&&Math.abs(n)<=1e12?n:NaN;
  }
  function scenarioEntities(id){
    return state.graph.edges.filter(e=>e.src===id&&e.type==="hypothetical_involves").map(e=>e.dst);
  }
  function scenarioPaths(id){
    const chans=state.graph.edges.filter(e=>e.src===id&&e.type==="hypothetical_transmission")
      .map(e=>state.byId.get(e.dst)).filter(Boolean);
    const factors=new Set();
    for(const ch of chans)for(const e of neighbors(ch.id))
      if(e.edge.type==="hypothetical_factor_channel"&&state.byId.get(e.other)?.type==="factor")factors.add(e.other);
    return {chans,factors:[...factors]};
  }
  function updateContext(){
    const id=$("#event-choice").value,node=state.byId.get(id);
    if(!node)return;
    const p=scenarioPaths(id);
    const host=$("#scenario-context");host.replaceChildren();
    host.append(el("b",node.name+": "));
    host.append(el("span",CASES[id]||node.description||"Hypothetical research case."));
    host.append(el("div",p.chans.length+" unreviewed economic channels · "+p.factors.length+
      " qualitative factor definitions · "+scenarioEntities(id).length+" source entity associations","scenario-path"));
  }
  function localCsvCell(value){
    let s=String(value==null?"":value);
    if(/^[\s]*[=+@\-\t\r]/.test(s))s="'"+s;
    return /[",\n\r]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;
  }
  function exportAttribution(){
    if(!state.lastAttribution.length){
      setMessage("#portfolio-privacy","Calculate a valid portfolio before exporting.");return;
    }
    const heads=["Scenario","Ticker","PositionUSD","GrossPortfolioWeight","SeedPriorRelevance",
      "GrossWeightedRelevance","RuleBasedChannelWatchlist","MappingStatus","UserAssumedReturnPercent","UserAssumedPnLUSD","Methodology"];
    const rows=[heads,...state.lastAttribution.map(p=>[
      $("#event-choice").value,p.ticker,p.value,p.grossShare,p.relevance??"",
      p.contribution??"",p.watchlistChannels.join(" | "),p.status,p.shock??"",p.pnl??"",
      "Research seed relevance and entirely user-input scenario return; NOT financial beta"
    ])];
    const text=rows.map(x=>x.map(localCsvCell).join(",")).join("\r\n")+"\r\n";
    const blob=new Blob([text],{type:"text/csv;charset=utf-8"});
    const href=URL.createObjectURL(blob),a=el("a");a.href=href;a.download="eventrisk-manual-attribution.csv";
    document.body.append(a);a.click();a.remove();URL.revokeObjectURL(href);
  }
  function drawBars(rows){
    const canvas=$("#attribution-plot"),ctx=canvas.getContext("2d");if(!ctx)return;
    const w=canvas.width,h=canvas.height;
    ctx.clearRect(0,0,w,h);ctx.fillStyle=css("--surface");ctx.fillRect(0,0,w,h);
    const top=rows.filter(r=>r.relevance!==null).sort((a,b)=>b.contribution-a.contribution).slice(0,6);
    if(!top.length){ctx.fillStyle=css("--muted");ctx.font="13px system-ui";
      ctx.fillText("No mapped analyst-prior exposure for this scenario.",12,25);return;}
    const max=Math.max(.01,...top.map(r=>r.contribution));
    for(let i=0;i<top.length;i++){
      const p=top[i],y=i*23+7;
      ctx.fillStyle=css("--ink-2");ctx.font="12px system-ui";ctx.textAlign="left";ctx.fillText(p.ticker,8,y+13);
      ctx.fillStyle=css("--hairline");ctx.fillRect(74,y,Math.max(30,w-155),14);
      ctx.fillStyle=css("--security");ctx.fillRect(74,y,Math.max(0,(w-155)*p.contribution/max),14);
      ctx.fillStyle=css("--ink-2");ctx.textAlign="right";ctx.fillText(fmt.format(p.contribution*100)+" pts",w-8,y+12);
    }
  }
  function calculate(){
    if(!state.graph)return;
    updateContext();
    const result=window.EventRiskAttribution.calculate({
      holdings:state.holdings,
      scenarioId:$("#event-choice").value,
      graph:state.graph
    });
    const {errors,rows,gross,score,coveredFraction,mapped,watchlistCount,pnl,provided}=result;
    const root=$("#attribution-results");root.replaceChildren();
    if(errors.length){
      root.append(el("p",errors.slice(0,8).join(" "),"warning-note"));
      state.lastAttribution=[];
      $("#relevance-score").textContent="—";$("#coverage-score").textContent="—";$("#pnl-score").textContent="—";$("#watchlist-score").textContent="—";
      drawBars([]);return;
    }
    if(!rows.length){
      root.append(el("p","Add a valid security and signed position to calculate. There is no upload.","note"));
      state.lastAttribution=[];
      $("#relevance-score").textContent="—";$("#coverage-score").textContent="—";$("#pnl-score").textContent="—";
      drawBars([]);return;
    }
    $("#relevance-score").textContent=fmt.format(score*100)+" / 100";
    $("#coverage-score").textContent=fmt.format(coveredFraction*100)+"%";
    $("#pnl-score").textContent=provided?(usd.format(pnl)+(provided<rows.length?"*":"")):"Not entered";
    $("#watchlist-score").textContent=watchlistCount+"/"+rows.length+" holdings";
    const caption=el("p","Gross positions: "+usd.format(gross)+
      " · "+mapped+"/"+rows.length+" holding lines have a source-prior relationship. "+
      (provided===rows.length?"Scenario P&L: all rows use YOUR return assumptions.":
        provided? " * P&L is PARTIAL: "+provided+" of "+rows.length+" lines have YOUR return assumptions.":
        "What-if P&L requires manually entered per-security assumed return percentages."),"note");
    root.append(caption);
    const t=el("table"),thead=el("thead"),head=el("tr");
    for(const v of ["Security","Position","Gross wt.","Seed prior","Relevance pts","Qualitative watchlist","Your what-if P&L"])head.append(el("th",v));
    thead.append(head);t.append(thead);
    const body=el("tbody");
    for(const p of rows){
      const tr=el("tr");
      for(const v of [p.ticker,usd.format(p.value),fmt.format(p.grossShare*100)+"%",
        p.relevance===null?"Not mapped":fmt.format(p.relevance),
        p.contribution===null?"—":fmt.format(p.contribution*100),
        p.watchlistChannels.length?p.watchlistChannels.join(", "):"—",
        p.pnl===null?"Not entered":usd.format(p.pnl)])tr.append(el("td",v));
      body.append(tr);
    }
    t.append(body);root.append(t);
    const note=el("p","Method: relevance = Σ(|position|/gross × highest connected entity→security seed prior). Sector/country watchlist uses disclosed matching rules and does NOT change this numerical score. "+
      "Mapping coverage = mapped gross / total gross. The model neither predicts return signs nor multiplies a prior by a shock.","note");
    root.append(note);
    state.lastAttribution=rows;
    drawBars(rows);
  }

  // ── UI wiring, using Marco's original DOM and split-handles ───────────────
  function wire(){
    document.querySelectorAll("nav button[data-view]").forEach(b=>b.addEventListener("click",()=>changeView(b.dataset.view)));
    document.querySelectorAll(".tabs button").forEach(b=>b.addEventListener("click",()=>{
      state.tab=b.dataset.tab;
      document.querySelectorAll(".tabs button").forEach(c=>c.setAttribute("aria-selected",String(c===b)));
      $("#search").value="";
      filterList();
      if(state.tab==="markets")searchSourceQuestions();
    }));
    $("#search").addEventListener("input",()=>{
      if(state.tab==="markets"){
        clearTimeout(wire.sourceDelay);
        wire.sourceDelay=setTimeout(()=>searchSourceQuestions(true),350);
      }else filterList();
    });
    $("#graph-toggle").addEventListener("click",()=>{
      state.expanded=!state.expanded;
      $("#graph-toggle").textContent=state.expanded?"Focus graph":"More connections";
      $("#graph-toggle").setAttribute("aria-pressed",String(state.expanded));
      if(state.selected)renderNetwork(state.selected);
    });
    $("#depth").addEventListener("change",()=>{if(state.selected)renderNetwork(state.selected);});
    $("#show-factors").addEventListener("change",()=>{if(state.selected)renderNetwork(state.selected);});
    $("#browse-mobile").addEventListener("click",()=>{
      const open=!document.body.classList.contains("mobile-list-open");
      document.body.classList.toggle("mobile-list-open",open);
      document.body.classList.remove("mobile-detail-open");
      $("#browse-mobile").setAttribute("aria-expanded",String(open));
      if(state.network)requestAnimationFrame(()=>state.network.redraw());
    });
    $("#open-attribution").addEventListener("click",()=>changeView("attribution"));
    $("#add-holding").addEventListener("click",()=>addHolding());
    $("#calculate").addEventListener("click",calculate);
    $("#event-choice").addEventListener("change",calculate);
    $("#clear-holdings").addEventListener("click",()=>{state.holdings=[];renderHoldings();calculate();});
    $("#load-demo").addEventListener("click",()=>{
      state.holdings=[newPosition("TSM","25000","-5"),newPosition("NVDA","15000","-3"),
        newPosition("AAPL","10000","-2"),newPosition("FXI","-5000","4")];
      renderHoldings();calculate();
      setMessage("#portfolio-privacy","DEMO holdings loaded. They are hypothetical example positions, not your actual portfolio. Edit or clear them; nothing is uploaded.");
    });
    $("#print-attribution").addEventListener("click",()=>window.print());
    $("#export-attribution").addEventListener("click",exportAttribution);
    $("#connect-research").addEventListener("click",async()=>{
      state.key=$("#analyst-key").value.trim();$("#analyst-key").value="";
      if(!state.key){setMessage("#access-status","Enter an issued analyst access key.");return;}
      setMessage("#access-status","Verifying real read-only MotherDuck access…");
      try{
        const r=await fetch("/api/v1/research/coverage",{
          headers:researchHeaders(),cache:"no-store"});
        const body=await r.json();
        if(!r.ok)throw Error(body.error||"Research API HTTP "+r.status);
        if(body.mode!=="LIVE_DATABASE_COUNT_ONLY")throw Error("Unexpected source provenance");
        const questions=body.coverage.find(x=>x.metric==="graph_question_nodes");
        const count=questions?Number(questions.value).toLocaleString():"unknown";
        setMessage("#access-status","Live warehouse verified: "+count+
          " source question identifiers. Provider redisplay rights are separate.");
        setMessage("#source-status","MOTHERDUCK LIVE · read-only source counts");
        if(state.tab==="markets")searchSourceQuestions();
      }catch(e){
        state.key="";
        setMessage("#access-status","Live connection not established: "+e.message+
          ". This service needs its own server-side, least-privileged MotherDuck credential.");
      }
    });
    const root=document.documentElement.style;
    document.querySelectorAll(".split").forEach(handle=>{
      const side=handle.dataset.side;let tracking=false;
      const set=px=>{
        const v=Math.max(205,Math.min(px,window.innerWidth*.49));
        root.setProperty("--"+side,v+"px");if(state.network)state.network.redraw();
      };
      handle.addEventListener("pointerdown",e=>{
        tracking=true;handle.setPointerCapture(e.pointerId);
        handle.classList.add("dragging");document.body.classList.add("resizing");
      });
      handle.addEventListener("pointermove",e=>{
        if(!tracking)return;
        set(side==="left"?e.clientX:window.innerWidth-e.clientX);
      });
      const end=()=>{tracking=false;handle.classList.remove("dragging");document.body.classList.remove("resizing");};
      handle.addEventListener("pointerup",end);handle.addEventListener("pointercancel",end);
      handle.addEventListener("keydown",e=>{
        if(!["ArrowLeft","ArrowRight"].includes(e.key))return;
        e.preventDefault();
        const w=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--"+side))||(side==="left"?300:360);
        const direction=(e.key==="ArrowRight"?1:-1)*(side==="left"?1:-1);
        set(w+direction*24);
      });
    });
    new ResizeObserver(()=>{if(state.network)state.network.redraw();}).observe($("#canvas-wrap"));
  }
  async function init(){
    wire();
    try{
      const [catalog,graph,runtime]=await Promise.all([
        fetch("/api/v1/catalog",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Catalog HTTP "+r.status);return r.json();}),
        fetch("/api/v1/graph",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Graph HTTP "+r.status);return r.json();}),
        fetch("/api/v1/runtime",{cache:"no-store"}).then(r=>r.json())
      ]);
      if(catalog.factors_count!==108||catalog.securities_count<500||!Array.isArray(catalog.channels)||
         graph.mode!=="PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE"||
         graph.edges.some(e=>e.review_status!=="RESEARCH_ONLY_NOT_APPROVED"))
        throw Error("Unexpected public-source graph provenance or definition count");
      state.catalog=catalog;state.graph=graph;rebuildGraphIndex();
      setMessage("#source-status","543 securities · 108 factors · "+
        catalog.channels.length+" economic channels · "+
        (runtime.connection_tested?"DB tested":"warehouse gated"));
      for(const n of graph.nodes.filter(n=>n.type==="event")){
        const opt=el("option",n.name);opt.value=n.id;$("#event-choice").append(opt);
      }
      $("#event-choice").value="event:taiwan";
      filterList();renderHoldings();calculate();
      if(typeof vis==="undefined"||typeof vis.Network!=="function"){
        setMessage("#empty","Graph library blocked by the browser. Original Marco graph requires pinned vis-network from unpkg.com.");
      }else{
        state.network=new vis.Network($("#graph"),{nodes:[],edges:[]},{
          physics:false,layout:{hierarchical:{enabled:true,direction:"LR",sortMethod:"directed"}},
          interaction:{hover:true,tooltipDelay:120},
          nodes:{font:{size:13,face:"system-ui"},borderWidth:2},
          edges:{smooth:{type:"continuous"},selectionWidth:1}
        });
        state.network.on("stabilizationIterationsDone",()=>state.network.setOptions({physics:false}));
        state.network.on("click",e=>{if(e.nodes.length)select(e.nodes[0]);});
      }
      const viewParam=new URLSearchParams(location.search).get("view");
      const eventParam=new URLSearchParams(location.search).get("event");
      if(eventParam&&state.byId.get(eventParam)?.type==="event")$("#event-choice").value=eventParam;
      await select(eventParam&&state.byId.has(eventParam)?eventParam:"event:taiwan",false);
      if(viewParam==="attribution")changeView("attribution");
    }catch(e){
      setMessage("#empty","Public source graph unavailable: "+e.message);
      setMessage("#list-status","Source catalog unavailable; no invented fallback nodes.");
      setMessage("#source-status","SOURCE UNAVAILABLE");
    }
  }
  document.addEventListener("DOMContentLoaded",init);
})();
