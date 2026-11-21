import importlib.util
import json
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
SWITCH = ROOT/'src'/'pi'/'controller'/'switchd.py'
PATCH = ROOT/'src'/'pi'/'session'/'patch_launcher.py'
spec=importlib.util.spec_from_file_location('switchd_v2', SWITCH)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
spec2=importlib.util.spec_from_file_location('launcher_patch_v2', PATCH)
p=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(p)

class Tests(unittest.TestCase):
    def setUp(self):
        with s.LOCK:
            s.STATE.update(mode='mirror',audio_error='',audio_action='pending',viewer_seen=0,viewer_mode='')
        while not s.AUDIO_EVENTS.empty():
            try: s.AUDIO_EVENTS.get_nowait();s.AUDIO_EVENTS.task_done()
            except Exception:break

    def test_magicmirror_uses_ipv6_localhost_everywhere(self):
        # Raspberry Pi OS MagicMirror commonly binds only [::1]:8080.
        # Keep the controller/tunnel at 127.0.0.1; only mirror HTTP needs IPv6.
        files = ('src/pi/kiosk/launch-viewer.sh', 'src/pi/kiosk/electron-kiosk.js')
        for filename in files:
            value = (ROOT / filename).read_text()
            self.assertIn('http://[::1]:8080/', value, filename)
            self.assertNotIn('http://127.0.0.1:8080/', value, filename)

    def test_launcher_preserves_old_path_when_disabled(self):
        original='#!/bin/bash\ncd $(dirname "$0")/..\nnpm run start:wayland\n'
        patched=p.patch_text(original)
        self.assertIn('exec node serveronly',patched)
        self.assertIn('npm run start:wayland',patched)
        self.assertEqual(patched.splitlines()[0], '#!/bin/bash')
        with self.assertRaises(ValueError):p.patch_text(patched)

    def test_modes_queue_audio_and_do_not_call_pm2(self):
        self.assertTrue(s.change_mode('spotify'))
        self.assertEqual(s.STATE['mode'],'spotify')
        self.assertFalse(s.change_mode('spotify'))
        self.assertTrue(s.change_mode('mirror'))
        self.assertEqual(s.STATE['mode'],'mirror')

    def test_http_rejects_non_local_action(self):
        with s.Server(('127.0.0.1',0),s.Handler) as server:
            task=threading.Thread(target=server.serve_forever,daemon=True);task.start()
            addr=f'http://127.0.0.1:{server.server_port}'
            try:
                req=Request(addr+'/enter',method='POST')
                with self.assertRaises(HTTPError) as e:urlopen(req)
                self.assertEqual(e.exception.code,403)
                req=Request(addr+'/enter',method='POST',headers={'X-Spotify-Appliance':'1','Origin':'https://not-local.test'})
                with self.assertRaises(HTTPError) as e:urlopen(req)
                self.assertEqual(e.exception.code,403)
                req=Request(addr+'/enter',method='POST',headers={'X-Spotify-Appliance':'1'})
                with urlopen(req) as r:self.assertEqual(json.load(r)['mode'],'spotify')
                with urlopen(addr+'/health') as r:self.assertEqual(json.load(r)['mode'],'spotify')
                req=Request(addr+'/exit',method='POST',headers={'X-Spotify-Appliance':'1','Origin':'http://127.0.0.1:16181'})
                with urlopen(req) as r:self.assertEqual(json.load(r)['mode'],'mirror')
            finally:server.shutdown();task.join()

    def test_viewer_heartbeat_and_wrapper(self):
        with s.Server(('127.0.0.1',0),s.Handler) as server:
            task=threading.Thread(target=server.serve_forever,daemon=True);task.start()
            addr=f'http://127.0.0.1:{server.server_port}'
            try:
                self.assertIn(b'MIRROR',urlopen(addr+'/player').read())
                req=Request(addr+'/viewer',method='POST',headers={'X-Spotify-Appliance':'1','X-Viewer-Mode':'mirror'})
                with urlopen(req):pass
                with urlopen(addr+'/health') as r:
                    data=json.load(r)
                self.assertTrue(data['viewer_alive'])
                self.assertEqual(data['viewer_mode'],'mirror')
            finally:server.shutdown();task.join()

    def test_audio_worker_latest_desired_mode_wins(self):
        cmds=[]
        def once_command(action):
            cmds.append(action)
            if action=='start':
                with s.LOCK: s.STATE['mode']='mirror'
        with patch.object(s,'audio_command',side_effect=once_command), patch.object(s,'connect_bluetooth',return_value=True), patch.object(s,'disconnect_bluetooth',return_value=None):
            with s.LOCK:s.STATE['mode']='spotify'
            s.AUDIO_EVENTS.put_nowait(1)
            t=threading.Thread(target=s.audio_worker,daemon=True);t.start()
            s.AUDIO_EVENTS.join()
            s.AUDIO_EVENTS.put_nowait(None)
            t.join(timeout=3)
            self.assertFalse(t.is_alive())
        self.assertEqual(cmds[:3],['stop','start','stop'])
        self.assertEqual(s.STATE['audio_action'],'stop')

if __name__=='__main__':unittest.main()