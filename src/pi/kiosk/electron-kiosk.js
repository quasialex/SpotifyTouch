/* Persistent, single-window MagicMirror / Spotify Touch kiosk for Pi Zero 2 W.
 * This script never starts or stops MagicMirror, Spotify Headless or mpv.
 */
'use strict';
const { app, BrowserWindow, Menu } = require('electron');
const http = require('node:http');
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');

const BASE = 'http://127.0.0.1:' + (process.env.SPOTIFY_SWITCH_PORT || '16181');
const MIRROR_URL = process.env.MAGICMIRROR_URL || 'http://[::1]:8080/';
const SPOTIFY_URL = BASE + '/player';
const profile = path.join(os.homedir(), '.cache', 'spotify-appliance-v2-kiosk');
fs.mkdirSync(profile, { recursive: true });
app.setPath('userData', profile);
app.commandLine.appendSwitch('ozone-platform', 'wayland');
app.commandLine.appendSwitch('disable-background-networking');
Menu.setApplicationMenu(null);
let windowRef;
let currentMode = null;
let loadingMode = null;
let pendingPoll = false;
let lastLoadedAt = 0;

function request(pathname, method='GET', extra={}) {
  return new Promise((resolve, reject) => {
    const req = http.request(BASE + pathname, {method, timeout: 2000, headers: extra}, response => {
      let body = '';
      response.on('data', chunk => {if(body.length<8192)body+=chunk;});
      response.on('end', () => {
        if(response.statusCode !== 200) return reject(new Error(`controller HTTP ${response.statusCode}`));
        try {resolve(JSON.parse(body));} catch(e) {reject(e);}
      });
    });
    req.on('timeout', () => req.destroy(new Error('controller timeout')));
    req.on('error', reject);
    req.end();
  });
}

async function navigate(mode) {
  if (!windowRef || windowRef.isDestroyed()) return;
  if (!['mirror','spotify'].includes(mode)) return;
  if (currentMode === mode || loadingMode === mode) return;
  loadingMode = mode;
  const url = mode==='spotify' ? SPOTIFY_URL : MIRROR_URL;
  try {
    await windowRef.loadURL(url);
    currentMode = mode;
    lastLoadedAt = Date.now();
    console.log('Loaded', mode, new Date().toISOString());
    request('/viewer', 'POST', {'X-Spotify-Appliance':'1','X-Viewer-Mode':mode}).catch(()=>{});
  } catch (error) {
    console.error('View load failed for',mode,error.message);
    currentMode = null; // try again on next poll
  } finally { loadingMode = null; }
}

async function poll() {
  if (pendingPoll || !windowRef || windowRef.isDestroyed()) return;
  pendingPoll = true;
  try {
    const health = await request('/health', 'GET', {'X-Spotify-Viewer':'1'});
    if(health.ok && ['mirror','spotify'].includes(health.mode)) {
      if (health.mode !== currentMode && health.mode !== loadingMode) await navigate(health.mode);
    }
  } catch (e) {
    if(Date.now()-lastLoadedAt > 5000) console.error('Controller unavailable:',e.message);
  } finally { pendingPoll = false; }
}

app.on('ready', () => {
  windowRef = new BrowserWindow({
    width: 800, height: 480, fullscreen: true, frame: false,
    show: false, autoHideMenuBar: true, backgroundColor: '#050808',
    webPreferences: {nodeIntegration:false, contextIsolation:true, sandbox:true}
  });
  windowRef.webContents.setWindowOpenHandler(() => ({action:'deny'}));
  windowRef.webContents.on('will-navigate', (event, url) => {
    if (url !== MIRROR_URL && url !== SPOTIFY_URL) event.preventDefault();
  });
  windowRef.once('ready-to-show', () => {windowRef.show();windowRef.setFullScreen(true);});
  setTimeout(() => {if(windowRef && !windowRef.isDestroyed() && !windowRef.isVisible())windowRef.show();},5000);
  windowRef.on('closed', () => {windowRef=null;});
  setInterval(poll, 1000);
  poll();
});
app.on('window-all-closed', () => app.quit());