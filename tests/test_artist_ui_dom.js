'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),vm=require('vm');
const root=path.join(__dirname,'../src/ubuntu/web');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const src=fs.readFileSync(path.join(root,'ui.js'),'utf8');
class E{
  constructor(tag='div'){this.tag=tag;this.children=[];this.className='';this.dataset={};this.style={};this.listeners={};
    this.hidden=false;this.disabled=false;this.textContent='';this.scrollTop=0;this.classList={toggle:()=>{},add:()=>{}};this.isConnected=true;}
  append(...els){for(const el of els){if(el.tag==='fragment')this.children.push(...el.children);else this.children.push(el)}}
  replaceChildren(...els){this.children=[];this.append(...els)}
  addEventListener(type,cb){(this.listeners[type]??=[]).push(cb)}
  async click(){for(const cb of this.listeners.click||[])await cb({preventDefault(){},stopPropagation(){}})}
}
const ids=[...html.matchAll(/id="([^"]+)"/g)].map(x=>x[1]);
const els=Object.fromEntries(ids.map(x=>[x,new E()]));
const quick=[...html.matchAll(/class="quick-item" data-page="([^"]+)" data-title="([^"]+)"/g)].map(x=>{const el=new E();el.dataset.page=x[1];el.dataset.title=x[2];return el});
const doc={getElementById:id=>els[id],createElement:tag=>new E(tag),createDocumentFragment:()=>new E('fragment'),querySelectorAll:q=>q==='.quick-item'?quick:[]};
const win={};win.parent=win;
const context={document:doc,location:{search:'?demo'},window:win,URLSearchParams,performance:{now:()=>0},setInterval:()=>{},setTimeout:()=>{},fetch:()=>{throw Error('demo should not fetch')},console};
vm.createContext(context);vm.runInContext(src,context);
async function flush(){for(let i=0;i<12;i++)await new Promise(r=>setImmediate(r))}
(async()=>{
 await flush();assert.equal(els.pageTitle.textContent,'Favourite Mix');
 assert.equal(els.nowOpenArtist.disabled,false,'Artist navigable if URI exists');
 await els.nowOpenArtist.click();await flush();
 assert.equal(els.pageTitle.textContent,'Demo Artist');
 assert.equal(els.results.children[1].textContent,'Popular tracks');
 assert.equal(els.results.children[3].textContent,'Albums');
 assert.equal(els.playCollection.textContent,'▶ Artist');
 await els.navBack.click();await flush();assert.equal(els.pageTitle.textContent,'Favourite Mix');
 await quick.find(x=>x.dataset.page==='liked').click();await flush();assert.equal(els.pageTitle.textContent,'Liked Songs');
 console.log('Artist navigation DOM mocked test passed');
})().catch(e=>{console.error(e);process.exitCode=1});