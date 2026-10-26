"use strict";
(function () {
  const money = new Intl.NumberFormat("en-US");
  const els = (id) => document.getElementById(id);
  const fmt = (n) => typeof n === "number" ? money.format(n) : String(n);
  function node(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function add(parent, ...children) { children.forEach(x => parent.appendChild(x)); return parent; }
  function stat(m) {
    return add(node("div","stat"), node("div","kicker",m.label),
      node("strong","",fmt(m.value)),node("div","description",m.detail || m.unit));
  }
  function line(label,value) {return add(node("div","metric-line"),node("span","",label),node("strong","",fmt(value)));}
  function percent(a,b){return b>0?Math.round(a/b*100):0;}
  function ratioBar(label, current, target, source) {
    const wrap=node("div","depth-wrap");
    const cap=add(node("div","depth-label"),node("span","",label),node("strong","",fmt(current)+" / "+fmt(target)+" days"));
    const bg=node("div","track"); const inner=node("span");inner.style.width=Math.min(100,percent(current,target))+"%";bg.appendChild(inner);
    add(wrap,cap,bg,node("small","",source)); return wrap;
  }
  function pageLabel(page) {
    return {overview:"OVERVIEW",explorer:"EVENT × FACTOR",models:"BETA LABORATORY",quality:"EVIDENCE & QUALITY",roadmap:"COMPLETION TRACKER"}[page];
  }
  function selectPage(page) {
    document.querySelectorAll(".page").forEach(e => e.hidden=e.id!=="page-"+page);
    document.querySelectorAll("[data-page]").forEach(b => {b.classList.toggle("active",b.dataset.page===page);b.setAttribute("aria-current",b.dataset.page===page?"page":"false");});
    els("crumb-current").textContent=pageLabel(page);
    document.querySelector(".sidebar").classList.remove("open");
    window.scrollTo({top:0,behavior:"instant"});
  }
  function overview(x) {
    els("snapshot-asof").textContent="SNAPSHOT · "+x.as_of_utc.replace("T"," ").replace("Z"," UTC");
    const prominent=["venue_receipts","asof_grid","paired_losses","missing_fields"];
    x.metrics.filter(m=>prominent.includes(m.key)).sort((a,b)=>prominent.indexOf(a.key)-prominent.indexOf(b.key))
      .forEach(m=>els("hero-cards").appendChild(stat(m)));
    const r=x.release,p=percent(r.automatic_passed,r.automatic_total);
    els("gate-percent").textContent=p+"%";els("gate-bar").style.width=p+"%";
    add(els("gate-details"),node("span","","✓ "+r.automatic_passed+" passed"),node("span","","× "+r.automatic_blocked+" blocked"),node("span","","! "+r.manual_blocked+" manual"));
    els("gate-warning").textContent="Last gate: "+r.gate_as_of_utc+". It PRECEDES newly stored BEA values. Passing this snapshot never authorizes release.";
    const top=[["Retrospective v2",x.metrics.find(m=>m.key==="panel_v2").value],
      ["Source-native v4",x.metrics.find(m=>m.key==="panel_v4").value],
      ["Prospective grid rows",x.metrics.find(m=>m.key==="asof_grid").value],
      ["Venue receipts",x.metrics.find(m=>m.key==="venue_receipts").value]];
    const max=Math.max(...top.map(z=>z[1]));
    for(const [label,value] of top){
      const row=node("div","bar-row"),track=node("div","bar-track"),fill=node("span");
      fill.style.width=(value/max*100).toFixed(2)+"%";
      add(track,fill);add(row,node("div","bar-label",label),track,node("div","bar-value",fmt(value)));els("volume-chart").appendChild(row);
    }
  }
  function explorer(x) {
    const f=x.factors;
    f.examples.forEach((item,i)=>{
      const wrap=node("article","path-card");const graph=node("div","path-graph");
      [["EVENT HYPOTHESIS",item.event],["ECONOMIC CHANNEL",item.channel],["MARKET FACTOR",item.market]].forEach((pair,j)=>{
        if(j>0) graph.appendChild(node("div","path-arrow","→"));
        const stage=node("div","path-stage");add(stage,node("em","",pair[0]),node("strong","",pair[1]));graph.appendChild(stage);
      });
      add(wrap,graph,node("div","path-caption","EXAMPLE "+(i+1)+" · "+item.tag));els("framework").appendChild(wrap);
    });
    add(els("depth-cards"),
      ratioBar("Independent capture calendar dates",f.source_capture_dates_prospective,f.required_capture_dates_research,"A market record is not a new day."),
      ratioBar("Factor observation source dates",f.source_factor_dates_prospective,f.required_factor_dates_research,"Cross-product rows do not increase macro sample size."),
      line("Factor observation labels",f.measured_rate_labels),
      line("Approved event-to-factor mappings",f.approved_event_factor_mappings));
  }
  function models(x) {
    const pairs=[
      {label:"Securities screened",value:48,detail:"Two prespecified variants each"},
      {label:"Model fits",value:x.metrics.find(m=>m.key==="security_models").value,detail:"Original joint funding regressions"},
      {label:"Daily holdout losses",value:x.metrics.find(m=>m.key==="paired_losses").value,detail:"209 shared dates; 48 × 2"},
      {label:"Familywise survivors",value:x.evidence.holm_surviving_models,detail:"Holm-adjusted 5% threshold"}
    ];pairs.forEach(m=>els("model-stats").appendChild(stat(m)));
    add(els("model-checks"),line("Nominal HAC p < 0.05 (before correction)",x.evidence.nominal_hac_p_below_005),
      line("Minimum global Holm-adjusted p",x.evidence.global_holm_min_adjusted_p),
      line("Holm-corrected significant coefficients",x.evidence.holm_surviving_models),
      line("Independently validated event-response betas",x.factors.validated_event_response_betas));
  }
  function quality(x) {
    const e=x.evidence;
    [
      {label:"Field-level rules",value:e.field_rules,detail:"16 source family contracts"},
      {label:"Missing mandatory fields",value:e.missing_fields,detail:"Still structurally absent"},
      {label:"Uncertified fields",value:e.uncertified_required_fields,detail:"Every required field remains uncertified"},
      {label:"Original BEA value cells",value:e.bea_actual_values,detail:"Original HTML hashes independently checked"},
    ].forEach(m=>els("quality-stats").appendChild(stat(m)));
    els("field-count").textContent=fmt(e.missing_fields);
    els("field-bar").style.width=percent(e.mandatory_fields-e.missing_fields,e.mandatory_fields)+"%";
    add(els("field-labels"),node("span","","Structurally present: "+fmt(e.mandatory_fields-e.missing_fields)),
      node("span","","Required: "+fmt(e.mandatory_fields)),node("span","","Independently certified: 0"));
    add(els("bea-lines"),line("Original publisher HTML packets",e.bea_packets),
      line("Source-native released numbers",e.bea_actual_values),
      line("First-known publication clocks verified",e.original_pub_clocks_verified),
      line("Pre-event consensus vintages verified",e.pre_event_consensus_verified),
      line("Approved source rights (these packets)",e.licensed_source_approvals));
  }
  let blockers=[];
  function drawBlockers(search) {
    const root=els("blocker-list");root.replaceChildren();
    const q=search.toLowerCase();
    const filtered=blockers.filter(b=>(b.name+" "+b.owner+" "+b.proof).toLowerCase().includes(q));
    els("blocker-count").textContent=filtered.length+" unresolved requirements";
    for(const b of filtered){
      const card=node("article","blocker"); const body=node("div");
      add(body,node("h3","",b.name),node("p","",b.proof),node("small","","Owner: "+b.owner));
      add(card,node("strong","priority",b.priority),body,node("span","status","BLOCKED"));
      root.appendChild(card);
    }
  }
  async function getJSON(url) {
    const r=await fetch(url,{cache:"no-store",credentials:"same-origin"});
    if(!r.ok)throw Error("HTTP "+r.status);
    return await r.json();
  }
  async function start() {
    document.querySelectorAll("[data-page]").forEach(b=>b.addEventListener("click",()=>selectPage(b.dataset.page)));
    els("menu-toggle").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
    els("blocker-search").addEventListener("input",e=>drawBlockers(e.target.value));
    try {
      const [o,f,e,b]=await Promise.all([
        getJSON("/api/v1/overview"),getJSON("/api/v1/factors"),
        getJSON("/api/v1/evidence"),getJSON("/api/v1/blockers")]);
      if(o.mode!=="FROZEN_RESEARCH_AGGREGATES"||o.release.institutional_release_approved!==false||
         o.snapshot_id!==f.snapshot_id||o.snapshot_id!==e.snapshot_id||o.snapshot_id!==b.snapshot_id)
         throw Error("Unreconciled preview source manifests");
      const x=Object.assign({},o,{factors:f.factors,evidence:e.evidence,blockers:b.blockers});
      overview(x);explorer(x);models(x);quality(x);
      blockers=x.blockers;drawBlockers("");
      els("loading").hidden=true;selectPage("overview");
    } catch(err){
      els("loading").hidden=true;els("error").hidden=false;
      console.error("Preview aggregate fetch refused:",err.message);
    }
  }
  document.addEventListener("DOMContentLoaded",start);
})();
