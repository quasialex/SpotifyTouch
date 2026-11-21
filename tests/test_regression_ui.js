'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'..','src','ubuntu','web','index.html'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'..','src','ubuntu','web','ui.css'),'utf8');
const js=fs.readFileSync(path.join(__dirname,'..','src','ubuntu','web','ui.js'),'utf8');
assert.doesNotMatch(html,/searchForm|showKeyboard|id="keyboard"|data-page="home"|data-page="recent"/);
assert.doesNotMatch(js,/searchForm|showKeyboard|queryArtistOverview|searchDesktop/);
assert.match(css,/grid-template-columns:205px/);
assert.match(html,/id="cover"/);
assert.match(html,/id="playlists"/);
assert.match(html,/id="results"/);
class E{
  constructor(tag='div'){this.tag=tag;this.children=[];this.className='';this.dataset={};this.style={};this.listeners={};this.hidden=false;this.disabled=false;this.textContent='';this.scrollTop=0;this.classList={toggle:()=>{}};}
  append(...els){for(const el of els){if(el.tag==='fragment')this.children.push(...el.children);else this.children.push(el)}}
  replaceChildren(...els){this.children=[];this.append(...els)}
  addEventListener(type,cb){(this.listeners[type]??=[]).push(cb)}
  async click(){for(const cb of this.listeners.click||[])await cb({preventDefault(){},stopPropagation(){}})}
}
const id=[...html.matchAll(/id="([^\"]+)"/g)].map(x=>x[1]);const els=Object.fromEntries(id.map(x=>[x,new E()]));
const quick=[...html.matchAll(/class="quick-item" data-page="([^"]+)" data-title="([^"]+)"/g)].map(x=>{const el=new E();el.dataset.page=x[1];el.dataset.title=x[2];return el});
const doc={getElementById:id=>els[id],createElement:tag=>new E(tag),createDocumentFragment:()=>new E('fragment'),querySelectorAll:query=>query==='.quick-item'?quick:[]};
const w={parent:null,postMessage:()=>{}};w.parent=w;
const c={document:doc,location:{search:'?demo'},window:w,URLSearchParams,performance:{now:()=>0},setInterval:()=>{},setTimeout:()=>{},fetch:()=>{throw Error('demo should not fetch')},console};
vm.createContext(c);vm.runInContext(js,c);
async function flush(){for(let i=0;i<16;i++)await new Promise(r=>setImmediate(r))}
(async()=>{
  await flush();
  assert.equal(els.pageTitle.textContent,'Favourite Mix');
  assert.equal(els.playlists.children.length,2);
  assert.equal(els.results.children.length,2);
  assert.equal(els.results.children[1].dataset.index,'1');
  await quick.find(x=>x.dataset.page==='liked').click();await flush();
  assert.equal(els.pageTitle.textContent,'Liked Songs');
  assert.equal(els.results.children.length,2);
  assert.ok(!els.playCollection.hidden);
  console.log('v2.2 Classic UI DOM tests passed');
})().catch(e=>{console.error(e);process.exitCode=1});