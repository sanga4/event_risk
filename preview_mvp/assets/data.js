"use strict";
/* No arbitrary browser SQL, credential persistence or raw source-content cache. */
(function(){
const $=id=>document.getElementById(id);
const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);return e;};
const state={analyst:"",admin:"",tables:[],selected:null,offset:0,limit:25,rows:[],columns:[]};
function message(text){$("connect-status").textContent=text;}
async function call(url){
 const r=await fetch(url,{cache:"no-store",
   headers:{"X-Analyst-Key":state.analyst,"X-Data-Admin-Key":state.admin}});
 let data;try{data=await r.json();}catch(_){throw Error("Invalid server response");}
 if(!r.ok)throw Error(data.error||"HTTP "+r.status);
 return data;
}
function selectStatus(item){
 $("dataset-title").textContent=item.name;
 $("dataset-description").textContent="main."+item.name+" · "+item.columns.length+
  " visible columns · "+item.kind.replaceAll("_"," ").toLowerCase();
 $("provenance").textContent="Source category: "+item.kind;
 const schema=$("schema");schema.replaceChildren();
 for(const col of item.columns.slice(0,28)){
  const pill=node("span",col.name+" · "+col.type);schema.append(pill);
 }
 schema.hidden=false;
}
function renderTables(){
 const filter=$("table-search").value.trim().toLowerCase();
 const items=state.tables.filter(t=>t.name.toLowerCase().includes(filter));
 const container=$("dataset-list");container.replaceChildren();
 for(const item of items){
  const b=node("button"),name=node("span",item.name);
  b.type="button";b.append(name,node("small",item.kind==="SOURCE_REDISPLAY"?"SOURCE":item.kind==="FACTOR_METADATA"?"META":"RESEARCH"));
  b.setAttribute("aria-current",String(state.selected?.name===item.name));
  b.addEventListener("click",()=>loadDataset(item,0));container.append(b);
 }
 if(!items.length)container.append(node("p","No matching accessible dataset definitions."));
 $("dataset-count").textContent=items.length+" / "+state.tables.length;
}
function tableContents(data){
 const host=$("result");host.replaceChildren();
 state.rows=data.rows||[];state.columns=data.columns||[];
 if(!state.rows.length){
  host.append(node("p","This page has no records. Try the previous page or another source dataset."));
  return;
 }
 const table=node("table");table.className="research-table";
 const thead=node("thead"),theadRow=node("tr");
 for(const col of state.columns)theadRow.append(node("th",col));
 thead.append(theadRow);table.append(thead);
 const body=node("tbody");
 for(const row of state.rows){
  const tr=node("tr");
  for(const col of state.columns){
   const value=row[col],td=node("td",value===null||value===undefined?"—":value);
   td.title=String(value===null||value===undefined?"":value).slice(0,2000);
   tr.append(td);
  }
  body.append(tr);
 }
 table.append(body);host.append(table);
}
async function loadDataset(item,offset){
 if(!state.analyst||!state.admin)return message("Connect with authorized keys first.");
 state.selected=item;state.offset=offset;state.rows=[];
 renderTables();selectStatus(item);
 $("result").replaceChildren(node("p","Querying approved MotherDuck source table…"));
 $("previous").disabled=true;$("next").disabled=true;$("download").disabled=true;
 try{
  const path="/api/v1/research/table?table="+encodeURIComponent(item.name)+
    "&limit="+state.limit+"&offset="+offset;
  const data=await call(path);
  if(data.mode!=="LIVE_MOTHERDUCK_ADMIN_READ_ONLY_PAGE"||data.dataset.name!==item.name)
   throw Error("Source integrity check failed");
  tableContents(data);
  $("source-status").textContent="Live SELECT · "+data.returned+" row(s) · offset "+offset;
  $("page-caption").textContent=(offset+1)+"–"+(offset+data.returned);
  $("previous").disabled=offset===0;
  $("next").disabled=!data.has_next_page||offset+state.limit>10000;
  $("download").disabled=data.returned===0;
 }catch(error){
  $("result").replaceChildren(node("p","Dataset blocked or unavailable: "+error.message));
  $("source-status").textContent="No successful row read";
  $("page-caption").textContent="—";
 }
}
function exportCSV(){
 if(!state.rows.length||!state.selected)return;
 const quote=x=>{
  let s=String(x===null||x===undefined?"":x);
  if(/^[\s]*[=+@\-\t\r]/.test(s))s="'"+s;
  return /[,\x22\n\r]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;
 };
 const lines=[state.columns,...state.rows.map(row=>state.columns.map(k=>row[k]))];
 const blob=new Blob([lines.map(row=>row.map(quote).join(",")).join("\r\n")+"\r\n"],
  {type:"text/csv;charset=utf-8"});
 const url=URL.createObjectURL(blob),a=node("a");
 a.href=url;a.download="eventrisk-research-"+state.selected.name+"-"+state.offset+".csv";
 document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
}
async function connect(){
 state.analyst=$("analyst-key").value.trim();state.admin=$("admin-key").value.trim();
 $("analyst-key").value="";$("admin-key").value="";
 if(!state.analyst||!state.admin){message("Both separately issued access keys are required.");return;}
 message("Checking your read-only warehouse permissions…");
 try{
  const d=await call("/api/v1/research/datasets");
  if(d.mode!=="LIVE_MOTHERDUCK_CATALOG"||d.arbitrary_sql_allowed!==false)
   throw Error("Unrecognized protected database contract");
  state.tables=d.tables||[];
  $("live-state").textContent="MotherDuck · LIVE READ-ONLY";
  message("Authenticated. "+state.tables.length+" discoverable research datasets. Actual table rows require independent source permission.");
  $("table-search").disabled=false;$("refresh").disabled=false;
  renderTables();
 }catch(e){
  state.analyst="";state.admin="";state.tables=[];
  message("Connection not established: "+e.message+". Configure MotherDuck service credentials and research roles in the server first.");
  $("live-state").textContent="MotherDuck · unavailable";
 }
}
async function init(){
 $("connect").addEventListener("click",connect);
 $("table-search").addEventListener("input",renderTables);
 $("previous").addEventListener("click",()=>{if(state.selected)loadDataset(state.selected,Math.max(0,state.offset-state.limit));});
 $("next").addEventListener("click",()=>{if(state.selected)loadDataset(state.selected,state.offset+state.limit);});
 $("refresh").addEventListener("click",()=>{if(state.selected)loadDataset(state.selected,state.offset);else connect();});
 $("download").addEventListener("click",exportCSV);
 try{
  const r=await fetch("/api/v1/runtime",{cache:"no-store"}),d=await r.json();
  $("live-state").textContent=d.connection_tested?"MotherDuck · verified":"MotherDuck · setup required";
  if(!d.database_credentials_present)
   message("The EventRisk Research server needs its own MotherDuck Read Scaling service token to connect.");
 }catch(_){$("live-state").textContent="Connection status unavailable";}
}
document.addEventListener("DOMContentLoaded",init);
})();