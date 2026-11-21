import importlib.util
import json
import threading
import unittest
from pathlib import Path
import os
os.environ['SPOTIFY_BLUETOOTH_MAC'] = 'AA:BB:CC:DD:EE:FF'
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('switchd_v202', ROOT/'src/pi/controller/switchd.py')
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)

class PatchTests(unittest.TestCase):
    def setUp(self):
        with s.LOCK:
            s.STATE.update(mode='mirror',audio_action='pending',audio_error='',bluetooth='idle',bluetooth_error='',viewer_mode='',viewer_seen=0)
        while not s.AUDIO_EVENTS.empty():
            try: s.AUDIO_EVENTS.get_nowait();s.AUDIO_EVENTS.task_done()
            except Exception: break

    def test_bluetooth_sink_parsing_in_audio_only(self):
        dump='''PipeWire 'pipewire-0'
Audio
 ├─ Devices:
 │  48. Built-in Audio
 ├─ Sinks:
 │  * 52. Built-in Audio Digital Stereo (HDMI)
 │    77. bluez_output.AA_BB_CC_DD_EE_FF.1 [vol: 0.6]
 ├─ Sources:
 │    88. bluez_output.AA_BB_CC_DD_EE_FF.monitor
Video
 ├─ Sinks:
 │    33. Bluetooth speaker
'''
        self.assertEqual(s.find_bluetooth_sink(dump),'77')
        self.assertIsNone(s.find_bluetooth_sink('Audio\n ├─ Sinks:\n │ 52. HDMI\n ├─ Sources:\n │ 88. Bluetooth speaker'))

    def test_first_spotify_entry_stops_old_player_before_connection(self):
        actions=[]
        with s.LOCK: s.STATE['mode']='spotify'
        def connect():
            actions.append('connect')
            return True
        with patch.object(s,'audio_command',side_effect=lambda a: actions.append(a)), patch.object(s,'connect_bluetooth',side_effect=connect),patch.object(s,'disconnect_bluetooth',side_effect=lambda: actions.append('disconnect')):
            s.AUDIO_EVENTS.put_nowait(1)
            thread=threading.Thread(target=s.audio_worker,daemon=True);thread.start()
            s.AUDIO_EVENTS.join()
            s.AUDIO_EVENTS.put_nowait(None);thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(actions,['stop','connect','start'])

    def test_mirror_entry_stops_audio_then_disconnects(self):
        actions=[]
        with patch.object(s,'audio_command',side_effect=lambda a: actions.append(a)),patch.object(s,'disconnect_bluetooth',side_effect=lambda: actions.append('disconnect')):
            s.AUDIO_EVENTS.put_nowait(1)
            thread=threading.Thread(target=s.audio_worker,daemon=True);thread.start()
            s.AUDIO_EVENTS.join()
            s.AUDIO_EVENTS.put_nowait(None);thread.join(2)
        self.assertEqual(actions,['stop','disconnect'])

    def test_fast_exit_during_bt_connect_never_starts_mp3(self):
        actions=[]
        with s.LOCK:s.STATE['mode']='spotify'
        def connect_then_exit():
            with s.LOCK:s.STATE['mode']='mirror'
            return True
        with patch.object(s,'audio_command',side_effect=lambda a:actions.append(a)),patch.object(s,'connect_bluetooth',side_effect=connect_then_exit),patch.object(s,'disconnect_bluetooth',side_effect=lambda:actions.append('disconnect')):
            s.AUDIO_EVENTS.put_nowait(1)
            thread=threading.Thread(target=s.audio_worker,daemon=True);thread.start()
            s.AUDIO_EVENTS.join();s.AUDIO_EVENTS.put_nowait(None);thread.join(2)
        self.assertEqual(actions,['stop','stop','disconnect'])

    def test_bluetooth_fails_closed_and_reports_error(self):
        actions=[]
        with s.LOCK:s.STATE['mode']='spotify';s.STATE['bluetooth_error']='speaker not ready'
        with patch.object(s,'audio_command',side_effect=lambda a:actions.append(a)),patch.object(s,'connect_bluetooth',return_value=False):
            s.AUDIO_EVENTS.put_nowait(1)
            thread=threading.Thread(target=s.audio_worker,daemon=True);thread.start()
            s.AUDIO_EVENTS.join();s.AUDIO_EVENTS.put_nowait(None);thread.join(2)
        self.assertEqual(actions,['stop'])
        self.assertIn('speaker not ready',s.STATE['audio_error'])

    def test_no_duplicate_exit_button_existing_iframe_message(self):
        self.assertIn(b'spotify-touch-close',s.PLAYER_HTML)
        self.assertNotIn(b'<button id="mirror"',s.PLAYER_HTML)
        self.assertNotIn(b'btn.disabled',s.PLAYER_HTML)
        self.assertIn(b'<iframe id="spotify"',s.PLAYER_HTML)

    def test_http_wrapper_and_health_report_bluetooth(self):
        with s.Server(('127.0.0.1',0),s.Handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            host=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(host+'/player') as r:self.assertIn(b'spotify-touch-close',r.read())
                with urlopen(host+'/health') as r:self.assertIn('bluetooth',json.load(r))
                req=Request(host+'/enter',method='POST',headers={'X-Spotify-Appliance':'1'})
                with urlopen(req) as r:self.assertEqual(json.load(r)['mode'],'spotify')
            finally:
                server.shutdown();thread.join()

    def test_button_is_larger_no_ring_no_overlay(self):
        css=(ROOT/'src/pi/magicmirror/MMM-SpotifyTouch.css').read_text()
        js=(ROOT/'src/pi/magicmirror/MMM-SpotifyTouch.js').read_text()
        svg=(ROOT/'src/pi/magicmirror/spotify-glyph.svg').read_text()
        self.assertIn('border-radius:0',css)
        self.assertIn('background:transparent',css)
        self.assertIn('r.height * 0.644',js)
        self.assertIn('spotify-glyph.svg',js)
        self.assertIn('stroke="#ffffff"',svg)
        self.assertNotIn('<circle',svg)

    def test_installer_does_not_restart_magicmirror_or_edit_ubuntu(self):
        sh=(ROOT/'src/pi/session/minimal-session.sh').read_text()
        self.assertNotIn('pm2 restart',sh)
        self.assertNotIn('podman',sh)
        self.assertIn('Minimal kiosk session',sh)

if __name__=='__main__':unittest.main()