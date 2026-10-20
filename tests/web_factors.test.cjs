'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../web/index.html'),'utf8');
const blocks=[...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)];
const controller=blocks.at(-1)?.[1];

test('website JavaScript parses after Factors integration',()=>{
  assert.ok(controller && controller.length>1000);
  assert.doesNotThrow(()=>new vm.Script(controller,{filename:'web/index.html'}));
});

test('site includes Factors catalog, map toggle and accessible legend entry',()=>{
  assert.match(html,/data-tab="factors"/);
  assert.match(html,/id="show-factors"/);
  assert.match(html,/\.swatch\.factor/);
  assert.match(html,/Factor \(qualitative\)/);
});

test('website renders Factor detail via live API with reversal',()=>{
  assert.match(controller,/\/factors\/" \+ encodeURIComponent\(fid\)/);
  assert.match(controller,/\/questions", \{limit: 75\}/);
  assert.match(controller,/factor\.definition/);
  assert.match(controller,/factor\.model/);
});

test('question and proposition details each include a Factors section',()=>{
  assert.match(controller,/\/questions\/\$\{encodeURIComponent\(id\)\}\/factors/);
  assert.match(controller,/\/propositions\/\$\{encodeURIComponent\(id\)\}\/factors/);
  assert.ok((controller.match(/factorSection\(factorMap\)/g)||[]).length>=2);
});

test('graph overlay is opt-in and no numeric loadings are shown for Factors',()=>{
  assert.match(controller,/include_factors: \$\("#show-factors"\)\.checked/);
  assert.match(controller,/factor_link/);
  assert.match(controller,/rule_id/);
  assert.match(controller,/No beta, coefficient or predicted direction/);
});

test('website separates review candidates from established links',()=>{
  assert.match(controller,/mapping\.review_candidates/);
  assert.match(controller,/Review candidates/);
  assert.match(controller,/not accepted/);
});

test('site has explicit Factors methodology and API documentation',()=>{
  for(const segment of ['/factors/{factor_id}/questions',
    '/questions/{id}/factors','/propositions/{id}/factors','/factors','qualitative'])
    assert.ok(html.includes(segment),segment);
  assert.match(html,/not a factor beta|never a factor beta/);
  assert.match(html,/historical graph view uses the current mapping-rule version/);
});

test('no portfolio scanning code returns to website',()=>{
  assert.doesNotMatch(html,/portfolio.?scan|scan.?portfolio|EVENTRISK\.SCAN|\/portfolio\/scan/i);
});
