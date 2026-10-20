'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const metadata = JSON.parse(fs.readFileSync(path.join(root,'excel/functions.json'),'utf8'));
const script = fs.readFileSync(path.join(root,'excel/functions.js'),'utf8');
const pane = fs.readFileSync(path.join(root,'excel/taskpane.html'),'utf8');
const manifest = fs.readFileSync(path.join(root,'excel/manifest.xml'),'utf8');
const valid = value => JSON.parse(JSON.stringify(value));

function mockApi(pathname, params) {
  const path = decodeURIComponent(pathname);
  if (path === '/questions')
    return {questions:[{id:'q:demo',name:'Will China invade Taiwan?',prob:.64,n_rungs:2,
      headline:{id:'prop:demo',name:'Will China invade Taiwan by 2027?'}}]};
  if (path === '/questions/q:demo')
    return {id:'q:demo',name:'Will China invade Taiwan?',prob:.64,volume_24h:360,
      headline:{id:'prop:demo',name:'Will China invade Taiwan by 2027?'},
      rungs:[{id:'prop:demo',name:'Will China invade Taiwan by 2027?',prob:.61,status:'live'},
             {id:'prop:later',name:'Will China invade Taiwan by 2028?',prob:.42,status:'live'}]};
  if (path === '/propositions') return {propositions:[
    {id:'prop:demo',name:'Will China invade Taiwan by 2027?',prob:.61},
    {id:'prop:later',name:'Will China invade Taiwan by 2028?',prob:.42}
  ]};
  if (path === '/propositions/prop:demo') return {id:'prop:demo',
    name:'Will China invade Taiwan by 2027?',prob:params.get('as_of')?.startsWith('2024')?.12:.61,
    volume_24h:200,open_interest:300,status:'live',close_time:'2027-12-31T00:00:00Z',
    markets:[
      {id:'mkt:kalshi:one',name:'Kalshi venue',relation:'same_as',venue:'kalshi',prob:.25,
        volume_24h:100,open_interest:150,observed_at:'2026-10-19T05:00:00Z'},
      {id:'mkt:polymarket:two',name:'Polymarket venue',relation:'same_as',venue:'polymarket',prob:.74,
        volume_24h:100,open_interest:150,observed_at:'2026-10-19T07:00:00Z'}
    ]};
  if (path === '/propositions/prop:later') return {id:'prop:later',name:'Later',prob:.42,
    markets:[{id:'mkt:kalshi:later',relation:'same_as',observed_at:'2026-10-19T06:00:00Z'}]};
  if (path === '/markets/mkt:kalshi:one') return {id:'mkt:kalshi:one',name:'Source contract',
    prob:.25,proposition:'prop:demo',venue:'kalshi'};
  if (path === '/propositions/prop:demo/history') return {points:[
    {t:'2026-10-18T00:00:00Z',prob:.5,n_markets:2},
    {t:'2026-10-19T00:00:00Z',prob:.61,n_markets:2}
  ]};
  if (path === '/health') return {status:'ok',last_successful_run:'2026-10-19T07:00:00Z'};
  return {__error:404,detail:'Not found: '+path};
}
function functionsHarness() {
  const registered = new Map(), calls = [], store = {};
  const ctx = {
    Map, URLSearchParams, Date, JSON, Number, String, Error, Math, Promise,
    localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v},removeItem:k=>{delete store[k]}},
    CustomFunctions:{
      associate:(id,fn)=>registered.set(id,fn),
      Error:class ExcelError extends Error{},
      ErrorCode:{notAvailable:'notAvailable',invalidValue:'invalidValue'}
    },
    fetch:async url=>{
      const parsed = new URL(url, 'https://example.test');
      calls.push(parsed);
      const data=mockApi(parsed.pathname,parsed.searchParams);
      const ok=!data.__error;
      return {ok,status:ok?200:404,statusText:ok?'OK':'Not found',json:async()=>ok?data:{detail:data.detail}};
    }
  };
  ctx.window=ctx;
  vm.runInNewContext(script,ctx,{filename:'excel/functions.js'});
  return {registered,calls,ctx,store};
}

