'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'..','src','ubuntu','cdp-helper.js'),'utf8');
const match=src.match(/async function execute\(req\)\{[\s\S]*?\n\}\nasync function main\(/);
assert.ok(match,'original v2.2 Spicetify execute function is present');
const tracks=[{uri:'spotify:track:a',name:'A',artists:[{name:'Artist'}]},
              {uri:'spotify:track:b',name:'B',artists:[{name:'Artist'}]},
              {uri:'spotify:track:a',name:'A again',artists:[{name:'Artist'}]}];
const actions=[];
const c={Spicetify:{Player:{data:{item:tracks[0],context:{uri:'spotify:playlist:list1'}},isPlaying:()=>true,
  getProgress:()=>0,getVolume:()=>0,playUri:async(u,x)=>{actions.push(['play',u,x])},
  next:async()=>{actions.push(['next'])},back:async()=>{actions.push(['previous'])},togglePlay:async()=>{actions.push(['toggle'])},pause:async()=>{},play:async()=>{}},
  Platform:{RootlistAPI:{getContents:async()=>({items:[{type:'playlist',uri:'spotify:playlist:list1',name:'My Playlist'}]})},
    LibraryAPI:{getTracks:async()=>({items:tracks})},
    PlaylistAPI:{getContents:async()=>({items:tracks})}}}};
vm.createContext(c);vm.runInContext(match[0].replace(/\nasync function main\($/,''),c);
(async()=>{
  assert.equal((await c.execute({action:'state'})).data.contextUri,'spotify:playlist:list1');
  assert.equal((await c.execute({action:'library'})).data[0].name,'My Playlist');
  let p=await c.execute({action:'playlist',uri:'spotify:playlist:list1'});
  assert.equal(p.data.length,3,'duplicates preserved to keep original row positions');
  assert.equal(await c.execute({action:'search',query:'ego death'}),undefined);
  assert.equal(await c.execute({action:'home'}),undefined);
  await c.execute({action:'play',uri:'spotify:track:a',contextUri:'spotify:playlist:list1',index:2});
  assert.equal(actions[0][2].index,2);
  await c.execute({action:'next'});await c.execute({action:'previous'});
  assert.deepEqual(actions.slice(1).map(x=>x[0]),['next','previous']);
  console.log('v2.2 Classic mocked CDP tests passed');
})().catch(e=>{console.error(e);process.exitCode=1});