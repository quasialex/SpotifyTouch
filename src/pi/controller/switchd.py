#!/usr/bin/env python3
"""Tiny local controller for a *single*, persistent MagicMirror/Spotify viewer.

The MagicMirror node server is not restarted when changing pages.
Only on-demand mpv and the paired Logitech Bluetooth connection are managed.
"""
import json
import os
import queue
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORT = int(os.environ.get('SPOTIFY_SWITCH_PORT','16181'))
AUDIO_UNIT = 'spotify-touch-audio.service'
BT_MAC = os.environ.get('SPOTIFY_BLUETOOTH_MAC','').strip().upper()  # Optional: paired speaker
BT_NODE = 'bluez_output.' + BT_MAC.replace(':', '_') if BT_MAC else ''
LOCK = threading.RLock()
STATE = {'mode': ('spotify' if os.environ.get('SPOTIFY_KIOSK_MODE') == 'standalone' else 'mirror'), 'audio_error': '', 'audio_action': 'pending',
         'last_switch_ms': None, 'viewer_seen': 0.0, 'viewer_mode': '',
         'bluetooth': 'idle', 'bluetooth_error': ''}
AUDIO_EVENTS = queue.Queue(maxsize=1)


def audio_command(action):
    p = subprocess.run(['systemctl', '--user', action, AUDIO_UNIT],
                       capture_output=True, text=True, timeout=20)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip()[-500:] or f'{action} failed')


def run_cmd(argv, timeout=8):
    """Run a bounded local command; no shell and no permanent poller."""
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip()[-280:] or f'{argv[0]} failed')
    return p.stdout


def bluetooth_connected():
    return bool(BT_MAC) and 'Connected: yes' in run_cmd(['bluetoothctl', 'info', BT_MAC], timeout=4)


def find_bluetooth_sink(text):
    """Extract only an Audio/Sinks ID, never a Bluetooth source or monitor."""
    in_audio = False
    in_sinks = False
    for line in text.splitlines():
        if line.strip() == 'Audio':
            in_audio = True
        elif line.strip() == 'Video':
            in_audio = False
            in_sinks = False
        if not in_audio:
            continue
        if 'Sinks:' in line:
            in_sinks = True
            continue
        if in_sinks and any(mark in line for mark in ('Sources:', 'Filters:', 'Streams:', 'Devices:')):
            in_sinks = False
        if BT_NODE and in_sinks and BT_NODE.lower() in line.lower():
            match = re.search(r'(?<!\d)(\d+)\.', line)
            if match:
                return match.group(1)
    return None


def current_mode_is(mode):
    with LOCK:
        return STATE['mode'] == mode


def connect_bluetooth():
    """Connect on Spotify entry only; select the sink before launching mpv.

    Two bounded attempts when the speaker is waking up; no background daemon.
    """
    with LOCK:
        STATE['bluetooth'] = 'connecting'
        STATE['bluetooth_error'] = ''
    if not BT_MAC:
        with LOCK: STATE['bluetooth'] = 'not-configured'
        return True  # Local default sink (e.g. HDMI) when Bluetooth is disabled.
    last_error = 'Configured Bluetooth speaker is unavailable'
    for attempt in range(2):
        if not current_mode_is('spotify'):
            return False
        try:
            if not bluetooth_connected():
                run_cmd(['bluetoothctl', 'connect', BT_MAC], timeout=10)
            for _ in range(10):
                if not current_mode_is('spotify'):
                    return False
                sink = find_bluetooth_sink(run_cmd(['wpctl','status','-n'],timeout=4))
                if sink:
                    run_cmd(['wpctl','set-default',sink],timeout=4)
                    run_cmd(['wpctl','set-volume','-l','1.0',sink,'1.0'],timeout=4)
                    with LOCK:
                        STATE['bluetooth'] = 'connected'
                        STATE['bluetooth_error'] = ''
                    return True
                time.sleep(0.5)
            last_error = 'Bluetooth connected but no PipeWire audio sink appeared'
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            last_error = str(exc)
        if attempt == 0 and current_mode_is('spotify'):
            time.sleep(1)
    with LOCK:
        STATE['bluetooth'] = 'unavailable'
        STATE['bluetooth_error'] = last_error
    return False


def disconnect_bluetooth():
    """Release the Z207 only; keep BlueZ / PipeWire running and reusable."""
    if not BT_MAC: return
    try:
        if bluetooth_connected():
            run_cmd(['bluetoothctl','disconnect',BT_MAC],timeout=6)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        with LOCK:
            STATE['bluetooth_error'] = str(exc)
    with LOCK:
        STATE['bluetooth'] = 'disconnected'


def audio_worker():
    """Serialized, mode-driven audio lifecycle; latest requested mode wins.

    On every Spotify entry, stop an old consumer, connect the BT speaker,
    select its PipeWire sink, then create a *fresh* mpv process. On exit,
    stop mpv before disconnecting the speaker. Don't block the UI switch.
    """
    while True:
        token = AUDIO_EVENTS.get()
        if token is None:
            AUDIO_EVENTS.task_done()
            return
        while True:
            with LOCK:
                wanted = STATE['mode']
            error = ''
            action = 'start' if wanted == 'spotify' else 'stop'
            try:
                audio_command('stop')
                if wanted == 'spotify' and current_mode_is('spotify'):
                    if connect_bluetooth() and current_mode_is('spotify'):
                        audio_command('start')  # fresh consumer, flushes old stream
                    elif current_mode_is('spotify'):
                        with LOCK:
                            error = STATE['bluetooth_error'] or 'Bluetooth unavailable; audio not started'
                elif wanted == 'mirror' and current_mode_is('mirror'):
                    disconnect_bluetooth()
            except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
                error = str(exc)
            with LOCK:
                STATE['audio_action'] = ('blocked' if wanted == 'spotify' and error else action)
                STATE['audio_error'] = error
                if STATE['mode'] == wanted:
                    break
        AUDIO_EVENTS.task_done()


