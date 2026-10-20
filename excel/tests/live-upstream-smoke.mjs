// Read-only integration check against the upstream Event Risk API.
// Run separately from deterministic unit tests: node excel/tests/live-upstream-smoke.mjs
import assert from "node:assert/strict";
const root=(process.env.EVENTRISK_UPSTREAM || "https://geo-risk-api-production.up.railway.app").replace(/\/$/,"");
async function get(uri) {
  const r=await fetch(root+uri,{headers:{Accept:"application/json"},signal:AbortSignal.timeout(30000)});
  if(!r.ok)throw new Error(uri+" returned "+r.status+" "+(await r.text()).slice(0,160));
  return r.json();
}
const health=await get("/health");
assert.ok(health.status,"health response missing status");
const found=await get("/questions?q=taiwan&limit=5");
assert.ok(Array.isArray(found.questions),"/questions lacks questions array");
console.log("Live upstream:",health.status,"Taiwan question count:",found.questions.length);
if(found.questions.length) {
  const q=found.questions[0];
  assert.ok(q.id && q.name,"question lacks id/name");
  const detail=await get("/questions/"+encodeURIComponent(q.id));
  assert.ok(Array.isArray(detail.rungs),"question detail lacks rungs");
  if(detail.rungs.length) {
    const p=await get("/propositions/"+encodeURIComponent(detail.rungs[0].id));
    assert.ok(Array.isArray(p.markets),"proposition detail lacks markets");
    console.log("Question",q.id,"events:",detail.rungs.length,"markets:",p.markets.length);
  }
}
console.log("Read-only upstream smoke PASS");
