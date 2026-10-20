'use strict';
// Isolated Excel front-end for Railway. Existing event-graph API is read-only upstream.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { URL } = require('node:url');
const folder = __dirname;
const ID = '15fbb7e3-86bf-433a-9a85-f2c7c8cf0a15';
const FILE = 'event-risk-analyst.xml';
const UPSTREAM = (process.env.EVENTRISK_UPSTREAM || 'https://geo-risk-api-production.up.railway.app').replace(/\/$/, '');
const allowFiles = new Map([
  ['functions.js','text/javascript; charset=utf-8'],
  ['functions.json','application/json; charset=utf-8'],
  ['taskpane.html','text/html; charset=utf-8'],
  ['icon-16.png','image/png'],['icon-32.png','image/png'],
  ['icon-64.png','image/png'],['icon-80.png','image/png']
]);
const apiRoutes = /^\/(health|questions(?:\/|$)|propositions(?:\/|$)|securities(?:\/|$)|portfolio\/scan$)/;
const json = (res, status, value) => {
  res.writeHead(status, {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
  res.end(JSON.stringify(value));
};
function origin(req) {
  if (process.env.PUBLIC_ORIGIN) return process.env.PUBLIC_ORIGIN.replace(/\/$/, '');
  const host = (req.headers.host || 'localhost:3000').replace(/[^a-zA-Z0-9.:-]/g, '');
  const scheme = req.headers['x-forwarded-proto'] === 'https' ? 'https' : 'http';
  return scheme + '://' + host;
}
async function proxy(req, res) {
  const target = UPSTREAM + req.url;
  const headers = {'Accept':'application/json'};
  if (req.headers['x-api-key']) headers['X-API-Key'] = req.headers['x-api-key'];
  if (req.headers['content-type']) headers['Content-Type'] = req.headers['content-type'];
  const chunks = [];
  if (req.method === 'POST') {
    for await (const chunk of req) chunks.push(chunk);
    if (Buffer.concat(chunks).length > 1_000_000) return json(res,413,{detail:'Request too large'});
  }
  try {
    const response = await fetch(target,{method:req.method,headers,
      ...(req.method==='POST'?{body:Buffer.concat(chunks)}:{}),
      signal:AbortSignal.timeout(45000)});
    const data = Buffer.from(await response.arrayBuffer());
    res.writeHead(response.status, {'Content-Type':response.headers.get('content-type')||'application/json',
      'Cache-Control':'no-store'});
    res.end(data);
  } catch {
    json(res,502,{detail:'Cannot reach the Event Risk API'});
  }
}
async function handler(req, res) {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/healthz') return json(res,200,{status:'ok',product:'er-excel-analyst'});
  if (req.method === 'GET' && pathname === '/') {
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});
    return res.end('<!doctype html><title>Event Risk Analyst Excel</title><h1>Event Risk Analyst Excel</h1><p>Independent Office add-in (ER.* formulas).</p><p><a href="/excel/manifest.xml">Excel manifest</a> · <a href="/excel/install.cmd">Windows installer</a></p>');
  }
  if (req.method === 'GET' && /^\/excel\/(manifest\.xml|install\.cmd|uninstall\.cmd)$/.test(pathname)) {
    const name = pathname.split('/').pop();
    const src = fs.readFileSync(path.join(folder,name),'utf8');
    const base = origin(req);
    let body = src.replaceAll('{BASE}',base).replaceAll('{ID}',ID).replaceAll('{FILE}',FILE);
    if (name.endsWith('.cmd')) body=body.replace(/\r?\n/g,'\r\n');
    res.writeHead(200,{'Content-Type':name.endsWith('.xml')?'application/xml; charset=utf-8':'application/octet-stream',
      'Cache-Control':'no-store'});
    return res.end(body);
  }
  if (req.method === 'GET' && pathname.startsWith('/excel/')) {
    const name = pathname.slice('/excel/'.length);
    if (!allowFiles.has(name)) return json(res,404,{detail:'Not found'});
    res.writeHead(200,{'Content-Type':allowFiles.get(name),'Cache-Control':'public, max-age=60'});
    return fs.createReadStream(path.join(folder,name)).pipe(res);
  }
  if (apiRoutes.test(pathname) && ['GET','POST'].includes(req.method)) return proxy(req,res);
  return json(res,404,{detail:'Not found'});
}
function createServer() {return http.createServer((req,res)=>{Promise.resolve(handler(req,res)).catch(
  ()=>json(res,500,{detail:'Excel add-in server error'}));});}
if (require.main===module) {
  createServer().listen(Number(process.env.PORT)||3000,'0.0.0.0',
    ()=>console.log('Event Risk Analyst Excel running'));
}
module.exports={createServer};
