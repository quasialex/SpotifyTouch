'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.join(__dirname,'../src/ubuntu/web');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const js=fs.readFileSync(path.join(root,'ui.js'),'utf8');
const css=fs.readFileSync(path.join(root,'ui.css'),'utf8');
assert.match(html,/id="nowOpenArtist"/);
assert.match(css,/\.top-btn\.dashboard\{height:43px;width:70px/);
assert.match(js,/queryArtistOverview|artist/); // The request is on demand in the Ubuntu CDP helper.
assert.doesNotMatch(html,/searchForm|showKeyboard|id="keyboard"/);
assert.match(js,/window.parent.postMessage\(\{type:'spotify-touch-close'\}/);
assert.match(html,/v=22artist/);
console.log('Artist touch layout tests passed');