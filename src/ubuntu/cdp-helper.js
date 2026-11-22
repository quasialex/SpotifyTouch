/* Spotify Touch: executes within the authenticated Spotify desktop page.
   No Web API search requests: the returned 429 was a real API error.
   RootlistAPI and LibraryAPI getContents have been verified on this user's client. */
'use strict';
const payload=process.argv[2]||'';
const write=x=>process.stdout.write(JSON.stringify(x)+'\n');
if(payload.length>60000) {write({ok:false,error:'Input too large'});process.exit(0);}
let req;
try {req=JSON.parse(Buffer.from(payload,'base64').toString('utf8'));}
catch {write({ok:false,error:'Malformed request'});process.exit(0);}
const actions=new Set(['health','state','library','liked','playlist','artist','album','play','pause','resume','toggle','next','previous']);
if(!actions.has(req.action)) {write({ok:false,error:'Unsupported command'});process.exit(0);}

async function execute(req){
  const S=globalThis.Spicetify;
  if(!S?.Player||!S?.Platform) return {ok:false,error:'Spotify client not ready (login required?)'};
  const safe=fn=>{try{return fn()}catch{return null}};
  const spotifyImage = value => {
    if(typeof value!=='string')return '';
    if(/^https:\/\/[a-z0-9.-]+\//i.test(value))return value;
    if(/^spotify:image:[a-f0-9]{40}$/i.test(value))return 'https://i.scdn.co/image/'+value.slice(14);
    return '';
  };
  const image = x => {
    if(!x || typeof x!=='object')return '';
    const sources = [x.images,x.coverArt?.sources,x.visuals?.avatarImage?.sources,
      x.visuals?.coverArt?.sources,x.albumOfTrack?.coverArt?.sources,
      x.album?.images,x.album?.coverArt?.sources,x.headerImage?.sources,
      x.metadata?.image_xlarge_url,x.metadata?.image_large_url,x.metadata?.image_url,
      x.image_url,x.image];
    for(const v of sources){
      if(Array.isArray(v)){
        for(const item of v){const u=spotifyImage(item?.url||item?.uri||item);if(u)return u;}
      }else {const u=spotifyImage(v);if(u)return u;}
    }
    return '';
  };
  function normalize(raw){
    const x=raw?.item?.data||raw?.track?.data||raw?.track||raw?.data||raw||{};
    const uri=x.uri||x._uri||x.link||raw?.uri||raw?._uri||'';
    const kind=uri.includes(':artist:')?'artist':uri.includes(':playlist:')?'playlist':uri.includes(':album:')?'album':'track';
    const artistList=Array.isArray(x.artists)?x.artists:(x.artists?.items||[]);
    const artists=artistList.map(a=>a?.name||a?.profile?.name||a?.data?.profile?.name).filter(Boolean);
    const artistUri=artistList.find(a=>/^spotify:artist:[A-Za-z0-9]+$/.test(a?.uri||''))?.uri||
      x.metadata?.artist_uri||x.metadata?.['artist_uri:0']||x.artistUri||'';
    const albumUri=x.album?.uri||x.albumOfTrack?.uri||x.metadata?.album_uri||'';
    const name=x.name||x.title||x.profile?.name||x.metadata?.title||raw?.name||'Untitled';
    return {uri,kind,name,subtitle:artists.join(', ')||x.metadata?.artist_name||
      x.owner?.name||x.owner?.displayName||x.description||raw?.subtitle||kind,
      image:image(x)||image(raw),artistUri,albumUri};
  }
  function albumItems(list){
    const found=[],seen=new Set();
    for(const item of Array.isArray(list)?list:[]){
      const candidates=item?.releases?.items||item?.releases||[item?.album||item];
      for(const release of Array.isArray(candidates)?candidates:[]){
        const album=release?.album||release?.data||release;
        const normalized=normalize(album);
        if(normalized.kind==='album'&&/^spotify:album:[A-Za-z0-9]+$/.test(normalized.uri)&&!seen.has(normalized.uri)){
          found.push(normalized);seen.add(normalized.uri);
        }
      }
    }
    return found.slice(0,30);
  }
  const unique=items=>{const seen=new Set();return items.filter(x=>x.uri&&!seen.has(x.uri)&&seen.add(x.uri)).slice(0,120);};
  const response=(data,notice)=>({ok:true,data, ...(notice?{notice}:{})});
  async function rootlist(){
    const r=await S.Platform.RootlistAPI.getContents({flatten:true});
    const found=[];
    function descend(items,depth=0){
      if(depth>8||found.length>200)return;
      for(const item of items||[]){
        if(item.type==='playlist'&&item.uri)found.push(normalize(item));
        if(Array.isArray(item.items))descend(item.items,depth+1);
      }
    }
    descend(r.items||[]);
    return unique(found);
  }
  try {
    switch(req.action){
      case 'health':return {ok:true,data:{ready:true,player:!!S.Player,library:!!S.Platform.LibraryAPI,rootlist:!!S.Platform.RootlistAPI,spotifySearch:false}};
      case 'state':{
        const track=S.Player.data?.item||{};
        const meta=track.metadata||{};
        const normalized=normalize(track);
        if(!normalized.artistUri)normalized.artistUri=meta.artist_uri||meta['artist_uri:0']||'';
        if(!normalized.albumUri)normalized.albumUri=meta.album_uri||'';
        return response({playing:!!S.Player.isPlaying?.(),track:normalized,progressMs:safe(()=>S.Player.getProgress())||0,volume:safe(()=>S.Player.getVolume())||0,contextUri:S.Player.data?.context?.uri||''});
      }
      case 'pause':await S.Player.pause();return response(null);
      case 'resume':await S.Player.play();return response(null);
      case 'toggle':await S.Player.togglePlay();return response(null);
      case 'next':await S.Player.next();return response(null);
      case 'previous':await S.Player.back();return response(null);
      case 'play':{
        if(!/^spotify:(track|album|playlist|artist):[A-Za-z0-9]+$/.test(req.uri||''))throw Error('Invalid Spotify URI');
        if(req.contextUri){
          // Spicetify's documented context argument. This tells Spotify which
          // collection Next / automatic playback should continue from.
          if(!/^(spotify:(?:playlist|album):[A-Za-z0-9]+|spotify:collection:tracks)$/.test(req.contextUri))throw Error('Invalid playback context');
          if(req.contextUri==='spotify:collection:tracks'){
            const library=S.Platform.LibraryAPI;
            const player=S.Platform.PlayerAPI;
            if(typeof library?.getTracks!=='function' ||
               typeof player?.clearQueue!=='function' ||
               typeof player?.addToQueue!=='function')
              throw Error('Liked Songs queue APIs unavailable');

            const result=await library.getTracks({limit:60,offset:0});
            const raw=Array.isArray(result)
              ? result : (result?.items||result?.tracks||[]);
            const liked=unique(raw.map(normalize).filter(x=>
              x.kind==='track' &&
              /^spotify:track:[A-Za-z0-9]+$/.test(x.uri)));

            const index=req.index;
            if(!Number.isInteger(index) || index<0 ||
               index>=liked.length || liked[index].uri!==req.uri)
              throw Error('Liked Songs changed; reopen the list and retry');

            await S.Player.playUri(req.uri);
            await new Promise(resolve=>setTimeout(resolve,1200));
            await player.clearQueue();

            const following=liked.slice(index+1).map(x=>({uri:x.uri}));
            for(let i=0;i<following.length;i+=20)
              await player.addToQueue(following.slice(i,i+20));

            return response({
              requestedContext:req.contextUri,
              queued:following.length
            });
          }
          const context={contextURI:req.contextUri,trackUri:req.uri};
          if(Number.isInteger(req.index)&&req.index>=0&&req.index<=9999)context.index=req.index;
          await S.Player.playUri(req.uri,context);
          return response({requestedContext:req.contextUri,playerContext:S.Player.data?.context?.uri||''});
        }
        await S.Player.playUri(req.uri);return response({requestedContext:null});
      }
      case 'library':return response(await rootlist());
      case 'liked':{
        // The method exists in the actual client; its arguments/shape remain version-sensitive.
        if(typeof S.Platform.LibraryAPI.getTracks!=='function')throw Error('Liked Songs API unavailable in this client');
        const r=await S.Platform.LibraryAPI.getTracks({limit:60,offset:0});
        const items=Array.isArray(r)?r:(r?.items||r?.tracks||[]);
        const results=unique(items.map(normalize).filter(x=>x.kind==='track'));
        if(!results.length)throw Error('Liked Songs returned no compatible track list yet');
        return response(results);
      }
      case 'artist':{
        if(!/^spotify:artist:[A-Za-z0-9]+$/.test(req.uri||''))throw Error('Invalid artist URI');
        const G=S.GraphQL;
        if(!G?.Definitions?.queryArtistOverview||typeof G.Request!=='function')throw Error('Artist catalog API unavailable');
        const raw=await G.Request(G.Definitions.queryArtistOverview,
          {uri:req.uri,locale:'intl-en',preReleaseV2:true});
        const artist=(raw?.data||raw)?.artistUnion;
        if(!artist || !artist.discography)throw Error('Spotify artist catalog returned an unsupported format');
        const top=artist.discography.topTracks?.items||[];
        const tracks=top.map(item=>normalize(item.track||item)).filter(x=>x.kind==='track'&&/^spotify:track:[A-Za-z0-9]+$/.test(x.uri)).slice(0,10);
        const albums=albumItems([...(artist.discography.albums?.items||[]),...(artist.discography.popularReleasesAlbums?.items||[])]);
        return response({kind:'artist',uri:req.uri,
          name:artist.profile?.name||'Artist',image:image(artist),
          topTracks:tracks,albums,totalAlbums:artist.discography.albums?.totalCount||albums.length});
      }
      case 'album':{
        if(!/^spotify:album:[A-Za-z0-9]+$/.test(req.uri||''))throw Error('Invalid album URI');
        const G=S.GraphQL;
        if(!G?.Definitions?.getAlbum||typeof G.Request!=='function')throw Error('Album catalog API unavailable');
        const raw=await G.Request(G.Definitions.getAlbum,
          {uri:req.uri,locale:'en',limit:50,offset:0},{persistCache:true});
        const album=(raw?.data||raw)?.albumUnion;
        if(!album)throw Error('Spotify album catalog returned an unsupported format');
        const tracks=(album.tracksV2?.items||album.tracks?.items||[])
          .map(x=>normalize(x.track?.data||x.track||x))
          .filter(x=>x.kind==='track'&&/^spotify:track:[A-Za-z0-9]+$/.test(x.uri))
          .slice(0,50);
        return response({kind:'album',uri:req.uri,name:album.name||'Album',
          image:image(album),tracks,totalTracks:album.tracksV2?.totalCount||album.tracks?.totalCount||tracks.length});
      }
      case 'playlist':{
        if(!/^spotify:playlist:[A-Za-z0-9]+$/.test(req.uri||''))throw Error('Invalid playlist URI');
        const service=S.Platform.PlaylistAPI;
        if(!service||typeof service.getContents!=='function')throw Error('Spotify PlaylistAPI.getContents not available');
        const r=await service.getContents(req.uri,{offset:0,limit:100});
        const raw=r?.items||r?.contents?.items||r?.rows||[];
        return response(raw.map(normalize).filter(x=>x.kind==='track'&&x.uri));
      }
    }
  }catch(e){return {ok:false,error:String(e?.message||e)};}
}
async function main(){
  const result=await fetch('http://127.0.0.1:9222/json/list');
  const tabs=await result.json();
  const page=tabs.find(x=>x.type==='page'&&String(x.url||'').includes('xpui.app.spotify.com'));
  if(!page?.webSocketDebuggerUrl)throw Error('Authenticated Spotify player page unavailable');
  const ws=new WebSocket(page.webSocketDebuggerUrl);
  const expression=`(${execute.toString()})(${JSON.stringify(req)})`;
  const data=await new Promise((resolve,reject)=>{
    const t=setTimeout(()=>{ws.close();reject(Error('Spotify operation timed out'));},17000);
    ws.addEventListener('open',()=>ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression,awaitPromise:true,returnByValue:true,userGesture:true}})));
    ws.addEventListener('message',e=>{
      let msg;try{msg=JSON.parse(e.data)}catch{return}
      if(msg.id!==1)return;
      clearTimeout(t);ws.close();
      if(msg.error)return reject(Error(msg.error.message));
      if(msg.result?.exceptionDetails)return reject(Error(msg.result.exceptionDetails.text));
      resolve(msg.result?.result?.value||{ok:false,error:'Empty Spotify response'});
    });
    ws.addEventListener('error',()=>{clearTimeout(t);reject(Error('CDP WebSocket error'));});
  });
  write(data);
}
main().catch(e=>write({ok:false,error:String(e.message||e)}));