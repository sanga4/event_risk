"use strict";
/* Event Risk Graph — minimal Marco UI using original public source seeds.
   Live venue/source questions are only loaded from the authenticated MotherDuck API.
   Research hypotheses and catalog factor definitions are not financial betas.
*/
(()=>{
 const $=id=>document.getElementById(id);
 const state={nodes:new Map(),edges:[],adj:new Map(),selected:null,tab:"contracts",
              key:"",ownerKey:"",sourceQuestions:[],sourceMarkets:[],sourceEvents:[],sourcePropositions:[],marketOffset:0,network:null,runtime:null};
 const typeColor={contract:"question",event:"question",question:"question",entity:"entity",security:"security",factor:"factor",
                  channel:"factor",event:"question",market:"market",proposition:"proposition"};
 const mk=(tag,text,cls)=>{const e=document.createElement(tag);
   if(text!==undefined&&text!==null)e.textContent=String(text);
   if(cls)e.className=cls;return e;};
 const val=x=>x===null||x===undefined?"—":typeof x==="object"?JSON.stringify(x):String(x);
 function reindex(){
   state.adj=new Map();
   for(const e of state.edges)for(const id of [e.src,e.dst]){
     if(!state.adj.has(id))state.adj.set(id,[]);
     state.adj.get(id).push(e);
   }
 }
 function nodeType(n){return n.source_event?"Native provider event (not canonical)":n.type==="market"?"Captured market contract":n.type==="proposition"?"Warehouse proposition (identity unverified)":n.type==="contract"?"Illustrative demo contract":n.type==="question"?"Source question":n.type==="event"?"Hypothetical scenario":
   n.type==="factor"?"Factor definition":n.type==="channel"?"Economic channel":n.type==="security"?"Security":"Entity";}
 function graphNeighbors(id){
   return (state.adj.get(id)||[]).map(edge=>({edge,other:edge.src===id?edge.dst:edge.src}))
     .filter(x=>state.nodes.has(x.other));
 }
 function browse(){
   $("market-pagination").hidden=state.tab!=="markets";
   const ids=[...state.nodes.values()].filter(n=>state.tab==="questions"?
     n.type==="question":n.type==={markets:"market",contracts:"contract",events:"event",entities:"entity",securities:"security",factors:"factor"}[state.tab]);
   const q=$("search").value.trim().toLowerCase();
   const rows=(q?ids.filter(n=>[n.name,n.ticker,n.description,n.subtitle,n.id]
      .some(v=>String(v||"").toLowerCase().includes(q))):ids)
     .sort((a,b)=>(a.ticker||a.name).localeCompare(b.ticker||b.name));
   const list=$("list");list.replaceChildren();
   for(const n of rows.slice(0,300)){
     const li=mk("li");li.dataset.id=n.id;li.tabIndex=0;
     if(n.id===state.selected)li.setAttribute("aria-current","true");
     li.append(mk("i",null,"swatch "+(typeColor[n.type]||"factor")));
     li.append(mk("span",(n.ticker?n.ticker+" · ":"")+n.name,"name"));
     li.append(mk("span",n.type==="security"?n.subtitle||"":n.type==="factor"?n.subtitle||"":n.type==="question"?"DB":n.type==="market"&&Number.isFinite(n.probability)?Math.round(n.probability*1000)/10+"%":"", "num"));
     li.addEventListener("click",()=>select(n.id));
     li.addEventListener("keydown",e=>{if(e.key==="Enter")select(n.id);});
     list.append(li);
   }
   $("list-info").textContent=state.tab==="questions"&&!state.key?
     "Source questions require MotherDuck access and display permission.":
     rows.length+" "+state.tab+" · "+Math.min(300,rows.length)+" shown";
   if(rows.length===0)list.append(mk("li",state.tab==="questions"?
     "No authorized source questions loaded.":"No results."));
 }
 function addRow(host,name,value){
   const p=mk("div",undefined,"row");
   p.append(mk("b",name+": "),mk("span",val(value)));
   host.append(p);
 }
 function detail(id){
   const n=state.nodes.get(id),host=$("detail");host.replaceChildren();if(!n)return;
   host.append(mk("div",nodeType(n),"kind"),mk("h2",n.name));
   addRow(host,"ID",id);
   if(n.ticker)addRow(host,"Ticker",n.ticker);
   if(n.subtitle)addRow(host,"Category",n.subtitle);
   if(n.description)addRow(host,"Description",n.description);
   if(n.last_recorded_at)addRow(host,"Warehouse recorded",n.last_recorded_at);
   if(n.native_event_id)addRow(host,"Native provider event ID",n.native_event_id);
   if(n.proposition_id)addRow(host,"Warehouse proposition ID",n.proposition_id);
   if(n.type==="market"){
     const pct=v=>typeof v==="number"&&Number.isFinite(v)?(v*100).toFixed(1)+"%":"Not captured";
     const percentage=v=>typeof v==="number"&&Number.isFinite(v)?v.toFixed(2)+" pp":"Not captured";
     const hero=mk("div",undefined,"hero");
     hero.append(mk("b",pct(n.probability)),mk("span","captured YES price · "+n.provider));
     host.append(hero);
     addRow(host,"YES implied market price",pct(n.probability));
     addRow(host,"Previous capture",pct(n.previous_probability));
     addRow(host,"Change from prior capture",percentage(n.probability_delta_pp));
     addRow(host,"Quote basis",n.quote_basis||"Unspecified");
     addRow(host,"Captured at",n.observed_at||"Unknown");
     addRow(host,"Known to warehouse",n.known_at||"Unknown");
     addRow(host,"Capture timestamp verified",n.capture_time_verified===true?"Yes":"Not verified");
     addRow(host,"Provider freshness verified",n.provider_quote_freshness_verified===true?"Yes":"Not verified");
     addRow(host,"Original PIT released",n.historical_point_in_time_released===true?"Yes":"No");
     addRow(host,"Native provider event ID",n.event_id||"Not supplied");
     addRow(host,"Resolution terms","Verify at the venue; this normalized quote view does not certify them.");
     addRow(host,"Canonical event mapping","UNREVIEWED: provider grouping is not verified real-world event identity.");
     if(Array.isArray(n.probabilityHistory)&&n.probabilityHistory.length){
       host.append(mk("h3","Captured probability history"));
       for(const p of n.probabilityHistory.slice(0,8)){
         const prob=typeof p.probability==="number"?(p.probability*100).toFixed(1)+"%":"n/a";
         addRow(host,p.observed_date,prob+" · "+
           (typeof p.probability_delta_pp==="number"?
             (p.probability_delta_pp>=0?"+":"")+p.probability_delta_pp.toFixed(2)+" pp":"no prior delta"));
       }
     }
     host.append(mk("p","Captured quote, not necessarily a current tradable price or the probability of the normalized event. Market prices and probabilities differ by contract structure.","note"));
   }
   if(n.type==="contract"&&!n.market_id)addRow(host,"Market probability","Not available: this is a synthetic demonstration, not a real exchange contract.");
   if(n.provider)addRow(host,"Venue / provider",n.provider);
   if(n.historical_series_validated===false)addRow(host,"Observed factor series","NOT VERIFIED");
   addRow(host,"Source",n.type==="market"?"MotherDuck / lab_live_market_latest_v1":n.source_event?"MotherDuck native provider event":n.liveWarehouse?"MotherDuck / graph_nodes":
     n.type==="contract"?"SYNTHETIC NAVIGATION EXAMPLE / NOT AN EXCHANGE CONTRACT":
     n.type==="security"?"Repository / securities.csv":
     n.type==="factor"?"Repository / factors.json":
     n.type==="entity"?"Repository / exposures.csv":"Repository research references");
   addRow(host,"Status",n.review_status||
      (n.liveWarehouse?"Raw source observation, original first-publication not verified":"Reference only"));
   const links=graphNeighbors(id).sort((a,b)=>(Number(b.edge.weight)||0)-(Number(a.edge.weight)||0));
   host.append(mk("h3","Relationships ("+links.length+")"));
   if(!links.length)host.append(mk("p","No connected source edges in this loaded graph.","note"));
   for(const {edge,other} of links.slice(0,35)){
     const destination=state.nodes.get(other),b=mk("button",destination.name,"detail-link");
     b.type="button";
     b.append(mk("div",edge.type.replaceAll("_"," ")+
       (edge.weight!==undefined&&edge.weight!==null?" · weight "+val(edge.weight):"")+
       " · "+(edge.review_status||"source research"),"meta"));
     b.addEventListener("click",()=>select(other));host.append(b);
   }
   if(links.length>35)host.append(mk("p","+"+(links.length-35)+" more connections; search/select to explore.","note"));
   host.append(mk("p","The data-center demonstration is hypothetical. Source-native venue groupings do not prove verified canonical events, company exposure, or security return betas.","note"));
 }
 function visible(id){
   const depth=Number($("depth").value)||1,seen=new Map([[id,0]]);
   let frontier=[id];
   for(let d=1;d<=depth;d++){
     const next=[];
     for(const key of frontier){
       for(const {other} of graphNeighbors(key))if(!seen.has(other)){
         seen.set(other,d);next.push(other);
       }
     }
     frontier=next;
   }
   const ids=[...seen].filter(([key])=>$("show-factors").checked||state.nodes.get(key)?.type!=="factor"||key===id);
   // Keep the original graph usable, not a hundreds-of-nodes hairball.
   ids.sort((a,b)=>a[1]-b[1]||a[0].localeCompare(b[0]));
   return new Set(ids.slice(0,85).map(x=>x[0]));
 }
 function demoPathIds(){
   // Explicitly small complete contract -> event -> entity -> securities -> factors.
   const ordered=[
    "contract:illustrative:data_center_power",
    "event:data_center_demand",
    "entity:theme:data_center_infrastructure",
   ];
   const watch=["EQIX","VRT","MSFT","CEG","NVDA"];
   for(const ticker of watch){
     const sec="security:"+ticker;
     if(!state.nodes.has(sec))continue;
     ordered.push(sec);
     for(const edge of state.edges){
       if(edge.src===sec&&edge.type==="proposed_security_factor_exposure" &&
          state.nodes.has(edge.dst)&&!ordered.includes(edge.dst))
         ordered.push(edge.dst);
     }
   }
   return new Set(ordered.filter(id=>state.nodes.has(id)));
 }
 function createLocalGraph(host){
   // Local SVG; no third-party script can inspect private keys.
   const ns="http://www.w3.org/2000/svg",element=(tag,attrs={})=>{
     const e=document.createElementNS(ns,tag);
     for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));
     return e;
   };
   let data={nodes:[],edges:[]};
   function draw(){
     host.replaceChildren();
     const buckets=Array.from({length:5},()=>[]);
     const types={market:0,contract:0,question:1,event:1,entity:2,security:3,channel:4,factor:4};
     for(const n of data.nodes){
       const original=state.nodes.get(n.id),bucket=types[original?.type]??2;
       buckets[bucket].push(n);
     }
     const rows=Math.max(1,...buckets.map(a=>a.length));
     const H=Math.max(440,Math.min(2500,(rows+1)*60)),W=1100;
     const root=element("svg",{viewBox:"0 0 "+W+" "+H,role:"img",
       "aria-label":"EventRisk contract to factor network"});
     const pos=new Map();
     buckets.forEach((b,i)=>b.forEach((n,j)=>pos.set(n.id,{x:90+i*225,y:(j+1)*H/(b.length+1)})));
     const defs=element("defs"),m=element("marker",{id:"arrow-eventrisk",viewBox:"0 0 10 10",
       refX:8,refY:5,markerWidth:6,markerHeight:6,orient:"auto-start-reverse"});
     m.append(element("path",{d:"M0 1 L9 5 L0 9 z",fill:"var(--axis)"}));
     defs.append(m);root.append(defs);
     for(const e of data.edges){
       const a=pos.get(e.from),b=pos.get(e.to);if(!a||!b)continue;
       root.append(element("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:"var(--axis)",
         "stroke-width":1.4,"marker-end":"url(#arrow-eventrisk)"}));
     }
     for(const n of data.nodes){
       const p=pos.get(n.id),item=state.nodes.get(n.id),type=item?.type;
       if(!p)continue;
       const group=element("g",{role:"button",tabindex:0,"aria-label":item?.name||n.id});
       const fill=n.color?.background||"var(--question)";
       const shape=type==="market"||type==="contract"?
         element("path",{d:"M"+p.x+" "+(p.y-12)+" l12 21 h-24 z",fill}):
         type==="security"?element("rect",{x:p.x-10,y:p.y-10,width:20,height:20,rx:2,fill}):
         type==="entity"?element("path",{d:"M"+p.x+" "+(p.y-12)+" l12 12 -12 12 -12 -12 z",fill}):
         element("circle",{cx:p.x,cy:p.y,r:n.id===state.selected?12:10,fill});
       shape.setAttribute("stroke",n.id===state.selected?"var(--ink)":"var(--page)");
       shape.setAttribute("stroke-width",n.id===state.selected?3:1);
       group.append(shape);
       const label=element("text",{x:p.x,y:p.y+29,"text-anchor":"middle",fill:"var(--ink)",
         "font-size":13});
       const name=item?.ticker||item?.name||n.id;
       label.textContent=name.length>29?name.slice(0,28)+"…":name;
       group.append(label);
       if(type==="market"&&Number.isFinite(item?.probability)){
         const sub=element("text",{x:p.x,y:p.y+46,"text-anchor":"middle",
           fill:"var(--ink-2)","font-size":12});
         sub.textContent=(item.probability*100).toFixed(1)+"% YES";
         group.append(sub);
       }
       const title=element("title");title.textContent=item?.name||n.id;group.append(title);
       group.addEventListener("click",()=>select(n.id));
       group.addEventListener("keydown",e=>{
         if(e.key==="Enter"||e.key===" "){e.preventDefault();select(n.id);}
       });
       group.style.cursor="pointer";root.append(group);
     }
     host.append(root);
   }
   return {setData(next){data=next;draw()},setOptions(){},fit(){},redraw(){draw()}};
 }
 function graph(id){
   if(!state.network){
     $("empty").textContent="Graph unavailable: original vis-network library could not load.";
     return;
   }
   const isDemo=id==="contract:illustrative:data_center_power";
   const ids=isDemo?demoPathIds():visible(id);
   const getColor=n=>getComputedStyle(document.documentElement)
     .getPropertyValue("--"+(typeColor[n.type]||"factor")).trim()||"#888";
   const nodes=[...ids].map(key=>{
     const n=state.nodes.get(key),type=n.type;
     return {id:key,label:(n.ticker||n.name).slice(0,38),
       shape:type==="contract"?"triangle":type==="event"?"dot":type==="security"?"square":type==="entity"?"diamond":type==="factor"?"box":"dot",
       size:key===id?19:10,
       color:{background:getColor(n),border:key===id?"#111":getColor(n)},
       font:{size:12,color:getComputedStyle(document.documentElement).getPropertyValue("--ink").trim(),
         strokeWidth:3,strokeColor:getComputedStyle(document.documentElement).getPropertyValue("--page").trim()},
       title:n.name+" · "+nodeType(n)};
   });
   const edges=state.edges.filter(e=>ids.has(e.src)&&ids.has(e.dst)).map((e,i)=>({
     id:String(i),from:e.src,to:e.dst,
     color:{color:getComputedStyle(document.documentElement).getPropertyValue("--axis").trim()},
     dashes:e.type.startsWith("hypothetical"),
     width:Math.max(.6,Math.min(2,Number(e.weight)||1)),
     title:e.type}));
   state.network.setOptions(isDemo?
    {physics:false,layout:{hierarchical:{enabled:true,direction:"LR",sortMethod:"directed",levelSeparation:165,nodeSpacing:95}},
     edges:{smooth:{type:"cubicBezier",forceDirection:"horizontal"}}}:
    {layout:{hierarchical:{enabled:false}},physics:false});
   state.network.setData({nodes,edges});
   $("empty").hidden=true;$("caption").hidden=false;
   $("caption").textContent=nodes.length+" nodes · "+edges.length+" source/reference edges";
   requestAnimationFrame(()=>state.network.fit({animation:false}));
 }
 async function select(id){
   if(!state.nodes.has(id))return;
   state.selected=id;browse();detail(id);graph(id);
   if(state.nodes.get(id).type==="market"&&state.key)await loadMarketValue(id);
   else if(state.nodes.get(id).liveWarehouse&&!state.nodes.get(id).source_event&&state.key)await loadNeighbors(id);
 }
 async function request(path){
   const headers={"X-Analyst-Key":state.key};
   if(state.ownerKey)headers["X-Data-Admin-Key"]=state.ownerKey;
   const r=await fetch(path,{cache:"no-store",headers});
   let data;try{data=await r.json()}catch(_){throw Error("Invalid server response");}
   if(!r.ok)throw Error(data.error||"HTTP "+r.status);
   return data;
 }
 async function searchMarkets(){
   if(!state.key){
     $("live-status").textContent="Unlock your private warehouse with both keys to inspect captured odds.";
     browse();return;
   }
   const venue=$("market-venue").value;
   const query=$("search").value.trim();
   $("live-status").textContent="Looking up captured "+venue+" market values…";
   try{
     const d=await request("/api/v1/research/markets?venue="+encodeURIComponent(venue)+
       "&limit=50&offset="+state.marketOffset+"&q="+encodeURIComponent(query));
     if(d.mode!=="LICENSE_GATED_CAPTURED_MARKET_QUOTES")throw Error("Unexpected quote source");
     for(const n of [...state.sourceMarkets,...state.sourceEvents,...state.sourcePropositions])state.nodes.delete(n.id);
     state.sourceMarkets=[];state.sourceEvents=[];state.sourcePropositions=[];
     state.edges=state.edges.filter(e=>!e.ownerMarketGrouping);
     const sourceGroupIds=new Set(),sourcePropositionIds=new Set();
     for(const m of d.rows||[]){
       const n={id:"market:"+m.venue+":"+m.market_id,type:"market",
         name:m.question||m.event_title||m.market_id,
         provider:m.venue,market_id:m.market_id,event_id:m.event_id,event_title:m.event_title,proposition_id:m.proposition_id,liveWarehouse:true,
         probability:m.probability,previous_probability:m.previous_probability,
         probability_delta_pp:m.probability_delta_pp,quote_basis:m.quote_basis,
         known_at:m.known_at,observed_at:m.observed_at,
         capture_time_verified:m.capture_time_verified,
         provider_quote_freshness_verified:m.provider_quote_freshness_verified,
         historical_point_in_time_released:m.historical_point_in_time_released,
         review_status:"Captured warehouse quote; venue freshness and original PIT unverified"};
       state.nodes.set(n.id,n);state.sourceMarkets.push(n);
       if(m.proposition_id){
         const propositionId=m.proposition_id;
         if(!sourcePropositionIds.has(propositionId)){
           sourcePropositionIds.add(propositionId);
           const proposition={id:propositionId,name:"Warehouse proposition · "+propositionId,
             type:"proposition",liveWarehouse:true,
             review_status:"WAREHOUSE_PROPOSITION_ID_NOT_VERIFIED_CANONICAL_EVENT"};
           state.nodes.set(propositionId,proposition);state.sourcePropositions.push(proposition);
         }
         state.edges.push({src:n.id,dst:propositionId,
           type:"warehouse_market_to_proposition",ownerMarketGrouping:true,
           review_status:"SOURCE_DERIVED_IDENTITY_NOT_CANONICAL_EVENT"});
       }
       if(m.event_id){
         const groupId="venue-event:"+m.venue+":"+m.event_id;
         if(!sourceGroupIds.has(groupId)){
           sourceGroupIds.add(groupId);
           const eventNode={id:groupId,name:m.event_title||m.event_id,type:"event",
             source_event:true,native_event_id:m.event_id,provider:m.venue,liveWarehouse:true,
             review_status:"SOURCE_PROVIDER_EVENT_GROUP_NOT_CANONICAL"};
           state.nodes.set(groupId,eventNode);state.sourceEvents.push(eventNode);
         }
         state.edges.push({src:n.id,dst:groupId,type:"native_provider_event_grouping",
           ownerMarketGrouping:true,review_status:"OBSERVED_PROVIDER_GROUPING_NO_CANONICAL_MAPPING"});
       }
     }
     reindex();browse();
     if(state.sourceMarkets.length)select(state.sourceMarkets[0].id);
     $("live-status").textContent=state.sourceMarkets.length+" "+venue+
       " captured contracts; rows "+(state.marketOffset+1)+"–"+
       (state.marketOffset+state.sourceMarkets.length)+
       ". Select one for captured YES price, history and provenance.";
     $("market-prev").disabled=state.marketOffset===0;
     $("market-next").disabled=state.sourceMarkets.length<50;
   }catch(e){
     $("live-status").textContent="Market values unavailable: "+e.message+
       ". Owner inspection requires both keys; public redistribution remains separately gated.";
     browse();
   }
 }
 async function loadMarketValue(id){
   const n=state.nodes.get(id);
   if(!n||!n.market_id||!state.key)return;
   try{
     const d=await request("/api/v1/research/market-quote?venue="+
       encodeURIComponent(n.provider)+"&market_id="+encodeURIComponent(n.market_id));
     if(d.mode!=="LICENSE_GATED_CAPTURED_MARKET_QUOTE")throw Error("Invalid quote contract");
     if(d.record){
       try{
         const hist=await request("/api/v1/research/market-history?venue="+
           encodeURIComponent(n.provider)+"&market_id="+encodeURIComponent(n.market_id)+
           "&limit=8");
         if(hist.mode==="LICENSE_GATED_CAPTURED_MARKET_HISTORY")
           n.probabilityHistory=hist.rows||[];
       }catch(_){n.probabilityHistory=[];}
       Object.assign(n,d.record);
       n.probability=d.record.probability;
       if(n.proposition_id && state.nodes.has(n.proposition_id))
         await loadNeighbors(n.proposition_id);
       if(state.selected===id){detail(id);browse();}
     }
   }catch(e){$("live-status").textContent="Market detail unavailable: "+e.message;}
 }
 async function searchQuestions(){
   if(!state.key){browse();return}
   $("live-status").textContent="Searching authorized warehouse source questions…";
   try{
     const term=$("search").value.trim(),url="/api/v1/research/events?limit=75&q="+encodeURIComponent(term);
     const data=await request(url);
     if(data.mode!=="LIVE_RESEARCH_GRAPH_ENTITY_SEARCH")throw Error("Unexpected source type");
     // Clear previously loaded warehouse question nodes, retain public reference nodes.
     for(const n of state.sourceQuestions)state.nodes.delete(n.id);
     state.sourceQuestions=[];
     for(const raw of data.rows||[]){
       const n={id:raw.node_id,name:raw.name,type:"question",liveWarehouse:true,
           last_recorded_at:raw.last_recorded_at,
           review_status:"Recorded warehouse node · not validated publication vintage"};
       state.nodes.set(n.id,n);state.sourceQuestions.push(n);
     }
     reindex();browse();
     $("live-status").textContent=state.sourceQuestions.length+
       " observed source questions returned from live MotherDuck (not original PIT certified).";
   }catch(e){$("live-status").textContent="Source questions unavailable: "+e.message;
     browse();}
 }
 async function loadNeighbors(id){
   try{
     const d=await request("/api/v1/research/graph-neighbors?node_id="+encodeURIComponent(id));
     if(d.mode!=="LIVE_RESEARCH_GRAPH_NEIGHBORHOOD")throw Error("Unexpected source response");
     for(const r of d.nodes||[]){
       if(!state.nodes.has(r.node_id))state.nodes.set(r.node_id,{
          id:r.node_id,name:r.name||r.node_id,
          type:["question","entity","security","factor","proposition","market"].includes(r.node_type)?r.node_type:"entity",
          liveWarehouse:true,review_status:"Source graph record (PIT not verified)"});
     }
     const sig=new Set(state.edges.map(e=>[e.src,e.dst,e.type].join("|")));
     for(const e of d.edges||[]){
       const x={src:e.src_id,dst:e.dst_id,type:e.edge_type,weight:e.weight,
          review_status:"Live warehouse source relation"};
       const key=[x.src,x.dst,x.type].join("|");
       if(state.nodes.has(x.src)&&state.nodes.has(x.dst)&&!sig.has(key)){
         state.edges.push(x);sig.add(key);
       }
     }
     reindex();detail(id);graph(id);
   }catch(e){$("live-status").textContent="Live neighborhood unavailable: "+e.message}
 }
 async function connect(){
   state.key=$("analyst-key").value.trim();state.ownerKey=$("owner-key").value.trim();
   $("analyst-key").value="";$("owner-key").value="";
   if(!state.key){$("live-status").textContent="Enter your issued analyst API key.";return;}
   try{
     const d=await request("/api/v1/research/coverage");
     if(d.mode!=="LIVE_DATABASE_COUNT_ONLY")throw Error("Unexpected source contract");
     state.tab="markets";
     for(const b of document.querySelectorAll(".tabs button"))
       b.setAttribute("aria-selected",String(b.dataset.tab==="markets"));
     $("live-status").textContent=state.ownerKey?"Private inspection enabled (not redistribution)":
       "Analyst connection verified; private source inspection also requires data-admin key.";
     await searchMarkets();
   }catch(e){state.key="";state.ownerKey="";$("live-status").textContent="Warehouse unlock failed: "+e.message;
     browse();}
 }
 function wire(){
   document.querySelectorAll(".tabs button").forEach(button=>{
     button.addEventListener("click",()=>{
       state.tab=button.dataset.tab;
       for(const b of document.querySelectorAll(".tabs button"))
         b.setAttribute("aria-selected",String(b===button));
       $("search").value="";state.marketOffset=0;
       if(state.tab==="questions")searchQuestions();else if(state.tab==="markets")searchMarkets();else browse();
     });
   });
   let debounce;
   $("search").addEventListener("input",()=>{
     if(state.tab!=="questions"&&state.tab!=="markets")return browse();
     state.marketOffset=0;
      clearTimeout(debounce);debounce=setTimeout(state.tab==="markets"?searchMarkets:searchQuestions,350);
   });
   $("depth").addEventListener("change",()=>state.selected&&graph(state.selected));
   $("show-factors").addEventListener("change",()=>state.selected&&graph(state.selected));
   $("connect").addEventListener("click",connect);
   $("market-venue").addEventListener("change",()=>{state.marketOffset=0;
      if(state.tab==="markets")searchMarkets()});
   $("market-prev").addEventListener("click",()=>{state.marketOffset=Math.max(0,state.marketOffset-50);searchMarkets()});
   $("market-next").addEventListener("click",()=>{state.marketOffset+=50;searchMarkets()});
   const root=document.documentElement.style;
   document.querySelectorAll(".split").forEach(handle=>{
     const side=handle.dataset.side;let dragging=false;
     const set=px=>{
       root.setProperty("--"+side,Math.max(200,Math.min(px,innerWidth*.48))+"px");
       if(state.network)state.network.redraw();
     };
     handle.addEventListener("pointerdown",e=>{dragging=true;handle.setPointerCapture(e.pointerId)});
     handle.addEventListener("pointermove",e=>{if(dragging)set(side==="left"?e.clientX:innerWidth-e.clientX)});
     handle.addEventListener("pointerup",()=>dragging=false);
     handle.addEventListener("keydown",e=>{
       if(!["ArrowLeft","ArrowRight"].includes(e.key))return;
       e.preventDefault();const current=parseInt(getComputedStyle(document.documentElement).getPropertyValue("--"+side))||(side==="left"?300:360);
       set(current+(e.key==="ArrowRight"?24:-24)*(side==="left"?1:-1));
     });
   });
 }
 async function main(){
   wire();
   try{
     const [g,r]=await Promise.all([
       fetch("/api/v1/graph-paths",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Graph HTTP "+r.status);return r.json()}),
       fetch("/api/v1/runtime",{cache:"no-store"}).then(r=>r.json())
     ]);
     if(g.mode!=="PUBLIC_REFERENCE_PLUS_EXPLICIT_SYNTHETIC_PATH_EXAMPLE")
       throw Error("Unexpected research graph provenance");
     for(const n of g.nodes)state.nodes.set(n.id,n);
     state.edges=g.edges;state.runtime=r;reindex();
     $("live-status").textContent=r.connection_tested?
       "Server queried MotherDuck · sign in to load source questions.":
       r.database_credentials_present?"Warehouse configured; not yet verified for this session.":
       "Not connected: Railway MOTHERDUCK_TOKEN is not configured.";
     state.network=createLocalGraph($("graph"));
     browse();
     const first=state.nodes.has("contract:illustrative:data_center_power")?"contract:illustrative:data_center_power":
       [...state.nodes.values()].find(n=>n.type==="entity")?.id;
     if(first)select(first);
   }catch(e){$("empty").textContent="Source unavailable: "+e.message;
     $("live-status").textContent="Graph unavailable";}
 }
 document.addEventListener("DOMContentLoaded",main);
})();
