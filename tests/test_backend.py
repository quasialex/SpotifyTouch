"""v2.2 Classic regression tests against real HTTP routing and mocked CDP calls."""
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('spotify22server',ROOT/'src'/'ubuntu'/'server.py')
backend=importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),backend.Handler)
        cls.url='http://127.0.0.1:%d'%cls.server.server_port
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.worker.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def get(self,p):
        with urlopen(self.url+p,timeout=3) as r:return r.status,json.load(r)
    def post(self,x):
        req=Request(self.url+'/api',data=json.dumps(x).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=3) as r:return r.status,json.load(r)
    def test_search_and_home_removed(self):
        for action in ('search','home','recent','home_v24','searchDesktop'):
            with self.assertRaises(HTTPError) as cm:self.get('/api?action='+action)
            self.assertEqual(cm.exception.code,400)
        with self.assertRaises(HTTPError) as cm:self.post({'action':'search','query':'Polyphia'})
        self.assertEqual(cm.exception.code,400)
    def test_main_actions(self):
        def fake(req):return {'ok':True,'data':req}
        with patch.object(backend,'call',side_effect=fake):
            self.assertEqual(self.get('/api?action=library')[1]['data']['action'],'library')
            self.assertEqual(self.get('/api?action=liked')[1]['data']['action'],'liked')
            self.assertEqual(self.get('/api?action=state')[1]['data']['action'],'state')
            self.assertEqual(self.get('/api?action=artist&uri=spotify:artist:abc123')[1]['data']['action'],'artist')
            self.assertEqual(self.get('/api?action=album&uri=spotify:album:abc123')[1]['data']['action'],'album')
            _,obj=self.post({'action':'play','uri':'spotify:track:abc123','contextUri':'spotify:playlist:xyz789','index':8})
            self.assertEqual(obj['data']['index'],8)
            self.assertEqual(obj['data']['contextUri'],'spotify:playlist:xyz789')
            _,album=self.post({'action':'play','uri':'spotify:track:abc123','contextUri':'spotify:album:xyz789','index':2})
            self.assertEqual(album['data']['contextUri'],'spotify:album:xyz789')
            for action in ('toggle','next','previous'):
                self.assertEqual(self.post({'action':action})[1]['data']['action'],action)
    def test_reject_invalid_play(self):
        with self.assertRaises(HTTPError) as cm:self.post({'action':'play','uri':'file:///bad'})
        self.assertEqual(cm.exception.code,400)
        with self.assertRaises(HTTPError) as cm:self.post({'action':'play','uri':'spotify:track:abc','contextUri':'spotify:artist:abc'})
        self.assertEqual(cm.exception.code,400)

if __name__=='__main__':unittest.main(verbosity=2)