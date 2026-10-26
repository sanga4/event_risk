"use strict";
document.addEventListener("DOMContentLoaded",async()=>{
  const by=id=>document.getElementById(id);
  const cell=(tag,text)=>{const el=document.createElement(tag);el.textContent=String(text);return el;};
  by("print-report").addEventListener("click",()=>window.print());
  try{
    const result=await fetch("/api/v1/capabilities",{cache:"no-store"});
    if(!result.ok)throw Error("HTTP "+result.status);
    const r=await result.json();
    if(r.source_mode!=="REQUEST_TIME_READ_OF_FROZEN_AUDITED_SNAPSHOTS"||
      r.institutional_release_approved!==false||r.continuous_market_refresh_enabled!==false)
      throw Error("Unexpected research status");
    by("report-meta").textContent="Generated "+r.generated_at_utc+" · Source data as of "+r.snapshot_as_of_utc+
      " · Graph as of "+r.graph_as_of_utc;
    const cards=[
      ["Graph nodes",r.graph.nodes],["Typed relations",r.graph.edges],
      ["Securities",r.graph.node_types.security],["Risk factors",r.graph.node_types.factor]
    ];
    for(const [name,count] of cards){
      const d=document.createElement("div");d.className="report-stat";
      d.append(cell("strong",count),cell("span",name));by("report-stats").append(d);
    }
    for(const c of r.capabilities){
      const tr=document.createElement("tr");
      tr.append(cell("td",c.name),cell("td",c.earlier),cell("td",c.now));
      const status=cell("td",c.status.replaceAll("_"," "));status.className="tag";tr.append(status);
      by("capabilities").append(tr);
    }
    const g=r.release;
    by("release-status").textContent=g.automatic_passed+" / "+g.automatic_total+" automatic gates passed; "+
      g.automatic_blocked+" blocked and "+g.manual_blocked+" separate manual gates unresolved. "+
      "Institutional release: NOT APPROVED. Original BEA packets were received after this release-gate snapshot.";
    for(const text of r.limitations){
      const p=cell("p", "• "+text);p.style.color="var(--ink-2)";p.style.fontSize="12px";
      by("limitations").append(p);
    }
  }catch(e){
    by("report-meta").textContent="Capability report unavailable: "+e.message+"; no fallback claims have been invented.";
    by("release-status").textContent="Unable to independently retrieve release evidence.";
  }
});
