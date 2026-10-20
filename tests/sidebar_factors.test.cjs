'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname,'../excel/taskpane.html'),'utf8');
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
if (!script) throw new Error('Missing Excel pane controller');

class Element {
  constructor(tag='div') {this.tagName=tag;this.children=[];this.listeners={};this._text='';this.value='';this.className='';this.hidden=false;}
  set textContent(v) {this._text=String(v);this.children=[];}
  get textContent() {return this._text+this.children.map(n=>n.textContent).join('');}
  replaceChildren(...items) {this._text='';this.children=[...items];}
  appendChild(child) {this.children.push(child);return child;}
  addEventListener(type,fn) {this.listeners[type]=fn;}
  click() {return this.listeners.click?.();}
}
const factor = (id,name,family='country') => ({factor_id:id,factor:{id,name,family,model:'Test-defined factor'},
  status:'mapped',link_type:'direct_or_structural',mechanism:'country_risk',
  reason:'Explicitly linked to an affected country',evidence:'linked entity: Taiwan',
  rule_id:'COUNTRY_EQUITY_V1',rule_version:'2026-10-20.1'});
const mapping = (status='mapped')=>({
  catalog_version:'2026-10-20.1',rule_version:'2026-10-20.1',
  factors:status==='mapped'?[factor('EQUITY.COUNTRY.TW','Taiwan equity')]:[],
  review_candidates:[{...factor('FF5.US.HML','Value (HML)','equity_style'),
    status:'review_required',reason:'Relative return spread not established by invasion'}]
});
async function tick(){for(let i=0;i<5;i++) await new Promise(resolve=>setImmediate(resolve));}
function harness(overrides={}) {
  const names=['theme','themeSearch','themeCount','themeResults',
    'questionQuery','questionSearch','eventResults','eventCount','selectionNote',
    'factorSource','factorVersion','factorReview','factorReviewCount','factorReviewResults','factorResults',
    'status','refresh','key','saveKey','keyMsg','health'];
  const el=Object.fromEntries(names.map(id=>[id,new Element()]));
  const calls=[],writes=[];
  const request=async(pathname,params)=>{
    calls.push({pathname,params});
    if(overrides[pathname])return overrides[pathname](pathname,params);
    if(pathname==='/health')return {status:'ok',last_successful_run:'2026-10-20'};
    if(pathname==='/entities')return [];
    if(pathname==='/questions')return {questions:[{id:'q:taiwan',name:'Will China invade Taiwan?',prob:.4,n_rungs:1,status:'live'}]};
    if(pathname==='/questions/q%3Ataiwan')return {id:'q:taiwan',name:'Will China invade Taiwan?',
      rungs:[{id:'prop:taiwan',name:'Taiwan invasion by 2027',prob:.4,status:'live'}]};
    if(pathname==='/questions/q%3Ataiwan/factors')return mapping();
    if(pathname==='/propositions/prop%3Ataiwan/factors')return mapping('review_only');
    throw new Error('Unexpected API route '+pathname);
  };
  const cell={getResizedRange:()=>({getCell:()=>({
    set values(v){writes.push(['values',v]);},
    set formulasR1C1(v){writes.push(['formula',v]);},
    set numberFormat(v){writes.push(['format',v]);}
  })}),getOffsetRange:()=>({select(){}})};
  const ctx={
    document:{getElementById:id=>el[id],createElement:tag=>new Element(tag)},
    EventRisk:{request,clearCache(){}},
    Office:{onReady:fn=>fn()},
    Excel:{CalculationType:{full:'full'},run:fn=>fn({workbook:{
      getActiveCell:()=>cell,application:{calculate(){}}},sync:async()=>{}})},
    localStorage:{getItem:()=>'',setItem(){},removeItem(){}},
    Promise,Map,Math,Date,Number,String,Error,encodeURIComponent,
    console
  };
  ctx.globalThis=ctx;
  vm.runInNewContext(script,ctx,{filename:'excel/taskpane.html'});
  return {el,calls,writes};
}

