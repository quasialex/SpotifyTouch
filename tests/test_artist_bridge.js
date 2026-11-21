'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../src/ubuntu/cdp-helper.js'),'utf8');
const match=source.match(/async function execute\(req\)\{[\s\S]*?\n\}\nasync function main\(/);
assert.ok(match);
let artistRequests=0, albumRequests=0, playCalls=[];
const artistUri='spotify:artist:1Qp56T7n950O3EGMsSl81D';
const topUri='spotify:track:2wBnZdVWa5jVpvYRfGU7rP';
const albumUri='spotify:album:3lvY0ag1k3qiPCsEM3Wnku';
const spicetify={
 Player:{data:{item:{uri:'spotify:track:5LA5Qhk8UYBHBaqjwqtHDz',name:'Current track',
   metadata:{artist_uri:artistUri,artist_name:'Ghost',album_uri:albumUri,image_xlarge_url:'https://i.scdn.co/image/test'}},context:{uri:'spotify:collection:tracks'}},
   isPlaying:()=>true,getProgress:()=>0,getVolume:()=>1,playUri:async(uri,opts)=>playCalls.push({uri,opts})},
 Platform:{RootlistAPI:{getContents:async()=>({items:[]})},LibraryAPI:{getTracks:async()=>({items:[]})}},
 GraphQL:{Definitions:{queryArtistOverview:'artistQuery',getAlbum:'albumQuery'},Request:async(def,vars)=>{
   if(def==='artistQuery'){
     artistRequests++;
     assert.equal(vars.uri,artistUri);
     assert.equal(vars.preReleaseV2,true);
     return {data:{artistUnion:{profile:{name:'Ghost'},visuals:{avatarImage:{sources:[{url:'https://i.scdn.co/image/artist'}]}},
       discography:{topTracks:{items:[{uid:'1',track:{uri:topUri,name:'Mary On A Cross',artists:{items:[{uri:artistUri,profile:{name:'Ghost'}}]},albumOfTrack:{uri:albumUri,coverArt:{sources:[{url:'https://i.scdn.co/image/cover'}]}}}}]},
       albums:{items:[{releases:{items:[{uri:albumUri,name:'Impera',coverArt:{sources:[{url:'https://i.scdn.co/image/album'}]}}]}}],totalCount:1}}}}};
   }
   if(def==='albumQuery'){
     albumRequests++;
     assert.equal(vars.uri,albumUri);assert.equal(vars.limit,50);
     return {data:{albumUnion:{name:'Impera',coverArt:{sources:[{url:'https://i.scdn.co/image/album'}]},
       tracksV2:{items:[{track:{uri:topUri,name:'Mary On A Cross',artists:{items:[{uri:artistUri,profile:{name:'Ghost'}}]}}}],totalCount:1}}}};
   }
   throw Error('unknown operation');
 }}
};
const c={Spicetify:spicetify};vm.createContext(c);
vm.runInContext(match[0].replace(/\nasync function main\($/,''),c);
(async()=>{
  const state=await c.execute({action:'state'});
  assert.equal(state.data.track.artistUri,artistUri,'Current artist must be touch-navigable');
  assert.equal(state.data.track.image,'https://i.scdn.co/image/test');
  const artist=await c.execute({action:'artist',uri:artistUri});
  assert.ok(artist.ok);
  assert.equal(artist.data.topTracks.length,1);
  assert.equal(artist.data.topTracks[0].name,'Mary On A Cross');
  assert.equal(artist.data.topTracks[0].image,'https://i.scdn.co/image/cover');
  assert.equal(artist.data.albums.length,1);
  assert.equal(artist.data.albums[0].name,'Impera');
  assert.equal(artistRequests,1);
  const album=await c.execute({action:'album',uri:albumUri});
  assert.equal(album.data.tracks.length,1);
  assert.equal(album.data.tracks[0].artistUri,artistUri);
  assert.equal(albumRequests,1);
  const invalid=await c.execute({action:'artist',uri:'spotify:artist:../bad'});
  assert.equal(invalid.ok,false);assert.equal(artistRequests,1);
  await c.execute({action:'play',uri:topUri,contextUri:albumUri,index:0});
  assert.equal(playCalls[0].opts.contextURI,albumUri);
  console.log('Artist/album CDP fixture tests passed');
})().catch(e=>{console.error(e);process.exitCode=1});