def wake_audio():
    try:
        AUDIO_EVENTS.put_nowait(1)
    except queue.Full:
        pass


def change_mode(target):
    if os.environ.get('SPOTIFY_KIOSK_MODE') == 'standalone' and target == 'mirror':
        return False
    if target not in ('mirror', 'spotify'):
        raise ValueError('Bad mode')
    with LOCK:
        if STATE['mode'] == target:
            return False
        STATE['mode'] = target
        STATE['last_switch_ms'] = int(time.monotonic() * 1000)
        STATE['audio_action'] = 'pending'
    wake_audio()
    return True


PLAYER_HTML = r'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Spotify Touch</title><style>
html,body{margin:0;height:100%;overflow:hidden;background:#0b1110;color:#fff;font-family:system-ui,Arial,sans-serif}
#spotify{position:absolute;inset:0;width:100%;height:100%;border:0}
#error{position:absolute;left:10px;bottom:8px;z-index:200;padding:8px;background:#4c2222;border-radius:6px;display:none}
</style></head><body>
<iframe id="spotify" src="http://127.0.0.1:16080/" title="Spotify Touch"></iframe>
<div id="error" role="alert"></div>
<script>
// Spotify Touch already renders its own MIRROR button. Its click
// sends spotify-touch-close to the parent; do not draw a second overlay.
let exiting=false;
async function exit(){
  if(exiting)return;
  exiting=true;
  try {
    const r=await fetch('/exit',{method:'POST',headers:{'X-Spotify-Appliance':'1'}});
    if(!r.ok)throw Error('HTTP '+r.status);
  } catch(e) {
    const el=document.getElementById('error');
    el.textContent='Return failed: '+e.message;
    el.style.display='block';exiting=false;
  }
}
window.addEventListener('message',e=>{
 if(e.origin==='http://127.0.0.1:16080' &&
    e.source===document.getElementById('spotify').contentWindow &&
    e.data && e.data.type==='spotify-touch-close')exit();
});
</script></body></html>'''.replace('src="http://127.0.0.1:16080/"', 'src="http://127.0.0.1:%d/%s"' % (int(os.environ.get('SPOTIFY_CONTROL_PORT','16080')), '?standalone=1' if os.environ.get('SPOTIFY_KIOSK_MODE') == 'standalone' else '')).replace("e.origin==='http://127.0.0.1:16080'", "e.origin==='http://127.0.0.1:%d'" % int(os.environ.get('SPOTIFY_CONTROL_PORT','16080'))).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def reply(self, payload, status=200):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health':
            with LOCK:
                if self.headers.get('X-Spotify-Viewer') == '1':
                    STATE['viewer_seen'] = time.monotonic()
                result = {'ok': True, 'mode': STATE['mode'], 'audio_action': STATE['audio_action'],
                          'audio_error': STATE['audio_error'], 'viewer_alive':
                          bool(STATE['viewer_seen'] and time.monotonic() - STATE['viewer_seen'] < 4),
                          'viewer_mode': STATE['viewer_mode'],
                          'bluetooth': STATE['bluetooth'], 'bluetooth_error': STATE['bluetooth_error']}
            return self.reply(result)
        if path == '/player':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(PLAYER_HTML)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            return self.wfile.write(PLAYER_HTML)
        return self.reply({'error': 'Not found'}, 404)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ('/enter', '/exit', '/viewer'):
            return self.reply({'error': 'Not found'}, 404)
        if self.headers.get('X-Spotify-Appliance') != '1':
            return self.reply({'error': 'Missing action header'}, 403)
        if self.headers.get('Origin', '') not in ('', 'http://127.0.0.1:16181'):
            return self.reply({'error': 'Untrusted Origin'}, 403)
        if path == '/viewer':
            with LOCK:
                STATE['viewer_seen'] = time.monotonic()
                STATE['viewer_mode'] = self.headers.get('X-Viewer-Mode', '')[:16]
            return self.reply({'ok': True})
        new_mode = 'spotify' if path == '/enter' else 'mirror'
        changed = change_mode(new_mode)
        return self.reply({'ok': True, 'mode': new_mode, 'changed': changed}, 202)

    def log_message(self, fmt, *args):
        if self.path not in ('/health', '/viewer'):
            print('%s %s' % (self.command, self.path), flush=True)


class Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    # Don't inherit a stale Spotify state after a crash or reboot. Explicitly
    # reconcile the audio unit back to stopped during initialisation.
    threading.Thread(target=audio_worker, daemon=True).start()
    wake_audio()
    with Server(('127.0.0.1', PORT), Handler) as server:
        print('Spotify Touch kiosk controller listening on 127.0.0.1:%d' % PORT, flush=True)
        server.serve_forever(poll_interval=.5)


if __name__ == '__main__':
    main()