"use strict";
/* EventRisk research knowledge graph.
 * Source data is public repository analyst priors + illustrative scenarios.
 * NOT a financial model, venue live quote feed, factor beta or PIT-valid surprise.
 * Canvas rendering avoids external JS/CDNs or vendor-data credentials.
 */
(function () {
  const $ = id => document.getElementById(id);
  const TYPES = {
    event: {title:"Event",plural:"EVENT SCENARIOS & OBSERVED RELEASES",color:"#4985ca",radius:13},
    entity: {title:"Entity",plural:"ENTITY REFERENCES",color:"#d18d56",radius:10},
    security: {title:"Security",plural:"SECURITIES & ETFS",color:"#2fa58b",radius:10},
    channel: {title:"Economic channel",plural:"ECONOMIC TRANSMISSION",color:"#9277c2",radius:10},
    factor: {title:"Risk factor",plural:"FACTOR DEFINITIONS",color:"#657d98",radius:10}
  };
  const LANES={event:-330,entity:-110,security:180,channel:-75,factor:220};
  const canvas=$("network"),ctx=canvas.getContext("2d",{alpha:true});
  const state={
    nodes:[],edges:[],byId:new Map(),positions:new Map(),visibleNodes:[],visibleEdges:[],
    focus:"event:taiwan",previous:[],tab:"event",depth:2,full:false,labels:false,
    hidePrior:false,search:"",warehouseOffset:0,warehouseEvents:[],camera:{zoom:1,panX:0,panY:0},
    w:0,h:0,ratio:1,motion:null,hover:null,layoutIterations:0,anim:false
  };
  const nfmt=new Intl.NumberFormat("en-US");
  function el(tag,cls,value){const x=document.createElement(tag);if(cls)x.className=cls;if(value!==undefined)x.textContent=value;return x;}
  function append(parent,...children){children.forEach(x=>parent.appendChild(x));return parent;}
  function stableHash(id){let v=2166136261;for(let i=0;i<id.length;i++)v=Math.imul(v^id.charCodeAt(i),16777619);return v>>>0;}
  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  function labelFor(n){return n.type==="security"?(n.ticker||n.name):n.name;}
  function truncate(text,max){return text.length>max?text.slice(0,max-1)+"…":text;}
  function statusDescription(n){
    switch(n.review_status){
      case "ILLUSTRATIVE_SCENARIO_NOT_AN_EVENT_OBSERVATION":return "Illustrative scenario · not a confirmed current event or forecast";
      case "ORIGINAL_OFFICIAL_VALUE_RECEIPT_RESEARCH_ONLY":return "Observed official economic number · first-publication vintage unverified";
      case "ANALYST_PRIOR_UNVERIFIED":return "Public seed analyst prior · not an empirically estimated beta";
      case "CATALOG_DEFINITION_NOT_MODEL_APPROVAL":return "Qualitative factor catalogue definition · not certified financial exposure";
      default:return "Unreviewed research relationship · not institutionally approved";
    }
  }
  function buildList(){
    const q=state.search.toLowerCase().trim();
    const items=state.nodes.filter(n=>(q || n.type===state.tab)&&(
      !q||[n.name,n.ticker,n.description,n.subtitle].some(s=>String(s||"").toLowerCase().includes(q))));
    const list=$("node-list");list.replaceChildren();
    $("list-title").textContent=q?"SEARCH ACROSS ALL GRAPH TYPES":TYPES[state.tab].plural;
    $("list-count").textContent=items.length+" items";
    for(const n of items){
      const btn=el("button","node-item");btn.type="button";btn.setAttribute("role","option");
      const isSel=n.id===state.focus;btn.classList.toggle("selected",isSel);btn.setAttribute("aria-selected",String(isSel));
      const dot=el("i","indicator "+n.type),middle=el("span","name",n.name);
      const tag=el("small","",n.ticker|| (n.source_received_at?"BEA":n.type==="event"?"SCENARIO":""));
      append(btn,dot,middle,tag);btn.addEventListener("click",()=>selectNode(n.id,true));list.appendChild(btn);
    }
    if(!items.length)list.appendChild(el("p","detail-welcome","No matching graph nodes."));
    $("total-nodes").textContent=nfmt.format(state.nodes.length);
  }
  function changeTab(type){
    if(!TYPES[type])return;
    state.tab=type;document.querySelectorAll("[data-kind]").forEach(b=>{
      const active=b.dataset.kind===type;
      b.classList.toggle("active",active);b.setAttribute("aria-selected",String(active));
    });
    buildList();
  }
  function selectNode(id,remember=true){
    if(!state.byId.has(id))return;
    if(remember&&state.focus!==id)state.previous.push(state.focus);
    state.focus=id;
    $("back-focus").disabled=!state.previous.length;
    $("graph-caption").textContent=state.byId.get(id).name;
    if(!state.full)updateVisible();
    else draw();
    changeTab(state.byId.get(id).type);
    drawDetail(state.byId.get(id));
    $("detail-panel").classList.add("open");
    if(state.byId.get(id)?.liveWarehouse)loadNeighbors(id);
  }
  function initializePositions(){
    state.positions.clear();
    const groups={};
    for(const t of Object.keys(TYPES))groups[t]=state.nodes.filter(n=>n.type===t).sort((a,b)=>a.name.localeCompare(b.name));
    for(const [type,group] of Object.entries(groups)){
      const step=type==="security"?37:type==="event"?77:49;
      group.forEach((n,i)=>{
        const h=stableHash(n.id),jitter=((h%31)-15);
        state.positions.set(n.id,{x:LANES[type]+jitter*2,y:(i-(group.length-1)/2)*step+jitter*0.9,vx:0,vy:0});
      });
    }
  }
  function updateVisible(){
    const usedEdges=state.edges.filter(e=>!(state.hidePrior&&e.type==="research_exposure_prior"));
    let nodeIds;
    if(state.full)nodeIds=new Set(state.nodes.map(n=>n.id));
    else{
      nodeIds=new Set([state.focus]);
      for(let depth=0;depth<state.depth;depth++){
        const next=new Set(nodeIds);
        for(const e of usedEdges){
          if(nodeIds.has(e.src))next.add(e.dst);
          if(nodeIds.has(e.dst))next.add(e.src);
        }
        nodeIds=next;
      }
    }
    // Bound canvas density. The full 543-security/108-factor catalog remains
    // searchable in the left pane; we don't render hundreds of unreadable labels.
    const ids=[...nodeIds].filter(id=>state.byId.has(id));
    const allCandidates=state.nodes.filter(n=>nodeIds.has(n.id));
    if(state.full){
      const perKind={event:8,entity:40,security:85,channel:22,factor:45};
      const selected=[];for(const [kind,max] of Object.entries(perKind))
        selected.push(...allCandidates.filter(n=>n.type===kind).slice(0,max));
      nodeIds=new Set(selected.map(n=>n.id));
    }else if(nodeIds.size>150){
      const adjacent=new Set([state.focus]);
      for(const e of usedEdges)if(e.src===state.focus)adjacent.add(e.dst);else if(e.dst===state.focus)adjacent.add(e.src);
      const scored=allCandidates.map(n=>({n,priority:n.id===state.focus?0:adjacent.has(n.id)?1:2}));
      scored.sort((a,b)=>a.priority-b.priority||a.n.name.localeCompare(b.n.name));
      nodeIds=new Set(scored.slice(0,150).map(x=>x.n.id));
    }
    state.visibleNodes=state.nodes.filter(n=>nodeIds.has(n.id));
    state.visibleEdges=usedEdges.filter(e=>nodeIds.has(e.src)&&nodeIds.has(e.dst));
    $("visible-nodes").textContent=String(state.visibleNodes.length);
    $("visible-edges").textContent=String(state.visibleEdges.length);
    $("full-network").classList.toggle("active",state.full);
    $("full-network").textContent=state.full?"Focus view":"Sample view";
    layoutGraph();
  }
  function layoutGraph(){
    const groups={};for(const type of Object.keys(TYPES))groups[type]=state.visibleNodes.filter(n=>n.type===type).sort((a,b)=>a.name.localeCompare(b.name));
    for(const [type,ns] of Object.entries(groups)){
      const lane=LANES[type],count=ns.length;
      const spacing=count>35?30:count>20?34:count>12?42:count>7?52:65;
      ns.forEach((n,i)=>{
        const p=state.positions.get(n.id);
        const jitter=(stableHash(n.id)%43)-21;
        p.x=lane+jitter*1.15;p.y=(i-(count-1)/2)*spacing+jitter*.7;
        p.vx=0;p.vy=0;
      });
    }
    state.layoutIterations=0;
    // Independent static graph layout; no force generation of new relationships.
    for(let i=0;i<24;i++)stepPhysics();
    fitGraph();
  }
  function stepPhysics(){
    const p=state.positions,ns=state.visibleNodes,es=state.visibleEdges;
    // Pull directly connected nodes into readable arrangements.
    for(const e of es){
      const a=p.get(e.src),b=p.get(e.dst);
      let dx=b.x-a.x,dy=b.y-a.y,dist=Math.hypot(dx,dy)||1;
      const desired=e.type==="research_exposure_prior"?170:155;
      const f=clamp((dist-desired)*.005,-1.3,1.3);
      const vx=(dx/dist)*f,vy=(dy/dist)*f;
      a.vx+=vx;a.vy+=vy;b.vx-=vx;b.vy-=vy;
    }
    // Spatial repulsion, capped to avoid teleports for dense full graph.
    for(let i=0;i<ns.length;i++)for(let j=i+1;j<ns.length;j++){
      const a=p.get(ns[i].id),b=p.get(ns[j].id),dx=a.x-b.x,dy=a.y-b.y;
      const d2=Math.max(100,dx*dx+dy*dy),d=Math.sqrt(d2);
      if(d>215)continue;
      const force=Math.min(1.1,1600/d2);
      const x=dx/d*force,y=dy/d*force;
      a.vx+=x;a.vy+=y;b.vx-=x;b.vy-=y;
    }
    for(const n of ns){
      const z=p.get(n.id);
      z.vx+=(LANES[n.type]-z.x)*.007;
      z.vy+=-z.y*.0004;
      z.vx=clamp(z.vx*.78,-6,6);z.vy=clamp(z.vy*.78,-6,6);
      z.x+=z.vx;z.y+=z.vy;
    }
  }
  function resize(){
    const bound=$("canvas-wrap").getBoundingClientRect();
    state.w=Math.max(100,bound.width);state.h=Math.max(100,bound.height);
    state.ratio=Math.min(2.5,window.devicePixelRatio||1);
    canvas.width=Math.floor(state.w*state.ratio);
    canvas.height=Math.floor(state.h*state.ratio);
    canvas.style.width=state.w+"px";canvas.style.height=state.h+"px";
    draw();
  }
  function fitGraph(){
    if(!state.visibleNodes.length)return;
    const locs=state.visibleNodes.map(n=>state.positions.get(n.id));
    const xs=locs.map(p=>p.x),ys=locs.map(p=>p.y);
    const minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);
    state.camera.zoom=clamp(Math.min((state.w-120)/(maxx-minx+260),(state.h-100)/(maxy-miny+150)),.16,1.4);
    state.camera.panX=-(minx+maxx)/2*state.camera.zoom;
    state.camera.panY=-(miny+maxy)/2*state.camera.zoom;
    draw();
  }
  function screenToWorld(sx,sy){
    return {x:(sx-state.w/2-state.camera.panX)/state.camera.zoom,
            y:(sy-state.h/2-state.camera.panY)/state.camera.zoom};
  }
  function drawArrow(ax,ay,bx,by,color){
    const theta=Math.atan2(by-ay,bx-ax),size=7,tx=bx-Math.cos(theta)*12,ty=by-Math.sin(theta)*12;
    ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(tx,ty);
    ctx.lineTo(tx-Math.cos(theta-.5)*size,ty-Math.sin(theta-.5)*size);
    ctx.lineTo(tx-Math.cos(theta+.5)*size,ty-Math.sin(theta+.5)*size);
    ctx.closePath();ctx.fill();
  }
  function drawShape(type,x,y,r){
    ctx.beginPath();
    if(type==="event"){ctx.arc(x,y,r,0,Math.PI*2);}
    else if(type==="entity"){ctx.moveTo(x,y-r);ctx.lineTo(x+r,y);ctx.lineTo(x,y+r);ctx.lineTo(x-r,y);ctx.closePath();}
    else if(type==="factor"){ctx.moveTo(x,y-r);ctx.lineTo(x+r,y);ctx.lineTo(x,y+r);ctx.lineTo(x-r,y);ctx.closePath();}
    else if(type==="security"){ctx.rect(x-r*.82,y-r*.82,r*1.64,r*1.64);}
    else {ctx.roundRect(x-r,y-r,r*2,r*2,4);}
  }
  function draw(){
    if(!ctx||!state.w||!state.h)return;
    ctx.setTransform(state.ratio,0,0,state.ratio,0,0);
    ctx.clearRect(0,0,state.w,state.h);
    ctx.save();const cam=state.camera;
    ctx.translate(state.w/2+cam.panX,state.h/2+cam.panY);
    ctx.scale(cam.zoom,cam.zoom);
    for(const e of state.visibleEdges){
      const a=state.positions.get(e.src),b=state.positions.get(e.dst);
      if(!a||!b)continue;
      const focus=e.src===state.focus||e.dst===state.focus,prior=e.type==="research_exposure_prior";
      const color=focus?"#8caea9":prior?"#b4d1c9":"#b9c5ce";
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
      ctx.strokeStyle=color;ctx.globalAlpha=focus?0.9:0.60;ctx.lineWidth=prior?1.5:1.1;
      ctx.setLineDash(prior?[5,4]:[4,5]);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;
      drawArrow(a.x,a.y,b.x,b.y,color);
      if(state.labels && cam.zoom>.45){
        const midx=(a.x+b.x)/2,midy=(a.y+b.y)/2;
        const text=prior?(e.weight+" analyst prior"):e.type.replaceAll("_"," ");
        ctx.font="9px system-ui";ctx.textAlign="center";ctx.fillStyle="#9babb1";ctx.fillText(truncate(text,32),midx,midy-7);
      }
    }
    for(const n of state.visibleNodes){
      const p=state.positions.get(n.id),isSelected=n.id===state.focus,isHover=n.id===state.hover;
      const type=TYPES[n.type],radius=type.radius*(isSelected?1.18:1);
      if(isSelected){ctx.beginPath();ctx.arc(p.x,p.y,radius+7,0,Math.PI*2);ctx.fillStyle="#c0e9dd";ctx.fill();}
      drawShape(n.type,p.x,p.y,radius);ctx.fillStyle=type.color;ctx.globalAlpha=isHover||isSelected?1:0.94;ctx.fill();
      ctx.globalAlpha=1;ctx.strokeStyle="#fff";ctx.lineWidth=1.8;ctx.stroke();
      if(isHover){ctx.beginPath();ctx.arc(p.x,p.y,radius+5,0,Math.PI*2);ctx.strokeStyle=type.color;ctx.lineWidth=1;ctx.stroke();}
      const text=truncate(labelFor(n),n.type==="event"?33:22);
      ctx.font=(isSelected?"700 ":"600 ")+"11px system-ui";ctx.textAlign="center";
      const width=Math.min(230,ctx.measureText(text).width+12),bx=p.x-width/2,by=p.y+radius+10;
      ctx.fillStyle="rgba(255,255,255,.87)";ctx.fillRect(bx,by-4,width,19);
      ctx.fillStyle=isSelected?"#204b50":"#50656a";ctx.fillText(text,p.x,by+9);
    }
    ctx.restore();
  }
  function findAt(x,y){
    const p=screenToWorld(x,y);
    const zoom=state.camera.zoom;
    const nodeList=state.visibleNodes.slice().reverse();
    for(const n of nodeList){
      const at=state.positions.get(n.id);
      if(Math.hypot(p.x-at.x,p.y-at.y)<Math.max(14,TYPES[n.type].radius+4,10/zoom))return n;
    }
    return null;
  }
  function canvasXY(e){const box=canvas.getBoundingClientRect();return {x:e.clientX-box.left,y:e.clientY-box.top};}
  function wireCanvas(){
    canvas.addEventListener("pointerdown",e=>{
      if(e.button!==0)return;
      const pos=canvasXY(e),hit=findAt(pos.x,pos.y);
      state.motion={pointerId:e.pointerId,startX:pos.x,startY:pos.y,lastX:pos.x,lastY:pos.y,hit:hit?.id||null,moved:false};
      canvas.setPointerCapture(e.pointerId);canvas.classList.add("dragging");
    });
    canvas.addEventListener("pointermove",e=>{
      const pt=canvasXY(e),motion=state.motion;
      if(motion&&motion.pointerId===e.pointerId){
        const dx=pt.x-motion.lastX,dy=pt.y-motion.lastY;
        if(Math.hypot(pt.x-motion.startX,pt.y-motion.startY)>4)motion.moved=true;
        if(motion.moved){
          if(motion.hit){const p=state.positions.get(motion.hit);p.x+=dx/state.camera.zoom;p.y+=dy/state.camera.zoom;}
          else{state.camera.panX+=dx;state.camera.panY+=dy;}
          draw();
        }
        motion.lastX=pt.x;motion.lastY=pt.y;return;
      }
      const hit=findAt(pt.x,pt.y);
      const next=hit?.id||null;
      if(next!==state.hover){state.hover=next;canvas.style.cursor=next?"pointer":"grab";draw();}
    });
    const end=e=>{
      const m=state.motion;if(!m||m.pointerId!==e.pointerId)return;
      canvas.classList.remove("dragging");
      if(!m.moved&&m.hit)selectNode(m.hit);
      state.motion=null;
      draw();
    };
    canvas.addEventListener("pointerup",end);
    canvas.addEventListener("pointercancel",end);
    canvas.addEventListener("wheel",e=>{
      e.preventDefault();
      const pt=canvasXY(e),before=screenToWorld(pt.x,pt.y);
      state.camera.zoom=clamp(state.camera.zoom*(e.deltaY<0?1.12:.88),.12,3.2);
      state.camera.panX=pt.x-state.w/2-before.x*state.camera.zoom;
      state.camera.panY=pt.y-state.h/2-before.y*state.camera.zoom;draw();
    },{passive:false});
    canvas.addEventListener("keydown",e=>{
      const cam=state.camera;
      if(e.key==="+"){cam.zoom=clamp(cam.zoom*1.2,.12,3.2);}
      else if(e.key==="-"){cam.zoom=clamp(cam.zoom/1.2,.12,3.2);}
      else if(e.key==="ArrowLeft"){cam.panX+=30;}
      else if(e.key==="ArrowRight"){cam.panX-=30;}
      else if(e.key==="ArrowUp"){cam.panY+=30;}
      else if(e.key==="ArrowDown"){cam.panY-=30;}
      else return;
      e.preventDefault();draw();
    });
  }
  function drawDetail(n){
    const detail=$("detail");detail.replaceChildren();
    const body=el("div","detail-body");
    append(body,el("span","node-type-badge "+n.type,TYPES[n.type].title),el("h2","",n.name),el("div","detail-sub",n.subtitle||"Research reference"));
    append(body,el("div","detail-alert",statusDescription(n)));
    append(body,el("div","detail-section-title","DESCRIPTION"),el("p","detail-description",n.description||"No additional verified description."),el("div","detail-divider"));
    const kv=el("dl","detail-kv");
    const kvRow=(label,value)=>{const row=el("div","kvrow");append(row,el("dt","",label),el("dd","",String(value)));kv.appendChild(row);};
    if(n.ticker)kvRow("Symbol",n.ticker);
    if(n.country)kvRow("Country",n.country);
    if(n.sector&&n.sector!=="Unspecified")kvRow("Sector",n.sector);
    if(n.reported_value!==null&&n.reported_value!==undefined)kvRow("Reported actual",n.reported_value+" "+(n.unit||""));
    if(n.source_received_at)kvRow("Retrieved",n.source_received_at);
    kvRow("Graph type",TYPES[n.type].title);
    kvRow("Review status",n.review_status);
    if(kv.childNodes.length)body.appendChild(kv);
    const edges=state.edges.filter(e=>e.src===n.id||e.dst===n.id).sort((a,b)=>{
      const pa=a.type==="research_exposure_prior"?0:1,pb=b.type==="research_exposure_prior"?0:1;
      return pa-pb||(b.weight||0)-(a.weight||0);
    });
    append(body,el("div","detail-section-title","CONNECTED NODES · "+edges.length));
    const container=el("div","detail-relations");
    for(const edge of edges.slice(0,27)){
      const target=state.byId.get(edge.src===n.id?edge.dst:edge.src);
      if(!target)continue;
      const btn=el("button","detail-rel");btn.type="button";
      const row=el("div","detail-rel-top");
      append(row,el("span","detail-rel-name",target.name));
      if(edge.weight!==undefined)row.appendChild(el("span","detail-rel-weight",nfmt.format(edge.weight)+" prior"));
      append(btn,row,el("div","detail-rel-info",
        (edge.src===n.id?"→ ":"← ")+edge.type.replaceAll("_"," ")+" · "+truncate(edge.summary||"Unreviewed relation",88)));
      btn.addEventListener("click",()=>selectNode(target.id));container.appendChild(btn);
    }
    if(edges.length>27)container.appendChild(el("p","source-line","+"+(edges.length-27)+" additional edges; use the graph API to inspect the complete public-seed subset."));
    if(!edges.length)container.appendChild(el("div","detail-welcome","No connected source-approved edges."));
    body.appendChild(container);
    append(body,el("div","detail-section-title","SOURCE & LINEAGE"),el("div","source-line",n.source||"Unspecified research source"));
    if(n.reference||n.source_url){
      const a=el("a","source-line","Open publisher/reference ↗");
      a.href=n.source_url||n.reference;a.target="_blank";a.rel="noopener noreferrer";
      body.appendChild(a);
    }
    append(body,el("div","detail-section-title","METHODOLOGY CAUTION"),
      el("div","safety-note","Graph direction means proposed relationship type, not market direction. Seed weights are editable analyst priors, not measured sensitivities, probabilities, alphas or confidence intervals."));
    // The analyst research desk is a read-only warehouse drilldown, not an
    // event-price impact forecast. It requires an issued key and an approved source.
    if(n.type==="security" && n.ticker){
      const action=el("button","detail-rel","Load researched factor regressions ↗");
      action.type="button";action.addEventListener("click",()=>openResearch(n,"models"));body.appendChild(action);
    }
    if(n.type==="factor"){
      const action=el("button","detail-rel","Load warehouse factor observations ↗");
      action.type="button";action.addEventListener("click",()=>openResearch(n,"factor-series"));body.appendChild(action);
    }
    const result=el("div","model-result");result.id="model-result";
    body.appendChild(result);
    detail.appendChild(body);
  }
  async function openResearch(node,kind){
    const container=$("model-result");if(!container)return;
    container.replaceChildren(el("p","source-line","Querying authenticated MotherDuck research..."));
    const path=kind==="models"?"/api/v1/research/models?ticker="+encodeURIComponent(node.ticker):
       "/api/v1/research/factor-series?factor_id="+encodeURIComponent(node.id.replace(/^factor:/,""))+"&limit=120";
    try{
      const response=await fetch(path,{headers:{"X-Analyst-Key":sessionStorage.getItem("eventrisk_analyst_key")||""},cache:"no-store"});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||"Research API rejected source");
      container.replaceChildren(el("h3","","Warehouse research (not approved beta)"));
      for(const entry of data.rows||[]){
        const card=el("div","detail-rel");
        for(const [key,value] of Object.entries(entry)){
          if(value===null||typeof value==="object")continue;
          append(card,el("div","source-line",key+": "+value));
        }
        container.appendChild(card);
      }
      if(!(data.rows||[]).length)container.appendChild(el("p","source-line","No source records for this identifier."));
    }catch(e){container.replaceChildren(el("div","detail-alert",
      "Not available: "+e.message+". A scoped read-only token, analyst key, and approved derived-data rights are required."));}
  }
  async function coverage(){
    const host=$("warehouse-cards");host.replaceChildren(el("p","source-line","Fetching live database counts..."));
    try{
      const r=await fetch("/api/v1/research/coverage",{headers:{"X-Analyst-Key":sessionStorage.getItem("eventrisk_analyst_key")||""},cache:"no-store"});
      const d=await r.json();if(!r.ok)throw Error(d.error||"HTTP "+r.status);
      host.replaceChildren();
      for(const row of d.coverage){
        const box=el("article","");
        append(box,el("b","",Number(row.value).toLocaleString()),el("h3","",row.metric.replaceAll("_"," ")),
          el("p","","Read-only query; not a count of independently validated economic events"));
        host.appendChild(box);
      }
      $("warehouse-message").textContent="Live warehouse COUNT queries verified for this session; raw source redisplay still requires permission.";
    }catch(e){host.replaceChildren(el("p","detail-alert","Warehouse not connected: "+e.message));
      $("warehouse-message").textContent="Live query not enabled: "+e.message;}
  }
  function researchHeaders(){
    return {"X-Analyst-Key":sessionStorage.getItem("eventrisk_analyst_key")||""};
  }
  function addLiveNode(row){
    if(!row?.node_id||state.byId.has(row.node_id))return;
    const type=row.node_type==="security"?"security":row.node_type==="factor"?"factor":
      row.node_type==="entity"?"entity":"event";
    const n={id:row.node_id,type,name:row.name||row.node_id,
      subtitle:"MotherDuck source graph · "+(row.node_type||"question"),
      description:"Real recorded source graph item. Provider-original first-published timestamp and point-in-time release remain unverified.",
      review_status:"LIVE_SOURCE_RESEARCH_NOT_APPROVED",liveWarehouse:true,source:"graph_nodes"};
    state.nodes.push(n);state.byId.set(n.id,n);
    state.positions.set(n.id,{x:LANES[type]+(stableHash(n.id)%65),y:(stableHash(n.id)%200)-100,vx:0,vy:0});
  }
  async function loadNeighbors(nodeId){
    const elResult=$("model-result");
    if(elResult)elResult.replaceChildren(el("p","source-line","Reading bounded live graph neighborhood..."));
    try{
      const r=await fetch("/api/v1/research/graph-neighbors?node_id="+encodeURIComponent(nodeId),
        {headers:researchHeaders(),cache:"no-store"});
      const d=await r.json();if(!r.ok)throw Error(d.error||"HTTP "+r.status);
      for(const n of d.nodes||[])addLiveNode(n);
      const keys=new Set(state.edges.map(e=>e.src+"|"+e.dst+"|"+e.type));
      for(const e of d.edges||[]){
        if(!state.byId.has(e.src_id)||!state.byId.has(e.dst_id))continue;
        const k=e.src_id+"|"+e.dst_id+"|"+e.edge_type;
        if(keys.has(k))continue;
        state.edges.push({src:e.src_id,dst:e.dst_id,type:e.edge_type,
          weight:e.weight,summary:e.note||e.provenance||"Original recorded research graph relation",
          review_status:"RESEARCH_ONLY_NOT_APPROVED"});
        keys.add(k);
      }
      if(state.focus===nodeId){
        updateVisible();drawDetail(state.byId.get(nodeId));
        const out=$("model-result");
        if(out)out.appendChild(el("p","source-line",
          "Live neighbors: "+(d.edges||[]).length+
          ". These are source graph relationships, NOT approved event betas."));
      }
    }catch(e){
      if(elResult)elResult.replaceChildren(el("p","detail-alert",
        "Live neighborhood unavailable: "+e.message));
    }
  }
  async function searchWarehouseEvents(reset=true){
    const output=$("warehouse-message");
    if(reset){state.warehouseOffset=0;state.warehouseEvents=[];}
    output.textContent="Searching source-dated warehouse graph questions...";
    try{
      const q=$("search").value.trim();
      const path="/api/v1/research/events?limit=50&offset="+state.warehouseOffset+
        "&q="+encodeURIComponent(q);
      const r=await fetch(path,{headers:researchHeaders(),cache:"no-store"});
      const d=await r.json();
      if(!r.ok)throw Error(d.error||"HTTP "+r.status);
      for(const row of d.rows||[])addLiveNode({...row,node_type:"question"});
      state.warehouseOffset+=(d.rows||[]).length;
      $("more-warehouse-events").hidden=(d.rows||[]).length<50;
      changeTab("event");
      output.textContent="Warehouse search loaded "+state.warehouseOffset+
        " real source questions (paginated); original provider clock and impact certification unverified.";
    }catch(e){
      $("more-warehouse-events").hidden=true;
      output.textContent="Warehouse event search unavailable: "+e.message+
        ". Source rights, analyst access and a scoped server database token must be configured.";
    }
  }
  function handlers(){
    document.querySelectorAll("[data-kind]").forEach(btn=>btn.addEventListener("click",()=>changeTab(btn.dataset.kind)));
    $("search").addEventListener("input",e=>{state.search=e.target.value;buildList();});
    document.addEventListener("keydown",e=>{
      if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();$("search").focus();}
      if(e.key==="Escape"&&state.search){$("search").value="";state.search="";buildList();}
    });
    document.querySelectorAll("[data-depth]").forEach(b=>b.addEventListener("click",()=>{
      state.depth=Number(b.dataset.depth);
      document.querySelectorAll("[data-depth]").forEach(x=>x.classList.toggle("selected",x===b));
      state.full=false;updateVisible();
    }));
    $("edge-labels").addEventListener("change",e=>{state.labels=e.target.checked;draw();});
    $("hide-analyst").addEventListener("change",e=>{state.hidePrior=e.target.checked;updateVisible();});
    $("full-network").addEventListener("click",()=>{state.full=!state.full;updateVisible();});
    $("fit-graph").addEventListener("click",fitGraph);
    $("zoom-in").addEventListener("click",()=>{state.camera.zoom=clamp(state.camera.zoom*1.2,.12,3.2);draw();});
    $("zoom-out").addEventListener("click",()=>{state.camera.zoom=clamp(state.camera.zoom/1.2,.12,3.2);draw();});
    $("clear-selection").addEventListener("click",()=>selectNode("event:taiwan"));
    $("back-focus").addEventListener("click",()=>{const id=state.previous.pop();if(id)selectNode(id,false);});
    $("notice-close").addEventListener("click",()=>{$("notice-close").parentElement.remove();});
    function page(name){
      const graph=name==="explore",method=name==="about",live=name==="live";
      document.body.classList.toggle("about",!graph);
      $("methodology").hidden=!method;$("live-panel").hidden=!live;
      for(const [id,on] of [["explore-tab",graph],["about-tab",method],["live-tab",live]]){
        const el=$(id);el.classList.toggle("active",on);el.setAttribute("aria-selected",String(on));
      }
      if(graph){resize();fitGraph();}
      if(live)coverage();
    }
    $("about-tab").addEventListener("click",()=>page("about"));
    $("explore-tab").addEventListener("click",()=>page("explore"));
    $("live-tab").addEventListener("click",()=>page("live"));
    $("back-explore").addEventListener("click",()=>page("explore"));
    $("back-from-live").addEventListener("click",()=>page("explore"));
    $("find-warehouse-events").addEventListener("click",()=>searchWarehouseEvents(true));
    $("more-warehouse-events").addEventListener("click",()=>searchWarehouseEvents(false));
    $("connect-warehouse").addEventListener("click",()=>{
      const key=$("analyst-key").value.trim();
      if(key){sessionStorage.setItem("eventrisk_analyst_key",key);$("analyst-key").value="";
        $("warehouse-message").textContent="Key stored for this tab only. Checking live source permissions...";
        coverage();
      }else $("warehouse-message").textContent="An analyst access key is required.";
    });
    document.querySelectorAll(".divider-handle").forEach(handle=>{
      const which=handle.dataset.panel;
      let moving=false;
      handle.addEventListener("pointerdown",e=>{moving=true;handle.setPointerCapture(e.pointerId);handle.classList.add("dragging");});
      handle.addEventListener("pointermove",e=>{
        if(!moving||window.innerWidth<851)return;
        const w=clamp(which==="left"?e.clientX:window.innerWidth-e.clientX,215,window.innerWidth*.48);
        document.documentElement.style.setProperty("--"+which,w+"px");
        resize();
      });
      const stop=()=>{moving=false;handle.classList.remove("dragging");};
      handle.addEventListener("pointerup",stop);handle.addEventListener("pointercancel",stop);
      handle.addEventListener("keydown",e=>{
        const step=e.key==="ArrowLeft"?-18:e.key==="ArrowRight"?18:0;if(!step)return;
        e.preventDefault();const cur=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--"+which))||(which==="left"?305:366);
        const direction=which==="right"?-step:step;
        document.documentElement.style.setProperty("--"+which,clamp(cur+direction,215,window.innerWidth*.48)+"px");resize();
      });
    });
    new ResizeObserver(()=>{resize();}).observe($("canvas-wrap"));
    wireCanvas();
  }
  async function load(){
    handlers();resize();
    try{
      const [g,cat,status]=await Promise.all([
        fetch("/api/v1/graph",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Graph HTTP "+r.status);return r.json();}),
        fetch("/api/v1/catalog",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Catalog HTTP "+r.status);return r.json();}),
        fetch("/api/v1/runtime",{cache:"no-store"}).then(r=>r.json())
      ]);
      if(g.mode!=="PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE"||
         cat.securities_count<500||cat.factors_count!==108||
         !g.nodes?.length||!g.edges?.length)throw Error("Catalog source checks failed");
      state.nodes=g.nodes;state.edges=g.edges;
      state.byId=new Map(g.nodes.map(n=>[n.id,n]));
      for(const edge of g.edges){
        if(!state.byId.has(edge.src)||!state.byId.has(edge.dst)||
           edge.review_status!=="RESEARCH_ONLY_NOT_APPROVED")throw Error("Unreviewed or dangling graph edge");
      }
      $("source-stamp").textContent=cat.securities_count+" securities / "+cat.factors_count+
          " definitions / "+cat.channels.length+" channels · source-repository catalog";
      $("runtime-indicator").textContent=status.direct_database_queries_enabled?
          "SERVER WAREHOUSE CREDENTIAL CONFIGURED":"LIVE WAREHOUSE: SETUP REQUIRED";
      initializePositions();changeTab("event");updateVisible();
      drawDetail(state.byId.get(state.focus));
      $("graph-caption").textContent=state.byId.get(state.focus).name;
      $("graph-loading").hidden=true;fitGraph();
    }catch(e){
      $("graph-loading").hidden=true;$("graph-error").hidden=false;
      $("graph-error").textContent="Catalog unavailable: "+e.message+"; fabricated fallbacks are disabled.";
      console.error("Catalog refused",e.message);
    }
  }
  document.addEventListener("DOMContentLoaded",load);
})();
