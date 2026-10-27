"use strict";
const {chromium}=require("playwright");
const {spawn}=require("node:child_process");
const path=require("node:path");
const fs=require("node:fs");
const assert=require("node:assert/strict");
const ROOT=path.resolve(__dirname,".."),PORT="18742";
const URL="http://127.0.0.1:"+PORT;
const env={...process.env,HOST:"127.0.0.1",PORT};
for(const k of ["MOTHERDUCK_TOKEN","PREVIEW_MVP_ANALYST_KEY","EVENTRISK_ANALYST_KEY",
 "EVENTRISK_SOURCE_REDISPLAY_APPROVED","PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED",
 "EVENTRISK_DERIVED_RESEARCH_APPROVED","PREVIEW_MVP_DERIVED_RESEARCH_APPROVED"])delete env[k];
let server,browser;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function ready(){
 for(let i=0;i<70;i++){
  if(server.exitCode!==null)throw Error("Server exited "+server.exitCode);
  try{if((await fetch(URL+"/health/live")).ok)return;}catch(_){}
  await sleep(200);
 }
 throw Error("Research API server did not become ready");
}
async function viewer(width,height,dir){
 const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
 const errors=[],writes=[];
 page.on("pageerror",e=>errors.push(e.message));
 page.on("request",r=>{if(r.url().includes("/api/v1")&&r.method()!=="GET")writes.push(r.url())});
 const r=await page.goto(URL+"/",{waitUntil:"domcontentloaded",timeout:30000});
 assert.equal(r.status(),200);
 await page.locator("#list li[data-id]").first().waitFor({timeout:12000});
 assert.equal(await page.locator("h1").innerText(),"Event Risk Graph");
 assert.equal(await page.locator("#detail").count(),1);
 assert.equal(await page.locator("#graph").count(),1);
 assert.equal(await page.locator('main .split').count(),2);
 assert.equal(await page.locator('a[href="/api"]').count(),1);
 assert.equal(await page.locator('.tabs [data-tab="contracts"]').count(),1);
 assert.equal(await page.locator('.tabs [data-tab="events"]').count(),1);
 await page.locator('.tabs [data-tab="contracts"]').click();
 await page.locator('[data-id="contract:illustrative:data_center_power"]').waitFor();
 await page.locator('[data-id="contract:illustrative:data_center_power"]').click();
 assert.ok((await page.locator("#detail").textContent()).includes("NOT_AN_ACTUAL_LISTING"));
 assert.ok((await page.locator("#path-notice").textContent()).includes("NOT an actual exchange listing"));

 assert.equal(await page.locator('a[href="/excel/manifest.xml"]').count(),1);
 assert.ok(!(await page.locator("body").innerText()).includes("Event Attribution"));
 assert.ok((await page.locator("#live-status").textContent()).length>5);
 if(width<900)assert.equal(await page.locator("#detail").isVisible(),true);
  if(width>=900){
  await page.waitForFunction(()=>document.querySelector("#graph svg g[role='button']")!==null,null,{timeout:15000});
   assert.ok((await page.locator("#graph svg g[role='button']").count())>=5);
  // Initial selection is asynchronous; verify concrete security details after the explicit click.
 }
 await page.locator('.tabs [data-tab="securities"]').click();
 await page.locator("#search").fill("TSM");
 await page.locator('[data-id="security:TSM"]').waitFor();
 await page.locator('[data-id="security:TSM"]').click();
 assert.ok((await page.locator("#detail").innerText()).includes("TSM"));
 assert.ok((await page.locator("#detail").innerText()).includes("Source"));
 await page.locator('.tabs [data-tab="factors"]').click();
 await page.locator("#search").fill("10Y");
 assert.ok((await page.locator("#list li[data-id]").count())>0);
 assert.equal(await page.locator('.tabs [data-tab="markets"]').count(),1);
 await page.locator('.tabs [data-tab="markets"]').click();
 assert.ok((await page.locator("#live-status").textContent()).includes("private warehouse"));
 assert.equal(await page.locator("#market-venue").count(),1);
  assert.equal(await page.locator("#market-next").count(),1);
  assert.equal(await page.locator("#owner-key").count(),1);
 await page.locator('.tabs [data-tab="questions"]').click();
 assert.ok((await page.locator("#list-info").innerText()).includes("require MotherDuck"));
 await page.locator("aside details summary").click();
 await page.locator("#analyst-key").fill("not-a-real-analyst-key");
 await page.locator("#connect").click();
 await page.getByText("Live MotherDuck unavailable",{exact:false}).waitFor({timeout:9000});
 await page.screenshot({path:path.join(dir,"marco-raw-graph-"+width+".png"),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 await page.close();console.log("MARCO_RAW_SOURCE_GRAPH_BROWSER=PASS",width,height);
}
async function documents(dir){
 const page=await browser.newPage({viewport:{width:1360,height:850}});
 const errors=[];page.on("pageerror",e=>errors.push(e.message));
 const response=await page.goto(URL+"/lab",{waitUntil:"domcontentloaded"});
 assert.equal(response.status(),200);
 await page.locator("#case-title").waitFor({timeout:12000});
 assert.equal(await page.locator("#factor-chart").count(),1,"Historical factor chart must be present and access-gated");
 assert.equal(await page.locator("#run-regression").count(),1);
 assert.equal(await page.locator("#load-series").count(),1);
 assert.ok((await page.locator("#warehouse-connection").textContent()).length>2);
 await page.goto(URL+"/api",{waitUntil:"domcontentloaded"});
 assert.ok((await page.locator("h2").innerText()).includes("EventRisk API"));
 assert.ok((await page.locator('a[href="/excel/manifest.xml"]').count())>0);
 await page.goto(URL+"/data",{waitUntil:"domcontentloaded"});
 assert.equal(await page.locator("#table-search").isEnabled(),false);
 await page.screenshot({path:path.join(dir,"source-connection-gated.png")});
 assert.deepEqual(errors,[]);
 await page.close();
 console.log("API_EXCEL_DOCS_AND_WAREHOUSE_GATE_BROWSER=PASS");
}
async function main(){
 const dir=path.join(ROOT,"artifacts");fs.mkdirSync(dir,{recursive:true});
 server=spawn("python",["app.py"],{cwd:ROOT,env,stdio:["ignore","pipe","pipe"]});
 try{
  await ready();
  browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
  await viewer(1440,900,dir);
  await viewer(390,844,dir);
  await documents(dir);
  console.log("EVENTRISK_RAW_MARCO_GRAPH_AND_API_EXCEL_CHROMIUM=PASS");
 }finally{
  if(browser)await browser.close();
  if(server&&!server.killed){server.kill("SIGTERM");await sleep(200)}
 }
}
main().catch(e=>{console.error("CHROMIUM_E2E_FAIL",e.stack||e);process.exitCode=1});
