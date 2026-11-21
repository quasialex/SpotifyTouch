#!/usr/bin/env python3
"""Localhost-only Spotify Touch HTTP API. Spotify session/controls remain in Podman."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import base64, json, os, subprocess, sys
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_ROOT = os.environ.get('SPOTIFY_WEB_ROOT', os.path.join(HERE,'web'))
ALLOWED_GET = {'health','state','library','liked','playlist','artist','album'}
ALLOWED_POST = {'play','pause','resume','toggle','next','previous'}


def call(req):
    blob = base64.b64encode(json.dumps(req, ensure_ascii=False, separators=(',',':')).encode()).decode()
    cmd = ['podman','exec',os.environ.get('SPOTIFY_CONTAINER_NAME','spotify-headless'), 'node',os.environ.get('SPOTIFY_BRIDGE_PATH','/data/spotify-touch-v2/cdp-helper.js'),blob]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=18)
        if proc.returncode != 0:
            return {'ok':False,'error':('Container bridge failed: '+proc.stderr.strip())[:250]}
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        return {'ok':False,'error':'Spotify bridge timed out'}
    except (IndexError,ValueError) as ex:
        return {'ok':False,'error':'Could not read the container response: '+str(ex)}
    except Exception as ex:
        return {'ok':False,'error':str(ex)}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args, directory=WEB_ROOT,**kwargs)

    def json_response(self,obj,code=200):
        data=json.dumps(obj,ensure_ascii=False).encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/api':
            args=parse_qs(u.query)
            action=args.get('action',[''])[0]
            if action not in ALLOWED_GET:
                return self.json_response({'ok':False,'error':'Unknown action'},400)
            req={'action':action,'query':args.get('query',[''])[0][:120], 'uri':args.get('uri',[''])[0][:140], 'name':args.get('name',[''])[0][:120]}
            return self.json_response(call(req))
        if u.path not in ('/','/index.html','/spotify-glyph.svg','/ui.css','/ui.js'):
            self.send_error(404)
            return
        self.path='/index.html' if u.path=='/' else u.path
        return super().do_GET()

    def do_POST(self):
        if self.path!='/api':return self.json_response({'ok':False,'error':'Not found'},404)
        length=int(self.headers.get('Content-Length','0') or '0')
        if length<1 or length>2000:return self.json_response({'ok':False,'error':'Bad input size'},400)
        try: obj=json.loads(self.rfile.read(length))
        except Exception:return self.json_response({'ok':False,'error':'Invalid JSON'},400)
        if not isinstance(obj,dict) or obj.get('action') not in ALLOWED_POST:
            return self.json_response({'ok':False,'error':'Unknown command'},400)
        req={'action':obj['action']}
        if req['action']=='play':
            req['uri']=str(obj.get('uri',''))[:100]
            context_uri=str(obj.get('contextUri',''))[:100]
            if context_uri:
                import re
                if not re.fullmatch(r'spotify:(?:playlist|album):[A-Za-z0-9]+|spotify:collection:tracks', context_uri):
                    return self.json_response({'ok':False,'error':'Invalid playback context'},400)
                req['contextUri']=context_uri
                index=obj.get('index')
                if isinstance(index,int) and not isinstance(index,bool) and 0 <= index <= 9999:
                    req['index']=index
            if not req['uri'].startswith('spotify:'):
                return self.json_response({'ok':False,'error':'Invalid Spotify URI'},400)
        return self.json_response(call(req))

    def log_message(self, fmt, *args):
        if self.path.startswith('/api'):
            super().log_message(fmt,*args)

if __name__=='__main__':
    address=('127.0.0.1', int(os.environ.get('SPOTIFY_TOUCH_PORT','16080')))
    print(f'Spotify Touch listening on http://{address[0]}:{address[1]}/',flush=True)
    ThreadingHTTPServer(address,Handler).serve_forever()