'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname,'../excel/taskpane.html'),'utf8');
const code = html.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1];
if (!code) throw Error('No sidebar controller found');

class Element {
  constructor(tagName = 'div') {
    this.tagName = tagName;
    this.children = [];
    this.listeners = {};
    this._textContent = '';
    this.value = '';
    this.className = '';
  }
  get textContent() {
    return this._textContent + this.children.map(c=>c.textContent).join('');
  }
  set textContent(value) { this._textContent=String(value); this.children=[]; }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...children) { this._textContent='';this.children=[...children]; }
  addEventListener(name,callback) { this.listeners[name]=callback; }
  async click() {
    const action=this.listeners.click;
    if (action) return action();
  }
}
const tick = async () => {
  for (let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
};
function setup() {
  const names=['theme','themeSearch','themeCount','themeResults','questionQuery',
    'questionSearch','eventResults','eventCount','selectionNote','status',
    'refresh','key','saveKey','keyMsg','health',
    'factorSource','factorVersion','factorReview','factorReviewCount',
    'factorReviewResults','factorResults'];
  const nodes=Object.fromEntries(names.map(id=>[id,new Element()]));
  const calls=[],writes=[],store={};
  let calculations=0;
  const services = async (name,params={}) => {
    calls.push({name,params});
    if(name==='/health')return {status:'ok',last_successful_run:'2026-10-19T07:00:00Z'};
    if(name==='/entities')return [{id:'wd:Q865',name:'Taiwan',n_live_questions:4}];
    if(name==='/entities/wd%3AQ865')return {questions:[
      {id:'q:linked',name:'Will there be a blockade?',prob:.32,n_rungs:1,status:'live'}
    ]};
    if(name==='/questions') {
      if(params.q==='Taiwan')return {questions:[
        {id:'q:demo',name:'Will China invade Taiwan?',prob:.61,n_rungs:2,status:'live'}
      ]};
      if(params.q==='oil')return {questions:[
        {id:'q:oil',name:'Will oil production fall?',prob:.48,n_rungs:1,status:'live'}
      ]};
      return {questions:[]};
    }
    if(name==='/questions/q%3Alinked')return {id:'q:linked',name:'Will there be a blockade?',
      rungs:[{id:'prop:blockade',name:'Blockade by end of year',prob:.32,status:'live'}]};
    if(name==='/questions/q%3Ademo')return {id:'q:demo',name:'Will China invade Taiwan?',
      rungs:[{id:'prop:2027',name:'Invasion by 2027',prob:.61,status:'live'},
             {id:'prop:2028',name:'Invasion by 2028',prob:.49,status:'live'}]};
    if(name==='/questions/q%3Aoil')return {id:'q:oil',name:'Will oil production fall?',
      rungs:[{id:'prop:oil',name:'Oil production fall',prob:.48,status:'live'}]};
    throw new Error('Unexpected request '+name);
  };
  function activeCell(){
    const ref=()=>{
      const entry={};
      Object.defineProperties(entry,{
        values:{set:v=>writes.push({type:'values',value:v})},
        formulasR1C1:{set:v=>writes.push({type:'formula',value:v})},
        numberFormat:{set:v=>writes.push({type:'format',value:v})}
      });
      return entry;
    };
    return {getResizedRange:()=>({getCell:ref}),getOffsetRange:()=>({select:()=>{}})};
  }
  const sandbox={
    document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag)},
    EventRisk:{request:services,clearCache:()=>{}},
    Office:{onReady:fn=>fn()},
    Excel:{
      CalculationType:{full:'full'},
      run:async fn=>fn({workbook:{getActiveCell:activeCell,
        application:{calculate:()=>{calculations++}}},sync:async()=>{}})
    },
    localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v},
      removeItem:k=>{delete store[k]}},
    globalThis:{},
    Promise,Map,Number,String,Error,Math,
    encodeURIComponent,console
  };
  sandbox.globalThis=sandbox;
  vm.runInNewContext(code,sandbox,{filename:'excel/taskpane.html'});
  return {nodes,calls,writes,store,get calculations(){return calculations}};
}

test('theme Taiwan discovers title matches AND questions linked to the Taiwan entity',async()=>{
  const {nodes,calls}=setup();
  nodes.theme.value='Taiwan';
  await nodes.themeSearch.click();
  assert.equal(nodes.themeResults.children.length,2);
  assert.match(nodes.themeResults.textContent,/Will China invade Taiwan/);
  assert.match(nodes.themeResults.textContent,/Will there be a blockade/);
  assert.ok(calls.some(c=>c.name==='/entities'));
  assert.ok(calls.some(c=>c.name==='/entities/wd%3AQ865'));
  assert.equal(nodes.themeCount.textContent,'(2)');
});
test('clicking a theme question loads ONLY its linked event contracts below',async()=>{
  const {nodes,calls}=setup();
  nodes.theme.value='Taiwan';
  await nodes.themeSearch.click();
  const firstQuestion=nodes.themeResults.children.find(x=>x.textContent.includes('blockade'));
  await firstQuestion.children[0].click(); await tick();
  assert.ok(calls.some(c=>c.name==='/questions/q%3Alinked'));
  assert.equal(nodes.eventCount.textContent,'(1)');
  assert.match(nodes.eventResults.textContent,/Blockade by end of year/);
  assert.doesNotMatch(nodes.eventResults.textContent,/Invasion by 2027/);
});
test('search for questions directly displays their associated event contracts',async()=>{
  const {nodes}=setup();
  nodes.questionQuery.value='oil';
  await nodes.questionSearch.click();
  assert.equal(nodes.eventCount.textContent,'(1)');
  assert.match(nodes.eventResults.textContent,/Oil production fall/);
});
test('clicking an event writes exact ER formulas into Excel',async()=>{
  const {nodes,writes}=setup();
  nodes.theme.value='Taiwan';
  await nodes.themeSearch.click();
  const question=nodes.themeResults.children.find(x=>x.textContent.includes('blockade'));
  await question.children[0].click();await tick();
  const contract=nodes.eventResults.children.find(x=>x.textContent.includes('Blockade by end'));
  await contract.children[0].click();await tick();
  const formulas=writes.filter(x=>x.type==='formula').map(x=>x.value[0][0]);
  assert.deepEqual(formulas,[
    '=ER.EVENT(RC[-1],"title")',
    '=ER.PROB(RC[-2])',
    '=ER.UPDATED(RC[-3])'
  ]);
  assert.ok(writes.some(x=>x.type==='values'&&x.value[0][0]==='prop:blockade'));
  assert.match(nodes.status.textContent,/Inserted prop:blockade/);
});
test('refresh and key controls remain working',async()=>{
  const {nodes,store,calls}=setup();
  nodes.key.value='an-example-access-key';
  await nodes.saveKey.click();
  assert.equal(store.apiKey,'an-example-access-key');
  assert.ok(calls.some(x=>x.name==='/health'));
  await nodes.refresh.click();
  assert.match(nodes.status.textContent,/recalculated/);
});