test('the seven exact ER functions are registered and Portfolio Scan is absent',()=>{
  const required=['PROB','FIELD','HISTORY','ASKNOWN','EVENT','SEARCH','UPDATED'];
  const ids=metadata.functions.map(f=>f.id);
  for(const id of required)assert.ok(ids.includes(id),id+' missing from metadata');
  assert.ok(!ids.includes('SCAN'));
  const {registered}=functionsHarness();
  for(const id of required)assert.equal(typeof registered.get(id),'function',id);
  assert.deepEqual([...registered.keys()].sort(), ids.sort());
});
test('unique add-in identity and ER namespace in Excel manifest',()=>{
  assert.match(manifest, /id="Functions.Namespace" DefaultValue="ER"/);
  assert.match(manifest, /<Id>f00e7ab3-6d20-4316-90ad-9c1e8074af20<\/Id>/);
  assert.doesNotMatch(manifest,/eeb823d5-3150-4ee3-a983-57ef26e13f0b/);
  assert.match(manifest,/Functions.Metadata.Url/);
  assert.match(manifest,/Taskpane.Url/);
});
test('PROB works for proposition, question and exact venue market',async()=>{
  const {registered:r}=functionsHarness();
  assert.equal(await r.get('PROB')('prop:demo'),.61);
  assert.equal(await r.get('PROB')('q:demo'),.64);
  assert.equal(await r.get('PROB')('mkt:kalshi:one'),.25);
});
test('FIELD volume uses exact source 24-hour volume when mkt ID is selected',async()=>{
  const {registered:r}=functionsHarness();
  assert.equal(await r.get('FIELD')('prop:demo','volume'),200);
  assert.equal(await r.get('FIELD')('mkt:kalshi:one','volume'),100);
  assert.equal(await r.get('FIELD')('mkt:kalshi:one','open_interest'),150);
  assert.equal(await r.get('FIELD')('q:demo','volume'),360);
});
test('FIELD rejects unsupported fields rather than returning wrong data',async()=>{
  const {registered:r}=functionsHarness();
  await assert.rejects(()=>r.get('FIELD')('prop:demo','secret_field'),/unsupported market field/);
  await assert.rejects(()=>r.get('FIELD')('prop:demo','nonexistent'),/unsupported market field/);
  await assert.rejects(()=>r.get('FIELD')('prop:demo','open_interest_of_question!!!'),/valid field/);
});
test('ASKNOWN sends as_of and known_as_of together and gets the past observation',async()=>{
  const {registered:r,calls}=functionsHarness();
  assert.equal(await r.get('ASKNOWN')('prop:demo','2024-05-15'),.12);
  const call=calls.find(c=>decodeURIComponent(c.pathname)==='/propositions/prop:demo');
  assert.equal(call.searchParams.get('as_of'),'2024-05-15T00:00:00.000Z');
  assert.equal(call.searchParams.get('known_as_of'),'2024-05-15T00:00:00.000Z');
});
test('ASKNOWN handles Excel date serial numbers',async()=>{
  const {registered:r,calls}=functionsHarness();
  await r.get('ASKNOWN')('q:demo',46200);
  const call=calls.find(c=>decodeURIComponent(c.pathname)==='/questions/q:demo');
  assert.equal(call.searchParams.get('as_of'),call.searchParams.get('known_as_of'));
});
test('EVENT title is exact, unknown descriptions are not fabricated',async()=>{
  const {registered:r}=functionsHarness();
  assert.equal(await r.get('EVENT')('prop:demo','title'),'Will China invade Taiwan by 2027?');
  assert.equal(await r.get('EVENT')('q:demo','title'),'Will China invade Taiwan?');
  await assert.rejects(()=>r.get('EVENT')('prop:demo','description'),/unsupported event field/);
});
test('SEARCH spills real proposition IDs and current probabilities',async()=>{
  const {registered:r,calls}=functionsHarness();
  const rows=valid(await r.get('SEARCH')('Taiwan'));
  assert.deepEqual(rows[0],['Event ID','Event / contract question','Probability']);
  assert.equal(rows[1][0],'prop:demo');
  assert.equal(rows[2][0],'prop:later');
  assert.equal(calls[0].searchParams.get('q'),'Taiwan');
});
test('HISTORY produces numeric Excel dates with a restated series',async()=>{
  const {registered:r,calls}=functionsHarness();
  const rows=valid(await r.get('HISTORY')('prop:demo','2026-10-18','2026-10-19'));
  assert.deepEqual(rows[0],['date','prob','n_markets']);
  assert.equal(rows[1][1],.5);
  assert.equal(rows[2][1],.61);
  assert.ok(Number.isFinite(rows[1][0]));
  assert.equal(calls[0].searchParams.get('start'),'2026-10-18T00:00:00.000Z');
  assert.equal(calls[0].searchParams.get('interval'),'1d');
});
test('HISTORY resolves a question to its current headline and rejects bad ranges',async()=>{
  const {registered:r,calls}=functionsHarness();
  const rows=valid(await r.get('HISTORY')('q:demo','2026-10-18','2026-10-19'));
  assert.equal(rows.length,3);
  assert.ok(calls.some(x=>decodeURIComponent(x.pathname)==='/propositions/prop:demo/history'));
  await assert.rejects(()=>r.get('HISTORY')('prop:demo','2026-10-20','2026-10-18'),/start must be/);
});
test('UPDATED returns the newest source timestamp as an Excel serial date',async()=>{
  const {registered:r}=functionsHarness();
  const value=await r.get('UPDATED')('prop:demo');
  const expected=Date.parse('2026-10-19T07:00:00Z')/86400000+25569;
  assert.equal(value,expected);
  assert.equal(await r.get('UPDATED')('q:demo'),expected);
  const single=await r.get('UPDATED')('mkt:kalshi:one');
  assert.equal(single,Date.parse('2026-10-19T05:00:00Z')/86400000+25569);
});
test('invalid ID returns meaningful error rather than claiming valid data',async()=>{
  const {registered:r}=functionsHarness();
  await assert.rejects(()=>r.get('FIELD')('event_123','volume'),/use a question/);
  await assert.rejects(()=>r.get('UPDATED')('event_123'),/use a question/);
});
test('pane keeps two searches, linked events, refresh and API key; no scan',()=>{
  for(const id of ['theme','themeSearch','themeResults','questionQuery','questionSearch',
    'eventResults','refresh','key','saveKey'])assert.ok(pane.includes('id="'+id+'"'),id);
  assert.match(pane,/\/questions\/" \+ encodeURIComponent\(id\)/);
  assert.match(pane,/=ER\.EVENT\(RC\[-1\]/);
  assert.match(pane,/=ER\.PROB\(RC\[-2\]\)/);
  assert.match(pane,/=ER\.UPDATED\(RC\[-3\]\)/);
  assert.doesNotMatch(pane,/portfolio.?scan|scan.?portfolio|=EVENTRISK\.SCAN/i);
  assert.doesNotMatch(pane,/\.innerHTML\s*=/);
});
test('sidebar inline JavaScript parses',()=>{
  const match=pane.match(/<script>\s*([\s\S]*?)<\/script>/);
  assert.ok(match,'missing inline controller');
  assert.doesNotThrow(()=>new vm.Script(match[1],{filename:'excel/taskpane.html'}));
});