test('Excel pane contains Factors below Events and before Refresh',()=>{
  const e=html.indexOf('<h3>Events'),f=html.indexOf('<h2>Factors'),r=html.indexOf('<h2>Refresh');
  assert.ok(e>=0 && f>e && r>f);
  for(const id of ['factorSource','factorResults','factorReview','factorReviewResults',
    'factorReviewCount','factorVersion']) assert.ok(html.includes('id="'+id+'"'),id);
  assert.doesNotMatch(html,/portfolio.?scan|scan.?portfolio|EVENTRISK\.SCAN/i);
});

test('clicking a question displays mapped factors with version and explicit trace',async()=>{
  const {el,calls}=harness();
  el.theme.value='Taiwan';
  await el.themeSearch.click();
  const btn=el.themeResults.children[0].children[0];
  await btn.click();await tick();
  assert.ok(calls.some(c=>c.pathname==='/questions/q%3Ataiwan/factors'));
  assert.match(el.factorResults.textContent,/Taiwan equity/);
  assert.match(el.factorResults.textContent,/Explicitly linked/);
  assert.match(el.factorVersion.textContent,/Catalog 2026-10-20.1/);
  assert.match(el.factorSource.textContent,/Will China invade Taiwan/);
});

test('review candidates are separate and not treated as accepted factors',async()=>{
  const {el}=harness();
  el.theme.value='Taiwan';
  await el.themeSearch.click();
  await el.themeResults.children[0].children[0].click();await tick();
  assert.doesNotMatch(el.factorResults.textContent,/Value \(HML\)/);
  assert.match(el.factorReviewResults.textContent,/Value \(HML\)/);
  assert.equal(el.factorReview.hidden,false);
  assert.equal(el.factorReviewCount.textContent,'(1)');
});

test('clicking a review candidate shows reasons and rule, never beta or coefficient',async()=>{
  const {el}=harness();
  el.theme.value='Taiwan';
  await el.themeSearch.click();
  await el.themeResults.children[0].children[0].click();await tick();
  el.factorReviewResults.children[0].children[0].click();await tick();
  assert.match(el.status.textContent,/Relative return spread not established/);
  assert.match(el.status.textContent,/COUNTRY_EQUITY_V1/);
  assert.doesNotMatch(el.factorResults.textContent,/beta|coefficient|return forecast/i);
});

test('event selection loads proposition-inherited factors without changing ER formulas',async()=>{
  const {el,writes,calls}=harness();
  el.theme.value='Taiwan';
  await el.themeSearch.click();
  await el.themeResults.children[0].children[0].click();await tick();
  const event=el.eventResults.children.find(x=>x.textContent.includes('Taiwan invasion'));
  await event.children[0].click();await tick();
  assert.ok(calls.some(c=>c.pathname==='/propositions/prop%3Ataiwan/factors'));
  assert.match(el.factorResults.textContent,/No established factor links/);
  assert.match(el.factorReviewResults.textContent,/Value \(HML\)/);
  assert.deepEqual(writes.filter(x=>x[0]==='formula').map(x=>x[1][0][0]),
    ['=ER.EVENT(RC[-1],"title")','=ER.PROB(RC[-2])','=ER.UPDATED(RC[-3])']);
});

test('stale factor responses cannot replace a newer selected question',async()=>{
  let finish;
  const slow=new Promise(resolve=>{finish=resolve;});
  const {el}=harness({'/questions/q%3Ataiwan/factors':()=>slow});
  el.theme.value='Taiwan';
  await el.themeSearch.click();
  // Launch old request, then reset by starting a new direct question search.
  void el.themeResults.children[0].children[0].click();
  await tick();
  el.questionQuery.value='oil';
  await el.questionSearch.click();await tick();
  finish(mapping());
  await tick();
  assert.doesNotMatch(el.factorResults.textContent,/Taiwan equity/);
  assert.match(el.factorResults.textContent,/Select an event/);
});

test('refresh clears factor state without changing legacy controls',async()=>{
  const {el}=harness();
  el.theme.value='Taiwan';
  await el.themeSearch.click();
  await el.themeResults.children[0].children[0].click();await tick();
  await el.refresh.click();await tick();
  assert.match(el.factorResults.textContent,/Select a question or event again/);
  assert.equal(el.factorReview.hidden,true);
});
