'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const base = path.join(__dirname, '..');
const defs = JSON.parse(fs.readFileSync(path.join(base,'functions.json'),'utf8'));
const required = ['PROB','FIELD','HISTORY','ASKNOWN','EVENT','SEARCH','UPDATED'];
const qp = {id:'q:taiwan',name:'Will China act against Taiwan?',prob:0.64,
  volume_24h:1900,change_24h:0.03,headline:{id:'p:tw',name:'Event'}};
const pp = {id:'p:tw',name:'China acts against Taiwan by Dec 2027',prob:0.64,
  volume_24h:1200,open_interest:4300,change_24h:0.03,status:'live',
  question:{id:'q:taiwan',name:qp.name},
  markets:[{id:'mkt:kalshi:tw',relation:'same_as',observed_at:'2026-10-18T10:30:00Z'},
           {id:'mkt:polymarket:tw',relation:'near_equivalent',observed_at:'2026-10-19T10:30:00Z'}]};
function runtime() {
  const registry = {};
  const calls = [];
  class ExcelError extends Error {
    constructor(code,msg){super(msg);this.code=code;}
  }
  const sandbox={
    URLSearchParams, console, Date, Number, String, Math, Map,
    localStorage:{getItem:()=>'',setItem:()=>{},removeItem:()=>{}},
    window:{},
    CustomFunctions:{
      Error:ExcelError,ErrorCode:{notAvailable:'NA',invalidValue:'VALUE'},
      associate:(name,fn)=>{registry[name]=fn;}
    },
    fetch:async (raw)=>{
      const url=new URL(raw,'https://example.test');
      calls.push(url);
      let response;
      if(url.pathname==='/questions') response={questions:[qp]};
      else if(url.pathname==='/questions/q%3Ataiwan') response=qp;
      else if(url.pathname==='/propositions/p%3Atw') response=pp;
      else if(url.pathname==='/propositions/p%3Atw/history')
        response={points:[{t:'2026-10-01T00:00:00Z',prob:0.54,n_markets:2}]};
      else throw new Error('Unhandled mock: '+raw);
      return {ok:true,status:200,json:async()=>response};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(base,'functions.js'),'utf8'),sandbox,
    {filename:'functions.js'});
  return {registry,calls};
}
test('Office metadata and JS registry expose exact seven names',()=>{
  const {registry}=runtime();
  for(const name of required){
    assert.equal(typeof registry[name],'function',name);
    const def=defs.functions.find(f=>f.name===name);
    assert.ok(def, 'missing Office metadata '+name);
  }
  assert.equal(new Set(defs.functions.map(f=>f.id)).size,defs.functions.length);
  for(const old of ['CHANGE','NAME','QUESTIONS','RUNGS','PROPOSITIONS','EXPOSURES','SCAN'])
    assert.equal(typeof registry[old],'function','retained '+old);
});
test('ER.PROB returns current probability for question and proposition',async()=>{
  const {registry}=runtime();
  assert.equal(await registry.PROB('p:tw'),0.64);
  assert.equal(await registry.PROB('q:taiwan'),0.64);
});
test('ER.FIELD volume, ER.EVENT title and ER.UPDATED use real observation time',async()=>{
  const {registry}=runtime();
  assert.equal(await registry.FIELD('p:tw','volume'),1200);
  assert.equal(await registry.FIELD('q:taiwan','volume'),1900);
  assert.equal(await registry.EVENT('p:tw','title'),pp.name);
  assert.equal(await registry.EVENT('q:taiwan','title'),qp.name);
  const when=await registry.UPDATED('p:tw');
  assert.ok(Math.abs(when - (Date.parse('2026-10-18T10:30:00Z')/86400000 + 25569)) < 0.00001);
  assert.equal(await registry.UPDATED('q:taiwan'),when);
  await assert.rejects(()=>registry.FIELD('p:tw','not_real'),/unknown field/);
});
test('ER.HISTORY spills dates and probabilities',async()=>{
  const {registry}=runtime();
  const rows=await registry.HISTORY('p:tw','2026-10-01','2026-10-18');
  assert.deepEqual(Array.from(rows[0]),['date','prob','n_markets']);
  assert.equal(rows[1][1],0.54);
});
test('ER.ASKNOWN sends both valid time and knowledge time as same moment',async()=>{
  const {registry,calls}=runtime();
  assert.equal(await registry.ASKNOWN('p:tw','2026-10-01'),0.64);
  const url=calls[0];
  assert.equal(url.searchParams.get('as_of'),'2026-10-01T00:00:00.000Z');
  assert.equal(url.searchParams.get('known_as_of'),'2026-10-01T00:00:00.000Z');
});
test('ER.SEARCH returns question ids and linked headline event ids',async()=>{
  const {registry}=runtime();
  const rows=await registry.SEARCH('Taiwan');
  assert.equal(rows[0][0],'id');
  assert.equal(rows[1][0],'q:taiwan');
  assert.equal(rows[1][4],'p:tw');
});
test('Independent manifest ID, ER namespace and valid sidebar inline JS',()=>{
  const m=fs.readFileSync(path.join(base,'manifest.xml'),'utf8');
  assert.match(m,/id="Functions.Namespace" DefaultValue="ER"/);
  assert.match(m,/<Id>15fbb7e3-86bf-433a-9a85-f2c7c8cf0a15<\/Id>/);
  assert.doesNotMatch(m,/eeb823d5-3150-4ee3-a983-57ef26e13f0b/);
  const html=fs.readFileSync(path.join(base,'taskpane.html'),'utf8');
  for(const id of ['themeQuery','themeResults','questionQuery','questionResults','eventResults',
                   'scan','refresh','key','saveKey'])assert.ok(html.includes('id="'+id+'"'),id);
  assert.ok(html.includes('detail.rungs'));
  const scripts=[...html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(m=>m[1]).filter(Boolean);
  assert.ok(scripts.length);
  for(const script of scripts)new vm.Script(script);
});
test('Standalone service serves correct XML manifest, metadata and health',async()=>{
  const {createServer}=require('../standalone-server.js');
  const server=createServer();
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try {
    const baseUrl='http://127.0.0.1:'+server.address().port;
    const health=await fetch(baseUrl+'/healthz');
    assert.equal(health.status,200);
    const manifest=await (await fetch(baseUrl+'/excel/manifest.xml')).text();
    assert.ok(manifest.includes(baseUrl+'/excel/functions.js'));
    assert.ok(manifest.includes('DefaultValue="ER"'));
    const meta=await (await fetch(baseUrl+'/excel/functions.json')).json();
    assert.ok(meta.functions.some(f=>f.id==='UPDATED'));
    const installer=await (await fetch(baseUrl+'/excel/install.cmd')).text();
    assert.ok(installer.includes('event-risk-analyst.xml'));
    assert.ok(installer.includes('15fbb7e3-86bf-433a-9a85-f2c7c8cf0a15'));
  } finally {await new Promise(resolve=>server.close(resolve));}
});
