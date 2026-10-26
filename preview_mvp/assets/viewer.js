"use strict";
/* Event Risk Graph — minimal Marco UI using original public source seeds.
   Live venue/source questions are only loaded from the authenticated MotherDuck API.
   Research hypotheses and catalog factor definitions are not financial betas.
*/
(()=>{
 const $=id=>document.getElementById(id);
 const state={nodes:new Map(),edges:[],adj:new Map(),selected:null,tab:"entities",
              key:"",sourceQuestions:[],network:null,runtime:null};
 const typeColor={question:"question",entity:"entity",security:"security",factor:"factor",
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
 function nodeType(n){return n.type==="question"?"Source question":n.type==="event"?"Hypothetical scenario":
   n.type==="factor"?"Factor definition":n.type==="channel"?"Economic channel":n.type==="security"?"Security":"Entity";}
 function graphNeighbors(id){
   return (state.adj.get(id)||[]).map(edge=>({edge,other:edge.src===id?edge.dst:edge.src}))
     .filter(x=>state.nodes.has(x.other));
 }
 function browse(){
   const ids=[...state.nodes.values()].filter(n=>state.tab==="questions"?
     n.type==="question":n.type==={entities:"entity",securities:"security",factors:"factor"}[state.tab]);
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
     li.append(mk("span",n.type==="security"?n.subtitle||"":n.type==="factor"?n.subtitle||"":n.type==="question"?"DB":"", "num"));
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
   addRow(host,"Source",n.liveWarehouse?"MotherDuck / graph_nodes":
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
   host.append(mk("p","References are not validated causal impact, return betas or trading recommendations.","note"));
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
 function graph(id){
   if(!state.network){
     $("empty").textContent="Graph unavailable: original vis-network library could not load.";
     return;
   }
   const ids=visible(id);
   const getColor=n=>getComputedStyle(document.documentElement)
     .getPropertyValue("--"+(typeColor[n.type]||"factor")).trim()||"#888";
   const nodes=[...ids].map(key=>{
     const n=state.nodes.get(key),type=n.type;
     return {id:key,label:(n.ticker||n.name).slice(0,38),
       shape:type==="security"?"square":type==="entity"?"diamond":type==="factor"?"box":"dot",
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
   state.network.setData({nodes,edges});
   $("empty").hidden=true;$("caption").hidden=false;
   $("caption").textContent=nodes.length+" nodes · "+edges.length+" source/reference edges";
   requestAnimationFrame(()=>state.network.fit({animation:false}));
 }
 async function select(id){
   if(!state.nodes.has(id))return;
   state.selected=id;browse();detail(id);graph(id);
   if(state.nodes.get(id).liveWarehouse&&state.key)await loadNeighbors(id);
 }
 async function request(path){
   const r=await fetch(path,{cache:"no-store",headers:{"X-Analyst-Key":state.key}});
   let data;try{data=await r.json()}catch(_){throw Error("Invalid server response");}
   if(!r.ok)throw Error(data.error||"HTTP "+r.status);
   return data;
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
          type:["question","entity","security","factor"].includes(r.node_type)?r.node_type:"entity",
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
   state.key=$("analyst-key").value.trim();$("analyst-key").value="";
   if(!state.key){$("live-status").textContent="Enter your issued analyst API key.";return;}
   try{
     const d=await request("/api/v1/research/coverage");
     if(d.mode!=="LIVE_DATABASE_COUNT_ONLY")throw Error("Unexpected source contract");
     $("live-status").textContent="Live MotherDuck SELECT verified · source-question display may require separate rights.";
     await searchQuestions();
   }catch(e){state.key="";$("live-status").textContent="Live MotherDuck unavailable: "+e.message;
     browse();}
 }
 function wire(){
   document.querySelectorAll(".tabs button").forEach(button=>{
     button.addEventListener("click",()=>{
       state.tab=button.dataset.tab;
       for(const b of document.querySelectorAll(".tabs button"))
         b.setAttribute("aria-selected",String(b===button));
       $("search").value="";
       if(state.tab==="questions")searchQuestions();else browse();
     });
   });
   let debounce;
   $("search").addEventListener("input",()=>{
     if(state.tab!=="questions")return browse();
     clearTimeout(debounce);debounce=setTimeout(searchQuestions,300);
   });
   $("depth").addEventListener("change",()=>state.selected&&graph(state.selected));
   $("show-factors").addEventListener("change",()=>state.selected&&graph(state.selected));
   $("connect").addEventListener("click",connect);
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
       fetch("/api/v1/graph",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Graph HTTP "+r.status);return r.json()}),
       fetch("/api/v1/runtime",{cache:"no-store"}).then(r=>r.json())
     ]);
     if(g.mode!=="PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE")
       throw Error("Unexpected research graph provenance");
     for(const n of g.nodes)state.nodes.set(n.id,n);
     state.edges=g.edges;state.runtime=r;reindex();
     $("live-status").textContent=r.connection_tested?
       "Server queried MotherDuck · sign in to load source questions.":
       r.database_credentials_present?"Warehouse configured; not yet verified for this session.":
       "Not connected: Railway MOTHERDUCK_TOKEN is not configured.";
     if(typeof vis!=="undefined"&&vis.Network){
       state.network=new vis.Network($("graph"),{nodes:[],edges:[]},{
         physics:{solver:"forceAtlas2Based",forceAtlas2Based:{gravitationalConstant:-75,
           springLength:140,avoidOverlap:.5},stabilization:{iterations:100}},
         interaction:{hover:true,tooltipDelay:100},
         nodes:{borderWidth:2},edges:{smooth:true}});
       state.network.on("stabilizationIterationsDone",()=>state.network.setOptions({physics:false}));
       state.network.on("click",p=>{if(p.nodes.length)select(p.nodes[0])});
       new ResizeObserver(()=>state.network.redraw()).observe($("canvas-wrap"));
     }
     browse();
     const first=state.nodes.has("entity:Q865")?"entity:Q865":
       [...state.nodes.values()].find(n=>n.type==="entity")?.id;
     if(first)select(first);
   }catch(e){$("empty").textContent="Source unavailable: "+e.message;
     $("live-status").textContent="Graph unavailable";}
 }
 document.addEventListener("DOMContentLoaded",main);
})();
