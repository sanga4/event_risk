"use strict";
(function(){
  let rows=[],graph=null,excelHost=false;
  const status=document.getElementById("excel-status"),
        insert=document.getElementById("insert"),
        graphButton=document.getElementById("import-graph"),
        fmt=new Intl.NumberFormat("en-US");
  const headers=["Metric","Value","Unit","Snapshot UTC","Original evidence source","Release status"];
  function safe(value){
    if(typeof value!=="string")return value;
    return /^[\s]*[=+\-@\t\r]/.test(value)?"'"+value:value;
  }
  async function jsonFrom(path){
    const r=await fetch(path,{cache:"no-store"});
    if(!r.ok)throw Error(path+" returned HTTP "+r.status);
    return await r.json();
  }
  async function load(){
    try{
      const [overview,meta,g]=await Promise.all([
        jsonFrom("/api/v1/overview"),jsonFrom("/api/v1/meta"),
        jsonFrom("/api/v1/graph")
      ]);
      if(overview.mode!=="FROZEN_RESEARCH_AGGREGATES"||
        overview.release.institutional_release_approved!==false||
        overview.snapshot_id!==meta.snapshot_id||
        meta.live_data_refresh_enabled!==false||
        g.mode!=="FROZEN_PUBLIC_SEED_PRIORS_AND_ILLUSTRATIVE_EVENT_SCENARIOS"||
        g.nodes.length>250||g.edges.length>600||
        g.edges.some(e=>e.review_status!=="RESEARCH_ONLY_NOT_APPROVED"))
        throw Error("Unacceptable preview graph or provenance state");
      rows=overview.metrics.map(m=>[safe(m.label),m.value,safe(m.unit),
        overview.as_of_utc,safe(m.source),"Research only - NOT approved"]);
      graph=g;
      const root=document.getElementById("excel-metrics");root.replaceChildren();
      const summary=[
        ["Graph nodes",g.nodes.length],["Graph relationships",g.edges.length],
        ["Public-seed exposure priors",g.edges.filter(e=>e.type==="research_exposure_prior").length],
        ["Stored venue records (not independent days)",overview.metrics.find(m=>m.key==="venue_receipts")?.value||0],
        ["Institutionally approved event betas",0]
      ];
      for(const [label,value] of summary){
        const line=document.createElement("div");line.className="excel-stat";
        const k=document.createElement("span");k.textContent=label;
        const v=document.createElement("strong");v.textContent=fmt.format(value);
        line.append(k,v);root.append(line);
      }
      insert.disabled=!excelHost;graphButton.disabled=!excelHost;
      status.textContent=excelHost
        ? "Ready: import "+g.nodes.length+" nodes, "+g.edges.length+" links, "
           +rows.length+" metrics and a formula explorer into dedicated ER_ worksheets."
        : "Open this taskpane in Excel to import; plain-browser CSV export still works.";
    }catch(error){
      rows=[];graph=null;insert.disabled=true;graphButton.disabled=true;
      document.getElementById("excel-metrics").textContent="No admissible graph snapshot";
      status.textContent="Fail closed: "+error.message;
    }
  }
  async function ensureSheet(ctx,name){
    let sh=ctx.workbook.worksheets.getItemOrNullObject(name);
    await ctx.sync();
    if(sh.isNullObject)sh=ctx.workbook.worksheets.add(name);
    return sh;
  }
  function writeRows(sh,table){
    if(!table.length||table.length>600)throw Error("Unexpected payload dimensions");
    const cols=table[0].length;
    if(!table.every(r=>r.length===cols))throw Error("Irregular graph payload");
    sh.getRangeByIndexes(0,0,table.length,cols).values=table;
    sh.getRangeByIndexes(0,0,1,cols).format.font.bold=true;
    sh.getRangeByIndexes(0,0,table.length,cols).format.autofitColumns();
  }
  insert.addEventListener("click",async()=>{
    if(!excelHost||!rows.length||typeof Excel==="undefined")return;
    try{
      await Excel.run(async ctx=>{
        const sh=ctx.workbook.worksheets.getActiveWorksheet();
        writeRows(sh,[headers,...rows]);
        await ctx.sync();
      });
      status.textContent="Inserted "+rows.length+" source-attributed aggregates. No approved beta or trading formula was generated.";
    }catch(err){status.textContent="Metric insertion failed: "+String(err.message||err);}
  });
  graphButton.addEventListener("click",async()=>{
    if(!excelHost||!graph||!rows.length||typeof Excel==="undefined")return;
    graphButton.disabled=true;
    status.textContent="Importing research graph and formulas to ER_ worksheets...";
    try{
      const nodeRows=[["Node ID","Node type","Name","Ticker","Source","Review status","Country"],
        ...graph.nodes.map(n=>[n.id,n.type,safe(n.name),safe(n.ticker||""),
          safe(n.source||""),safe(n.review_status||""),safe(n.country||"")])];
      const edgeRows=[["From ID","To ID","Relation type","Analyst-prior weight","Source","Review status","Explanation"],
        ...graph.edges.map(e=>[e.src,e.dst,e.type,e.weight??null,safe(e.source||""),
          "NOT APPROVED",safe(e.summary||"")])];
      const snapshotRows=[headers,...rows];
      await Excel.run(async ctx=>{
        const nodeSheet=await ensureSheet(ctx,"ER_Nodes"),
              edgeSheet=await ensureSheet(ctx,"ER_Edges"),
              metricSheet=await ensureSheet(ctx,"ER_Metrics"),
              explorerSheet=await ensureSheet(ctx,"ER_Explorer");
        // Dedicated names only. Original EventRisk workbook sheets remain intact.
        for(const sh of [nodeSheet,edgeSheet,metricSheet,explorerSheet]){
          sh.getRange("A1:H400").clear(Excel.ClearApplyTo.contents);
        }
        writeRows(nodeSheet,nodeRows);
        writeRows(edgeSheet,edgeRows);
        writeRows(metricSheet,snapshotRows);
        const demo=[
          ["RESEARCH PATH EXPLORER","Editable IDs / results","Source status"],
          ["Graph source",graph.as_of_utc,"FROZEN SOURCE SNAPSHOT"],
          ["Event ID","event:taiwan","Illustrative scenario"],
          ["Entity ID","entity:Q865","Unreviewed involvement"],
          ["Security ID","security:TSM","Original seed prior"],
          ["Economic channel","channel:semiconductor_supply","Illustrative mechanism"],
          ["Risk factor","factor:EQUITY.INDUSTRY.SEMICONDUCTORS","Catalog, not beta"],
          ["","", ""],
          ["Event to entity link",null,"COUNTIFS of public sample graph"],
          ["Entity to security link",null,"COUNTIFS of analyst-prior edges"],
          ["Event to channel link",null,"COUNTIFS of illustrative edges"],
          ["Channel to factor link",null,"COUNTIFS of illustrative edges"],
          ["Two-link security path",null,"Graph connectivity, not price risk"],
          ["Two-link factor path",null,"Graph connectivity, not factor beta"],
          ["Qualitative prior weight",null,"NOT a measured coefficient"],
          ["CAVEAT","No event beta, forecast, alpha, risk weighting, or licensing approval is implied.",""]
        ];
        writeRows(explorerSheet,demo);
        const src="ER_Edges!$A$2:$A$400",dst="ER_Edges!$B$2:$B$400",
          rel="ER_Edges!$C$2:$C$400",wt="ER_Edges!$D$2:$D$400";
        const has=(a,b)=>'=IF(COUNTIFS('+src+','+a+','+dst+','+b+')>0,"YES","NO")';
        explorerSheet.getRange("B9").formulas=[[has("$B$3","$B$4")]];
        explorerSheet.getRange("B10").formulas=[[has("$B$4","$B$5")]];
        explorerSheet.getRange("B11").formulas=[[has("$B$3","$B$6")]];
        explorerSheet.getRange("B12").formulas=[[has("$B$6","$B$7")]];
        explorerSheet.getRange("B13").formulas=[['=IF(AND(B9="YES",B10="YES"),"CONNECTED","NO PATH")']];
        explorerSheet.getRange("B14").formulas=[['=IF(AND(B11="YES",B12="YES"),"CONNECTED","NO PATH")']];
        explorerSheet.getRange("B15").formulas=[['=SUMIFS('+wt+','+src+',$B$4,'+dst+',$B$5,'+rel+',"research_exposure_prior")']];
        explorerSheet.getRange("B3:B7").format.fill="#FFF5C8";
        explorerSheet.getRange("B3:B7").format.font.color="#0000FF";
        explorerSheet.getRange("A1:C1").format.font.bold=true;
        explorerSheet.activate();
        await ctx.sync();
      });
      status.textContent="Imported "+graph.nodes.length+" nodes, "+graph.edges.length+
        " links, "+rows.length+" metrics and a 7-formula topology explorer. "
        +"Only ER_ sheets were written; institutional model approval remains FALSE.";
    }catch(err){
      status.textContent="Graph import failed: "+String(err.message||err);
    }finally{graphButton.disabled=false;}
  });
  if(typeof Office!=="undefined"&&typeof Office.onReady==="function"){
    Office.onReady(info=>{excelHost=info.host===Office.HostType.Excel;load();});
  }else{load();}
})();
