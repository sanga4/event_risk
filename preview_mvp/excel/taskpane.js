"use strict";
(function(){
  const $=id=>document.getElementById(id);
  let inExcel=false,catalog=null,graph=null,inventory=null;
  const status=message=>$("status").textContent=message;
  function safeCell(x){
    if(x===null||x===undefined)return "";
    if(typeof x==="boolean"||typeof x==="number")return x;
    const v=String(x);
    return /^[\s]*[=+\-@\t\r]/.test(v)?"'"+v:v;
  }
  function rectangular(rows){
    const size=Math.max(0,...rows.map(r=>r.length));
    return rows.map(r=>[...r,...new Array(Math.max(0,size-r.length)).fill("")].map(safeCell));
  }
  async function api(path,priv=false){
    const headers=priv?{"X-Analyst-Key":$("key").value.trim()}:{};
    if(priv&&$("owner-key").value.trim())headers["X-Data-Admin-Key"]=$("owner-key").value.trim();
    const r=await fetch(path,{headers,cache:"no-store"});
    let d;try{d=await r.json();}catch(_){throw Error("Invalid backend source response");}
    if(!r.ok)throw Error(d.error||"HTTP "+r.status);
    return d;
  }
  async function writeSheet(context,name,rows){
    if(!/^[A-Za-z_0-9]{1,29}$/.test(name))throw Error("Illegal sheet name");
    if(rows.length<1||rows.length>10000||rows[0].length>20)throw Error("Unexpected source size");
    let sheet=context.workbook.worksheets.getItemOrNullObject(name);
    sheet.load("isNullObject");await context.sync();
    if(sheet.isNullObject)sheet=context.workbook.worksheets.add(name);
    else{
      const used=sheet.getUsedRangeOrNullObject();
      used.load("isNullObject");await context.sync();
      if(!used.isNullObject)used.clear(Excel.ClearApplyTo.all);
    }
    const cells=rectangular(rows);
    const target=sheet.getRangeByIndexes(0,0,cells.length,cells[0].length);
    target.values=cells;
    sheet.getRangeByIndexes(0,0,1,cells[0].length).format.fill.color="#153b40";
    sheet.getRangeByIndexes(0,0,1,cells[0].length).format.font.color="#ffffff";
    sheet.getRangeByIndexes(0,0,1,cells[0].length).format.font.bold=true;
    target.format.columnWidth=135;
    sheet.getRange("A:A").format.columnWidth=190;
    return sheet;
  }
  async function importReference(){
    if(!inExcel)return;
    status("Inserting source published catalogs; no source prices.");
    try{
      await Excel.run(async c=>{
        await writeSheet(c,"ER_Securities",[
          ["Ticker","Issuer / instrument","Country","Asset class","Sector","Provenance"],
          ...catalog.securities.map(s=>[s.ticker,s.name,s.country,s.asset_class,s.sector,"Repo public reference — NOT portfolio holdings"])
        ]);
        await writeSheet(c,"ER_Factors",[
          ["Factor ID","Name","Family","Definition","Historical series validated"],
          ...catalog.factors.map(f=>[f.factor_id,f.name,f.family,f.definition,false])
        ]);
        await writeSheet(c,"ER_Channels",[
          ["Channel ID","Economic transmission hypothesis","Linked factor families","Review status"],
          ...catalog.channels.map(ch=>[ch.id,ch.name,ch.related_factor_families.join(", "),ch.review_status])
        ]);
        await writeSheet(c,"ER_Inventory",[
          ["Warehouse measure","Last verified value","Evidence date","Data status"],
          ...Object.entries(inventory.counts).map(([k,v])=>[
             k,v,inventory.evidence_checked_date_utc,inventory.refresh_mode
          ])
        ]);
        await c.sync();
      });
      status("Imported source definitions, economic channels and dated inventory. 108 defined factors do NOT mean 108 observed historical series.");
    }catch(e){status("Excel reference import failed: "+e.message);}
  }
  async function importGraph(){
    if(!inExcel)return;
    status("Inserting qualitative source prior relationships and formulas...");
    const entityMap=new Map(graph.nodes.filter(n=>n.type==="entity").map(n=>[n.id,n]));
    const priors=graph.edges.filter(e=>e.type==="research_exposure_prior");
    const scenarios=graph.edges.filter(e=>e.type==="hypothetical_transmission");
    if(graph.mode!=="PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE"||
       graph.edges.some(e=>e.review_status!=="RESEARCH_ONLY_NOT_APPROVED"))
       return status("Graph source-review conditions failed; import refused.");
    try{
      await Excel.run(async c=>{
        await writeSheet(c,"ER_Priors",[
          ["Entity ID","Security ID","Entity name","Analyst prior","Original source rationale","Review state"],
          ...priors.map(e=>[e.src,e.dst,entityMap.get(e.src)?.name||e.src,
             e.weight,e.summary||"","Not a measured financial beta"])
        ]);
        await writeSheet(c,"ER_Pathways",[
          ["Event ID","Economic channel ID","Relationship","Status"],
          ...scenarios.map(e=>[e.src,e.dst,e.type,e.review_status])
        ]);
        const sh=await writeSheet(c,"ER_Explorer",[
          ["EVENTRISK GRAPH PATH EXPLORER","Value","What it means"],
          ["Event ID","event:taiwan","Illustrative; not a source-recorded announcement"],
          ["Entity ID","entity:Q865","Original public seed entity"],
          ["Security ID","security:TSM","Source security reference"],
          ["Channel ID","channel:supply","Economic transmission hypothesis"],
          ["Event to channel connected","","Not causal"],
          ["Entity to security connected","","Not portfolio beta"],
          ["Entity to security prior","","Qualitative 0–1 relevance prior"],
          ["READINESS","RESEARCH ONLY","Original PIT and institutional beta unapproved"]
        ]);
        const pLast=priors.length+1,chLast=scenarios.length+1;
        sh.getRange("B6").formulas=[[
          '=IF(COUNTIFS(ER_Pathways!A2:A'+chLast+',B2,ER_Pathways!B2:B'+chLast+',B5)>0,"CONNECTED","NO PATH")'
        ]];
        sh.getRange("B7").formulas=[[
          '=IF(COUNTIFS(ER_Priors!A2:A'+pLast+',B3,ER_Priors!B2:B'+pLast+',B4)>0,"CONNECTED","NO PATH")'
        ]];
        sh.getRange("B8").formulas=[[
          '=SUMIFS(ER_Priors!D2:D'+pLast+',ER_Priors!A2:A'+pLast+',B3,ER_Priors!B2:B'+pLast+',B4)'
        ]];
        sh.getRange("B2:B5").format.fill="#fff3d3";
        sh.getRange("B8").numberFormat=[["0.00"]];
        await c.sync();
      });
      status("Source prior graph + 3 working Excel formulas imported. No approved return or event-impact beta represented.");
    }catch(e){status("Excel graph import failed: "+e.message);}
  }
  async function importModels(){
    if(!inExcel)return;
    const ticker=$("ticker").value.trim().toUpperCase();
    if(!/^[A-Z0-9.=_-]{1,25}$/.test(ticker))return status("Invalid ticker.");
    status("Requesting authorized original 48-security funding regression family for "+ticker+"...");
    try{
      const result=await api("/api/v1/research/funding-diagnostics?ticker="+encodeURIComponent(ticker),true);
      if(result.approved_event_impact!==false)throw Error("Research model status unexpected");
      if(!(result.fits||[]).length)return status("No original source-fitted regression for "+ticker+".");
      await Excel.run(async c=>{
        await writeSheet(c,"ER_Regressions",[
          ["Ticker","Variant","SPY beta","2Y yield beta","10Y yield beta","Funding beta","Funding CI low",
           "Funding CI high","HAC SE","Holm adj p","Holm pass","Heldout skill","Start","End","Build ID","Approval"],
          ...result.fits.map(m=>[ticker,m.variant,m.market_spy_beta,m.dgs2_yield_change_beta,
            m.dgs10_yield_change_beta,m.funding_basis_beta,m.funding_ci95_low,
            m.funding_ci95_high,m.funding_hac_nw5_se,m.familywise?.holm_familywise_p,
            !!m.familywise?.holm_p_below_05,m.incremental_heldout_skill,m.first_day,
            m.last_day,m.build_id,m.institutional_beta_released?"Approved":"RESEARCH ONLY"])
        ]);
        await c.sync();
      });
      status("Inserted real source-fit coefficients and independent Holm evidence for "+ticker+
        ". These are NONCAUSAL historical associations, never identified event effects.");
    }catch(e){status("Regression source access denied/unavailable: "+e.message+
      ". Check independent entitlement, scoped read-only MotherDuck token and analyst key.");}
  }
  async function importSeries(){
    if(!inExcel)return;
    const id=$("factor").value;
    status("Reading allowed source observations for "+id+"...");
    try{
      const result=await api("/api/v1/research/factor-series?factor_id="+encodeURIComponent(id)+"&limit=250",true);
      if(result.no_first_publication_claim!==true)throw Error("Original vintage claim not source verified");
      await Excel.run(async c=>{
        await writeSheet(c,"ER_FactorHistory",[
          ["Source observed date","Observed value","Unit","Warehouse available at","Availability basis","Factor ID","Original publisher PIT"],
          ...(result.rows||[]).map(p=>[p.observed_date,p.value,p.unit,p.available_at,
            p.availability_basis,id,"NOT VERIFIED"])
        ]);
        await c.sync();
      });
      status("Inserted "+(result.rows||[]).length+" dated source observations for "+id+
        ". No original publisher first-release timing or event surprise inferred.");
    }catch(e){status("Factor source access denied/unavailable: "+e.message);}
  }
  async function importExtended(){
    if(!inExcel)return;
    status("Loading proposed (unmeasured) factor definitions and a clearly artificial five-stage path...");
    try{
      const [factors,paths]=await Promise.all([
        api("/api/v1/factor-proposals"),api("/api/v1/graph-paths")]);
      if(factors.mode!=="PROPOSED_UNMEASURED_FACTOR_TAXONOMY"||
         factors.validated_series_count!==0||
         paths.mode!=="PUBLIC_REFERENCE_PLUS_EXPLICIT_SYNTHETIC_PATH_EXAMPLE"||
         paths.contract_count_verified!==0)
        throw Error("Unexpected contract or factor validation claim");
      const syntheticNodes=paths.nodes.filter(n=>
        n.type==="contract"||n.id==="event:data_center_demand"||
        n.id==="entity:theme:data_center_infrastructure"||
        n.id.startsWith("factor:PROPOSED."));
      const demoIds=new Set(syntheticNodes.map(n=>n.id));
      const securityIds=new Set(paths.edges.filter(e=>
        e.type==="proposed_thematic_relevance").map(e=>e.dst));
      for(const n of paths.nodes)if(securityIds.has(n.id))demoIds.add(n.id);
      await Excel.run(async c=>{
        await writeSheet(c,"ER_ProposedFactors",[
          ["Factor ID","Definition","Family","Observed series validated","Original PIT verified","Market rights verified","Release status"],
          ...factors.factors.map(p=>[p.factor_id,p.name,p.family,
            p.validated_observation_series,p.original_publication_pit_verified,
            p.market_data_rights_verified,p.release_status])
        ]);
        await writeSheet(c,"ER_FiveStageNodes",[
          ["Node ID","Node type","Name","Source / review status","Exchange verified"],
          ...paths.nodes.filter(n=>demoIds.has(n.id)).map(n=>[
             n.id,n.type,n.name,n.review_status||"",false])
        ]);
        await writeSheet(c,"ER_FiveStageEdges",[
          ["Source node","Target node","Relationship","Review state","Causal coefficient estimated"],
          ...paths.edges.filter(e=>demoIds.has(e.src)&&demoIds.has(e.dst)&&
            e.source_kind==="EXPLICIT_ILLUSTRATIVE_HYPOTHESIS").map(e=>[
              e.src,e.dst,e.type,e.review_status,false])
        ]);
        await c.sync();
      });
      status("Inserted "+factors.count+" unmeasured proposed factors and synthetic contract pathway. "+
        "No actual Kalshi/Polymarket contract, verified series, or security return beta was claimed.");
    }catch(e){status("Extended factor/pathway import failed: "+e.message);}
  }
  async function importMarkets(){
    if(!inExcel)return;
    status("Retrieving licensed captured market values from MotherDuck via EventRisk API...");
    try{
      if(!$("key").value.trim())throw Error("Issued analyst key is required");
      const venue=$("venue").value;
      if(!["kalshi","polymarket"].includes(venue))throw Error("Invalid venue");
      const d=await api("/api/v1/research/markets?venue="+venue+"&limit=50",true);
      if(d.mode!=="LICENSE_GATED_CAPTURED_MARKET_QUOTES"||d.venue!==venue)
        throw Error("Unexpected market-data source contract");
      await Excel.run(async c=>{
        await writeSheet(c,"ER_MarketValues",[
          ["Venue","Native contract ID","Event ID","Event title","Market question",
           "YES market-implied %","Previous capture %","Change (percentage points)",
           "Quote basis","Warehouse known at","Provider observed at",
           "Captured timestamp verified","Quote freshness verified","Original PIT released"],
          ...d.rows.map(m=>[
           m.venue,m.market_id,m.event_id,m.event_title,m.question,
           typeof m.probability==="number"?m.probability*100:"",
           typeof m.previous_probability==="number"?m.previous_probability*100:"",
           m.probability_delta_pp,m.quote_basis,m.known_at,m.observed_at,
           m.capture_time_verified,m.provider_quote_freshness_verified,
           m.historical_point_in_time_released])
        ]);
        await c.sync();
      });
      status("Imported "+d.rows.length+" source-permitted market quotes. Captured quotes are not current executable prices, calibrated probabilities of the normalized event, or verified original PIT.");
    }catch(e){status("Market odds import unavailable: "+e.message+
      ". Requires a valid analyst key and independent source redisplay authorization.");}
  }
  async function importMarketHistory(){
    if(!inExcel)return;
    status("Loading captured contract probability history...");
    try{
      if(!$("key").value.trim())throw Error("Issued analyst key is required");
      const venue=$("venue").value,marketId=$("market-id").value.trim();
      if(!/^[A-Za-z0-9._:-]{1,180}$/.test(marketId))throw Error("Enter a valid native market ID");
      const d=await api("/api/v1/research/market-history?venue="+
        encodeURIComponent(venue)+"&market_id="+encodeURIComponent(marketId)+"&limit=180",true);
      if(d.mode!=="LICENSE_GATED_CAPTURED_MARKET_HISTORY"||
         d.market_id!==marketId||d.venue!==venue)
        throw Error("Unexpected historical source contract");
      await Excel.run(async c=>{
        await writeSheet(c,"ER_MarketHistory",[
          ["Venue","Native contract ID","Observation date","Captured YES %","Change pp",
           "Previous observed date","Last quote captured at","Snapshot count",
           "Snapshot source","Observation provenance","Original PIT verified"],
          ...d.rows.map(m=>[venue,marketId,m.observed_date,
            typeof m.probability==="number"?100*m.probability:"",
            m.probability_delta_pp,m.previous_observed_date,m.last_quote_at,
            m.snapshot_count,m.snapshot_source,m.observation_provenance,
            m.point_in_time_verified])
        ]);
        await c.sync();
      });
      status("Imported "+d.rows.length+" captured daily values; this is not a certified originally published PIT history.");
    }catch(e){status("Probability history unavailable: "+e.message+
      ". Separate analyst authorization and source data-use rights are required.");}
  }
  async function init(){
    try{
      const [c,g,i]=await Promise.all([
        api("/api/v1/catalog"),api("/api/v1/graph"),api("/api/v1/inventory")]);
      if(c.factors_count!==108||c.securities_count<500||g.mode!=="PUBLIC_CATALOG_PLUS_HYPOTHETICAL_TRANSMISSION_NOT_LIVE"||
         i.refresh_mode!=="DATED_READ_ONLY_AGGREGATE_AUDIT_NOT_LIVE_DATABASE_CONNECTION")
          throw Error("Unapproved reference/graph metadata state");
      catalog=c;graph=g;inventory=i;
      $("public-status").textContent=c.securities_count+" securities, "+c.factors_count+" factor definitions, "+
        c.channels.length+" economic channels. Dated warehouse audit "+i.evidence_checked_date_utc+".";
    }catch(e){status("Reference catalog not available: "+e.message);return;}
    if(typeof Office==="undefined"){
      status("Open using Microsoft Excel's installed EventRisk Research add-in. This browser page is read-only.");
      return;
    }
    Office.onReady(info=>{
      if(info.host!==Office.HostType.Excel){status("This taskpane must run inside Microsoft Excel.");return;}
      inExcel=true;
      for(const id of ["reference","graph","extended","regression","series","market-values","market-history"])$(id).disabled=false;
      status("Connected to Microsoft Excel. Public catalogs are ready; real warehouse regressions and factor data require separate analyst/source authorization.");
    });
  }
  document.addEventListener("DOMContentLoaded",()=>{
    $("reference").addEventListener("click",importReference);
    $("graph").addEventListener("click",importGraph);
    $("extended").addEventListener("click",importExtended);
    $("market-values").addEventListener("click",importMarkets);
    $("market-history").addEventListener("click",importMarketHistory);
    $("regression").addEventListener("click",importModels);
    $("series").addEventListener("click",importSeries);
    init();
  });
})();