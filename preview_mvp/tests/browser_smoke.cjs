"use strict";
/* Actual Chromium smoke of Marco-style Preview MVP and private manual holdings.
   CI only: starts an isolated loopback-only source-catalog server, never connects
   to a research warehouse or submits analyst holdings to HTTP endpoints. */
const {chromium}=require("playwright");
const {spawn}=require("node:child_process");
const path=require("node:path");
const fs=require("node:fs");
const assert=require("node:assert/strict");
const root=path.resolve(__dirname,"..");
const PORT="18742",URL="http://127.0.0.1:"+PORT;
const env={...process.env,HOST:"127.0.0.1",PORT,
  PREVIEW_MVP_SOURCE_REDISPLAY_APPROVED:"false",
  PREVIEW_MVP_DERIVED_RESEARCH_APPROVED:"false"};
delete env.MOTHERDUCK_TOKEN;
delete env.PREVIEW_MVP_ANALYST_KEY;
let proc,browser;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function ready(){
  for(let n=0;n<75;n++){
    if(proc.exitCode!==null)throw Error("Preview MVP process exited "+proc.exitCode);
    try{const r=await fetch(URL+"/health/live");if(r.ok)return;}catch(_){}
    await sleep(190);
  }
  throw Error("Loopback preview server did not become ready");
}
async function assertBrowser(width,height,dir){
  const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
  const errors=[],mutations=[];
  page.on("pageerror",e=>errors.push(e.message));
  page.on("request",r=>{
    if(r.url().includes("/api/v1/")&&r.method()!=="GET")mutations.push(r.method()+" "+r.url());
    if(r.url().includes("/api/v1/")&&
       (r.url().toLowerCase().includes("positions")||r.url().toLowerCase().includes("holdings")))
      mutations.push("Holdings leaked into an HTTP request URL");
  });
  const response=await page.goto(URL+"/",{waitUntil:"domcontentloaded",timeout:30000});
  assert.equal(response.status(),200);
  await page.waitForFunction(()=>{
    const el=document.getElementById("source-status");
    return el&&el.textContent.includes("543 securities");
  },{timeout:15000});
  assert.equal(await page.locator("#event-choice option").count(),8);
  assert.ok((await page.locator("#source-status").innerText()).includes("108 factors"));
  assert.equal(await page.locator('main .split').count(),2);
  // The original vis-network should produce graph canvas elements on the desktop
  // viewport when its exact original pinned script loads.
  if(width>=1000){
    await page.waitForFunction(()=>document.querySelector("#graph canvas")!==null,
      {timeout:20000});
    assert.equal(await page.locator("#empty").isVisible(),false);
    assert.ok((await page.locator("#detail").innerText()).includes("Related securities"));
    assert.ok((await page.locator("#detail").innerText()).includes("Related financial factor definitions"));
    const initialCount=Number((await page.locator("#caption").innerText()).match(/^\\d+/)[0]);
    await page.getByRole("button",{name:"Show securities & factors in graph (depth 2)"}).click();
    await page.waitForTimeout(250);
    const expandedCount=Number((await page.locator("#caption").innerText()).match(/^\\d+/)[0]);
    assert.ok(expandedCount>initialCount,
      "Original Marco graph must offer real company/factor two-hop exploration");
    await page.screenshot({path:path.join(dir,"marco-expanded-"+width+".png")});
    await page.locator("#depth").selectOption("1");
  }
  if(width<=650){
    const graphRect=await page.locator("#graph").boundingBox();
    assert.ok(graphRect&&graphRect.width>=width-15,
      "Mobile graph must occupy full viewport width, not a narrow right sliver");
    assert.equal(await page.locator("#browse-mobile").isVisible(),true);
    assert.equal(await page.locator("main aside").isVisible(),false);
    await page.locator("#browse-mobile").click();
    assert.equal(await page.locator("main aside").isVisible(),true);
    await page.locator('main aside [data-id="event:trade"]').click();
    assert.equal(await page.locator("main aside").isVisible(),false);
    assert.equal(await page.locator("#detail").isVisible(),true);
    assert.ok((await page.locator("#detail").innerText()).includes("Trade restrictions"));
    await page.locator(".mobile-detail-dismiss").click();
    assert.ok(!(await page.locator("body").getAttribute("class")).includes("mobile-detail-open"));
    await page.waitForTimeout(280);
  }
  await page.screenshot({path:path.join(dir,"marco-"+width+".png")});
  await page.locator('nav [data-view="attribution"]').click();
  await page.locator("#load-demo").click();
  assert.equal(await page.locator("#holdings-body tr").count(),4);
  const score=await page.locator("#relevance-score").innerText();
  assert.match(score,/^\d[\d.,]*\s*\/\s*100$/);
  const coverage=await page.locator("#coverage-score").innerText();
  assert.match(coverage,/^\d[\d.,]*%$/);
  const pnl=await page.locator("#pnl-score").innerText();
  assert.match(pnl,/\-\$2,100\.00/,"short FXI cash exposure sign handling in user what-if");
  assert.ok((await page.locator("#attribution-results").innerText()).includes("TSM"));
  await page.screenshot({path:path.join(dir,"attribution-"+width+".png")});
  await page.locator("#event-choice").selectOption("event:funding");
  await page.locator("#holdings-body .ticker-input").first().fill("JPM");
  const watch=await page.locator("#watchlist-score").innerText();
  assert.match(watch,/[1-9]\d*\/4 holdings/,
    "Funding rule should flag a source-defined Financials security without creating beta");
  const table=await page.locator("#attribution-results").innerText();
  assert.ok(table.includes("funding"),"Source-screening tag must be displayed");
  assert.ok(table.includes("Not mapped"),"Don't call watchlist flags proven exposure");
  const noBetas=(await page.locator("#relevance-score").innerText());
  assert.ok(!/NaN|Infinity/.test(noBetas));
  await page.locator("#holdings-body .money-input").first().fill("0");
  assert.ok((await page.locator("#attribution-results").innerText()).includes("nonzero"));
  await page.locator("#holdings-body .money-input").first().fill("25000");
  assert.ok(!(await page.locator("#attribution-results").innerText()).includes("enter a finite nonzero"));
  await page.locator("#export-attribution").click();
  // Export creates local Blob, no upload requests.
  await page.locator("#clear-holdings").click();
  assert.equal(await page.locator("#holdings-body tr").count(),1);
  assert.equal(await page.locator("#relevance-score").innerText(),"—");
  await page.locator('nav [data-view="explore"]').click();
  assert.equal(await page.locator("#graph").count(),1);
  assert.deepEqual(mutations,[]);
  assert.deepEqual(errors,[]);
  await page.close();
  console.log("MARCO_REAL_BROWSER_ATTRIBUTION=PASS",width+"x"+height);
}
async function main(){
  const out=path.join(root,"artifacts");
  fs.mkdirSync(out,{recursive:true});
  proc=spawn("python",["app.py"],{cwd:root,env,stdio:["ignore","pipe","pipe"]});
  let stderr="";
  proc.stderr.on("data",b=>stderr+=b.toString().slice(0,4000));
  try{
    await ready();
    browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
    await assertBrowser(1440,900,out);
    await assertBrowser(390,844,out);
    console.log("PREVIEW_MVP_CHROMIUM_E2E=PASS",
      "Original Marco graph / desktop/mobile / 8 scenarios / manual user holdings / qualitative screening / CSV");
  }finally{
    if(browser)await browser.close();
    if(proc&&!proc.killed){proc.kill("SIGTERM");await sleep(250);}
    if(stderr&&process.exitCode)console.error(stderr.slice(-3000));
  }
}
main().catch(e=>{console.error("CHROMIUM_E2E_FAIL",e.stack||e);process.exitCode=1;});
