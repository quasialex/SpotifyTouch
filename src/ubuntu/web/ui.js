'use strict';
// Spotify Touch: UI and presentation only. Catalog and playback live in Spotify on Ubuntu.
const $ = id => document.getElementById(id);
const DEMO = new URLSearchParams(location.search).has('demo');
const stack = [];
let stackIndex = -1, navToken = 0, playlists = [], playing = false;
let suppressClickUntil = 0, busyPlayback = false;
let activeCollection=null; // {page,uri,items}; only known-track collections set playback context
let currentPlaylistUri='';
let refreshInFlight=false, lastCover='', nowArtistUri='', activePlayableUri='';
const catalogCache=new Map(); // Max six on-demand pages, no background requests.
const artistUriRe=/^spotify:artist:[A-Za-z0-9]+$/;
const albumUriRe=/^spotify:album:[A-Za-z0-9]+$/;

const demoData = [
  {name:'Favourite Mix',subtitle:'Playlist',uri:'spotify:playlist:demo01',kind:'playlist'},
  {name:'Evening Music',subtitle:'Playlist',uri:'spotify:playlist:demo02',kind:'playlist'}
];
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const validImage = url => typeof url === 'string' && /^https:\/\/[a-z0-9.-]+\//i.test(url) ? url : null;
function setConnection(message, good=false) { $('connection').textContent=message; $('connection').style.color=good?'#8af2a3':'#d9b79b'; }
function setNotice(message='') { $('notice').textContent=message; $('notice').hidden=!message; }
function spinner(message) { $('results').innerHTML=`<p class="message">${escapeHtml(message)}</p>`; }
async function api(action, params={}) {
  if (DEMO) {
    if (action==='state') return {playing,track:{name:'Demo track',subtitle:'Demo Artist',artistUri:'spotify:artist:demo01'},contextUri:'spotify:playlist:demo01'};
    if (action==='health') return {ready:true};
    if (action==='library') return demoData.filter(x=>x.kind==='playlist');
    if (action==='liked'||action==='playlist') return [
      {kind:'track',name:'First track',subtitle:'An Artist',uri:'spotify:track:demo01'},
      {kind:'track',name:'Second track',subtitle:'Another Artist',uri:'spotify:track:demo02'}
    ];
    if (action==='artist') return {kind:'artist',uri:params.uri,name:'Demo Artist',image:'',topTracks:[
      {uri:'spotify:track:demo03',kind:'track',name:'Demo Popular Track',subtitle:'Demo Artist'}],albums:[
      {uri:'spotify:album:demo03',kind:'album',name:'Demo Album',subtitle:'Album'}],totalAlbums:1};
    if (action==='album') return {kind:'album',uri:params.uri,name:'Demo Album',tracks:[
      {uri:'spotify:track:demo03',kind:'track',name:'Demo Popular Track',subtitle:'Demo Artist'}]};
    if (action==='toggle') {playing=!playing;return null;}
    return null;
  }
  const gets = new Set(['health','state','library','liked','playlist','artist','album']);
  const url=gets.has(action)?'/api?'+new URLSearchParams({action,...params}):'/api';
  const res=await fetch(url,gets.has(action)?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...params})});
  if(!res.ok) throw new Error(`Server error ${res.status}`);
  const response=await res.json();
  if(!response.ok) throw new Error(response.error||'Spotify operation unavailable');
  if(response.notice) setNotice(response.notice);
  return response.data;
}
function itemElement(item,compact=false) {
  const b=document.createElement('button'); b.className=compact?'side-item':'result-item'; b.type='button';
  b.dataset.kind=item.kind||'track'; b.dataset.uri=item.uri||''; b.dataset.name=item.name||'';
  const image=validImage(item.image);
  const avatar=image?`<img class="thumbnail" src="${escapeHtml(image)}" loading="lazy" alt="">`:'<span class="thumbnail placeholder">♫</span>';
  b.innerHTML=avatar+`<span class="item-text"><strong>${escapeHtml(item.name||'Untitled')}</strong><small>${escapeHtml(item.subtitle||item.kind||'')}</small></span>${compact?'':'<span class="chevron">›</span>'}`;
  return b;
}
function fillList(target,items,emptyMessage,compact=false) {
  target.replaceChildren();
  if(!Array.isArray(items)||items.length===0) {const p=document.createElement('p');p.className='message';p.textContent=emptyMessage;target.append(p);return;}
  const fragment=document.createDocumentFragment();
  for(const [index,item] of items.entries()) {
    const element=itemElement(item,compact);
    element.dataset.index=String(index); // preserve position even when a track occurs twice
    fragment.append(element);
  }
  target.append(fragment);
}
async function loadLibrary() {
  try {
    playlists=await api('library');
    fillList($('playlists'),playlists,'No playlists found.',true);
    setConnection(DEMO?'Preview mode':'Connected',true);
  } catch(e) { fillList($('playlists'),[],'Library unavailable',true);setConnection(e.message); }
}
function addSection(root,label,items,emptyMessage){
  const h=document.createElement('h2');h.className='artist-section';h.textContent=label;root.append(h);
  if(!items.length){const p=document.createElement('p');p.className='message';p.textContent=emptyMessage;root.append(p);return;}
  for(const [index,item] of items.entries()){
    const b=itemElement(item);b.dataset.index=String(index);
    if(item.kind==='album')b.classList.add('artist-release');
    root.append(b);
  }
}
function renderDetail(detail,page){
  const root=$('results');root.replaceChildren();
  const hero=document.createElement('div');hero.className='artist-hero';
  const art=validImage(detail.image);
  if(art){const img=document.createElement('img');img.src=art;img.alt='';hero.append(img);}
  const text=document.createElement('div');
  const heading=document.createElement('strong');heading.textContent=detail.name||'Untitled';text.append(heading);
  const sub=document.createElement('small');
  sub.textContent=page==='artist'?'Top tracks and albums':'Album tracks';text.append(sub);
  hero.append(text);root.append(hero);
  if(page==='artist'){
    addSection(root,'Popular tracks',detail.topTracks||[],'No popular tracks returned by Spotify.');
    addSection(root,'Albums',detail.albums||[],'No album data returned by Spotify.');
  }else addSection(root,'Tracks',detail.tracks||[],'Track listing not available for this album. Use Play to play the album.');
}
async function detailData(page,uri){
  const key=page+':'+uri,found=catalogCache.get(key);
  if(found && Date.now()-found.at<180000)return found.data;
  const data=await api(page,{uri});
  catalogCache.delete(key);catalogCache.set(key,{at:Date.now(),data});
  if(catalogCache.size>6)catalogCache.delete(catalogCache.keys().next().value);
  return data;
}
function setHistoryControls(){ $('navBack').disabled=stackIndex<=0; $('navForward').disabled=stackIndex<0||stackIndex>=stack.length-1; }
async function navigate(page,title,params={},addHistory=true) {
  const myToken=++navToken;
  if(addHistory) { stack.splice(stackIndex+1); stack.push({page,title,params}); stackIndex=stack.length-1; }
  setHistoryControls(); $('pageTitle').textContent=title; $('resultCount').textContent='';spinner('Loading…');setNotice('');
  for(const b of document.querySelectorAll('.quick-item')) b.classList.toggle('active',b.dataset.page===page);
  try {
    if(page==='artist'||page==='album'){
      const detail=await detailData(page,params.uri);
      if(myToken!==navToken)return;
      if(!detail || detail.kind!==page)throw new Error('Spotify returned an unexpected catalog result');
      renderDetail(detail,page);
      activeCollection=page==='album'?{page,uri:params.uri,items:detail.tracks||[]}:null;
      activePlayableUri=params.uri;
      $('playCollection').hidden=false;
      $('playCollection').textContent=page==='artist'?'▶ Artist':'▶ Album';
      $('results').scrollTop=0;
      $('resultCount').textContent=page==='artist'?
        `${(detail.topTracks||[]).length} top tracks · ${(detail.albums||[]).length} albums`:
        `${(detail.tracks||[]).length} tracks`;
      return;
    }
    const items=await api(page,params);
    if(myToken!==navToken) return;
    if(!Array.isArray(items)) throw new Error('Spotify returned an unexpected data format');
    fillList($('results'),items,'No tracks found in this playlist.');
    activeCollection=(page==='liked'||page==='playlist') ? {page,uri:page==='liked'?'spotify:collection:tracks':params.uri,items} : null;
    activePlayableUri='';
    $('playCollection').textContent='▶ Play';
    $('playCollection').hidden=!(activeCollection&&activeCollection.items.some(i=>i.kind==='track'));
    $('results').scrollTop=0;
    $('resultCount').textContent=`${items.length} item${items.length===1?'':'s'}`;
  } catch(e) {
    if(myToken!==navToken) return;
    activeCollection=null;activePlayableUri='';$('playCollection').hidden=true;
    if(page==='album'&&albumUriRe.test(params.uri||'')){
      // Catalog track-list failure must not prevent playing an album.
      activePlayableUri=params.uri;
      $('playCollection').textContent='▶ Album';
      $('playCollection').hidden=false;
      spinner('Album track list unavailable. You can still play the album.');
    } else spinner('This section is not available yet.');
    setNotice(e.message);
  }
}
async function playSelectedTrack(uri,context=null,index=-1){
  if(busyPlayback)return; // prevent multiple queued play requests from repeated taps
  busyPlayback=true;
  const payload={uri};
  if(context&&index>=0){payload.contextUri=context.uri;payload.index=index;}
  setConnection('Starting playback…');
  try{
    await api('play',payload);
    if(context?.uri?.startsWith('spotify:playlist:')) currentPlaylistUri=context.uri;
  }catch(e){setConnection(e.message);setNotice(e.message);}
  finally{busyPlayback=false;setTimeout(refresh,800);}
}
function enterItem(button) {
  const {uri='',kind='',name=''}=button.dataset;
  if(!uri||DEMO&&(kind==='track')) return;
  if(kind==='track') {
    const context=activeCollection;
    const index=context ? Number(button.dataset.index) : -1;
    void playSelectedTrack(uri,context,index);
    return;
  }
  if(kind==='playlist'||(kind==='album'&&albumUriRe.test(uri)))
    navigate(kind,name,{uri});
}
for(const area of [$('results'),$('playlists')]) {
  area.addEventListener('click',e=>{
    if(performance.now()<suppressClickUntil) {e.preventDefault();e.stopPropagation();return;}
    const button=e.target.closest('button[data-uri]');if(button)enterItem(button);
  },true);
  // labwc may synthesize mouse movement for touchscreen drag; implement vertical scrolling
  // only for mouse-like pointer events. Real touch pointers use browser-native pan-y.
  let down=false,drag=false,startY=0,lastY=0;
  area.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse'||e.button!==0)return;down=true;drag=false;startY=lastY=e.clientY;});
  area.addEventListener('pointermove',e=>{if(!down)return;const difference=e.clientY-startY;
    if(Math.abs(difference)>7) {drag=true;area.scrollTop-=e.clientY-lastY;e.preventDefault();}lastY=e.clientY;
  });
  const end=()=>{if(drag)suppressClickUntil=performance.now()+180;down=false;drag=false;};
  area.addEventListener('pointerup',end);area.addEventListener('pointercancel',end);area.addEventListener('pointerleave',end);
}
for(const b of document.querySelectorAll('.quick-item')) b.addEventListener('click',()=>{
  if(b.dataset.page==='current'){
    if(currentPlaylistUri) {
      const saved=playlists.find(p=>p.uri===currentPlaylistUri);
      navigate('playlist',saved?.name||'Current Playlist',{uri:currentPlaylistUri});
    } else setNotice('No current playlist reported. Select a playlist or start one from your phone.');
  } else navigate(b.dataset.page,b.dataset.title);
});
$('navBack').addEventListener('click',()=>{if(stackIndex>0){const x=stack[--stackIndex];navigate(x.page,x.title,x.params,false);}});
$('navForward').addEventListener('click',()=>{if(stackIndex+1<stack.length){const x=stack[++stackIndex];navigate(x.page,x.title,x.params,false);}});
$('sideCollapse').addEventListener('click',()=>{$('app').classList.toggle('sidebar-collapsed');});
async function playerCommand(action) {
  if(busyPlayback)return;busyPlayback=true;try{await api(action);}catch(e){setConnection(e.message);}finally{busyPlayback=false;setTimeout(refresh,800);}
}
$('playCollection').addEventListener('click',()=>{
  if(activePlayableUri){void playSelectedTrack(activePlayableUri);return;}
  if(!activeCollection)return;
  const index=activeCollection.items.findIndex(x=>x.kind==='track');
  if(index<0)return;
  void playSelectedTrack(activeCollection.items[index].uri,activeCollection,index);
});
// Native previous/next use Spotify's active playback queue. Do not reload the
// whole playlist context on each skip (the old helper's playUri was heavier).
async function skipWithinCollection(delta){
  await playerCommand(delta>0?'next':'previous');
}
$('prev').addEventListener('click',()=>skipWithinCollection(-1));
$('toggle').addEventListener('click',()=>playerCommand('toggle'));
$('next').addEventListener('click',()=>skipWithinCollection(1));
async function refresh(){
  if(refreshInFlight||busyPlayback)return null;
  refreshInFlight=true;
  try{
    const state=await api('state');if(!state)return null;
    $('toggle').textContent=state.playing?'Ⅱ':'▶';playing=Boolean(state.playing);
    $('song').textContent=state.track?.name||'Nothing playing';
    $('artist').textContent=state.track?.subtitle||'Spotify Headless • Ubuntu';
    nowArtistUri=artistUriRe.test(state.track?.artistUri||'')?state.track.artistUri:'';
    $('nowOpenArtist').disabled=!nowArtistUri;
    $('nowOpenArtist').title=nowArtistUri?'View '+(state.track?.subtitle||'artist')+' top songs and albums':'Artist information unavailable';
    const artwork=validImage(state.track?.image)||'/spotify-glyph.svg';
    if(lastCover!==artwork){$('cover').src=artwork;lastCover=artwork;}
    if(state.contextUri)currentPlaylistUri=state.contextUri.startsWith('spotify:playlist:')?state.contextUri:'';
    setConnection(DEMO?'Preview mode':'Connected',true);
    return state;
  }catch(e){setConnection(e.message);return null;}
  finally{refreshInFlight=false;}
}
function closePlayer(){if(window.parent&&window.parent!==window) window.parent.postMessage({type:'spotify-touch-close'},'*'); else history.length>1?history.back():void 0;}
$('nowOpenArtist').addEventListener('click',()=>{
  if(nowArtistUri)void navigate('artist',$('artist').textContent||'Artist',{uri:nowArtistUri});
});
$('backDashboard').addEventListener('click',closePlayer);
// Load serially rather than starting multiple authenticated CDP requests at once.
// Use the active playlist when available; otherwise show Liked Songs.
(async function start(){
  const state=await refresh();
  await loadLibrary();
  if(currentPlaylistUri){
    const saved=playlists.find(p=>p.uri===currentPlaylistUri);
    await navigate('playlist',saved?.name||'Current Playlist',{uri:currentPlaylistUri});
  }else await navigate('liked','Liked Songs');
  setInterval(()=>{void refresh();},10000);
})();