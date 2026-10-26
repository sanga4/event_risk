"use strict";
(function(){
  let rows=[];
  let excelHost=false;
  const status=document.getElementById("excel-status"), insert=document.getElementById("insert");
  const fmt=new Intl.NumberFormat("en-US");
  async function load(){
    try{
      const [overview,meta]=await Promise.all([
        fetch("/api/v1/overview",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Aggregate endpoint unavailable");return r.json();}),
        fetch("/api/v1/meta",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("Provenance endpoint unavailable");return r.json();})
      ]);
      if(overview.mode!=="FROZEN_RESEARCH_AGGREGATES"||overview.release.institutional_release_approved!==false||
         overview.snapshot_id!==meta.snapshot_id||meta.live_data_refresh_enabled!==false)
        throw Error("Unacceptable provenance or unexpected live mode");
      rows=overview.metrics.map(m=>[m.label,m.value,m.unit,overview.as_of_utc,m.source,"Research only - not approved"]);
      const root=document.getElementById("excel-metrics");
      root.replaceChildren();
      overview.metrics.slice(0,5).forEach(m=>{
        const line=document.createElement("div");line.className="excel-stat";
        const key=document.createElement("span");key.textContent=m.label;
        const value=document.createElement("strong");value.textContent=fmt.format(m.value);
        line.append(key,value);root.appendChild(line);
      });
      status.textContent=excelHost?"Ready to insert "+rows.length+" audited aggregate metrics (A1:F"+(rows.length+1)+").":"Open in Microsoft Excel to insert into a sheet, or download the CSV.";
      insert.disabled=!excelHost;
    }catch(error){
      document.getElementById("excel-metrics").textContent="No admissible aggregate snapshot";
      status.textContent="Fail closed: "+error.message;insert.disabled=true;
    }
  }
  insert.addEventListener("click",async()=>{
    if(!excelHost||!rows.length||typeof Excel==="undefined")return;
    const values=[["Metric","Value","Unit","Snapshot UTC","Original evidence source","Release status"],...rows];
    try{
      await Excel.run(async ctx=>{
        const sheet=ctx.workbook.worksheets.getActiveWorksheet();
        const range=sheet.getRange("A1:F"+values.length);
        range.values=values;
        sheet.getRange("A1:F1").format.font.bold=true;
        range.format.autofitColumns();
        await ctx.sync();
      });
      status.textContent="Inserted "+rows.length+" research aggregates into the active worksheet. Institutional release remains blocked.";
    }catch(err){status.textContent="Excel insertion failed: "+String(err.message||err);}
  });
  if(typeof Office!=="undefined"&&typeof Office.onReady==="function"){
    Office.onReady(info=>{excelHost=info.host===Office.HostType.Excel;load();});
  }else{load();}
})();
