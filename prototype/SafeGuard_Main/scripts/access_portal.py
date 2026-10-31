#!/usr/bin/env python3
"""Independent HTTPS entry point. Never starts, stops, or restarts the controller."""
import argparse
import getpass
import hashlib
import hmac
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit
from navigation_session import atomic_json

COOKIE = 'safeguard_session'
SESSION_SECONDS = 7 * 86400


class Login:
    def __init__(self, record, clock=time.time):
        self.record = record
        self.clock = clock
        self.key = bytes.fromhex(record['signing_key'])
        self.failures = {}
        self.lock = threading.Lock()

    @staticmethod
    def create(password):
        if len(password) < 12:
            raise ValueError('Use at least 12 characters for the portal password')
        salt = secrets.token_hex(16)
        return {'salt': salt, 'password_hash': hashlib.scrypt(password.encode(),
            salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex(), 'signing_key': secrets.token_hex(32)}

    def authenticate(self, password, peer):
        with self.lock:
            now = self.clock()
            self.failures = {k:v for k,v in self.failures.items() if now-v[1]<300}
            attempts, since = self.failures.get(peer, (0, now))
            if attempts >= 10:
                return None
            actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(self.record['salt']), n=16384, r=8, p=1).hex()
            if not hmac.compare_digest(actual, self.record['password_hash']):
                self.failures[peer] = (attempts+1, since)
                return None
            self.failures.pop(peer, None)
            payload = f'{int(now+SESSION_SECONDS)}.{secrets.token_hex(16)}'
            return payload+'.'+hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()

    def valid(self, cookie):
        try:
            parsed = SimpleCookie(cookie)
            value = parsed[COOKIE].value
            expiry, nonce, signature = value.split('.')
            if not self.clock() < int(expiry) <= self.clock()+SESSION_SECONDS+1:
                return False
            return hmac.compare_digest(signature, hmac.new(self.key,
                f'{expiry}.{nonce}'.encode(), hashlib.sha256).hexdigest())
        except (ValueError, KeyError, TypeError):
            return False


LOGIN_HTML = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>SafeGuard 접속</title><style>body{font:18px system-ui;max-width:640px;margin:10vh auto;padding:24px}input,button{font:inherit;padding:12px;margin:8px 0}</style>
<h1>SafeGuard</h1><p>처음 연결할 때 운영 비밀번호를 입력하세요. 이 기기에서 7일 동안 접속을 유지합니다.</p>
<form id="login"><input id="password" type="password" autocomplete="current-password" required placeholder="운영 비밀번호"><button>접속</button></form>
<p id="error"></p><script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.querySelector('#password').value})});if(r.ok)location.href=location.pathname;else document.querySelector('#error').textContent='비밀번호를 확인하세요. 반복 실패하면 5분 뒤 다시 시도하세요.'}catch(e){document.querySelector('#error').textContent='Pi 연결을 확인하세요.'}};</script></html>'''


def handler(login, runtime, authority='safeguard.local:9443', upstream=('127.0.0.1',8080), monitor=None):
    runtime = Path(runtime)
    origin = 'https://'+authority
    portal = Path(__file__).with_name('access_portal.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # Do not log credentials, pairing codes or location information.

        def reply(self, status, content, content_type='application/json; charset=utf-8', cookie=None):
            if not isinstance(content, bytes):
                content = (json.dumps(content, ensure_ascii=False) if not isinstance(content,str) else content).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            if cookie: self.send_header('Set-Cookie', cookie)
            self.end_headers()
            try: self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError): pass

        def guard(self, post=False):
            if self.headers.get_all('Host') != [authority]:
                self.reply(403, {'error':'Unknown host'}); return False
            if post and self.headers.get_all('Origin') != [origin]:
                self.reply(403, {'error':'Origin mismatch'}); return False
            return True

        def authenticated(self):
            if not login.valid(self.headers.get('Cookie','')):
                self.reply(401, {'error':'Login required'}); return False
            return True

        def do_GET(self):
            if not self.guard(): return
            path = urlsplit(self.path).path
            if path in ('/','/dashboard') and not login.valid(self.headers.get('Cookie','')):
                self.reply(200, LOGIN_HTML, 'text/html; charset=utf-8'); return
            if not self.authenticated(): return
            if path == '/': self.reply(200,portal,'text/html; charset=utf-8')
            elif path == '/api/pairing':
                try: value=json.loads((runtime/'navigation_pairing.json').read_text())
                except (OSError,ValueError): value={'available':False}
                self.reply(200,value)
            elif path == '/dashboard':
                if monitor:self.reply(200,Path(__file__).with_name('dashboard.html').read_bytes(),'text/html; charset=utf-8')
                else:self.proxy('GET','/')
            elif path == '/api/state':
                if monitor:self.reply(200,monitor.snapshot())
                else:self.proxy('GET','/api/state')
            else: self.reply(404,{'error':'Not found'})

        def do_POST(self):
            if not self.guard(post=True): return
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:
                self.reply(400,{'error':'Length required'}); return
            try: length=int(self.headers.get('Content-Length','-1'))
            except ValueError: length=-1
            if not 0 <= length <= 4096:
                self.reply(413,{'error':'Request too large'}); return
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                self.reply(415,{'error':'JSON required'}); return
            data=self.rfile.read(length)
            try:
                value=json.loads(data)
                if not isinstance(value,dict): raise ValueError('object required')
            except (ValueError,UnicodeError):
                self.reply(400,{'error':'Invalid JSON'}); return
            if self.path == '/api/login':
                password=value.get('password')
                token=login.authenticate(password,self.client_address[0]) if isinstance(password,str) else None
                if not token: self.reply(403,{'error':'Login failed'}); return
                self.reply(200,{'ok':True},cookie=f'{COOKIE}={token}; Path=/; Max-Age={SESSION_SECONDS}; Secure; HttpOnly; SameSite=Strict'); return
            if not self.authenticated(): return
            if self.path == '/api/control':
                if monitor:self.reply(403,{'ok':False,'error':'Connection check is read-only; hardware control is disabled.'})
                else:self.proxy('POST','/api/control',data)
            elif self.path == '/api/pairing/reset':
                atomic_json(runtime/'navigation_pairing_reset.json',{'request':secrets.token_hex(16)})
                self.reply(202,{'ok':True})
            elif self.path == '/api/logout':
                self.reply(200,{'ok':True},cookie=f'{COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict')
            else: self.reply(404,{'error':'Not found'})

        def proxy(self, method, path, body=None):
            conn=http.client.HTTPConnection(*upstream,timeout=2)
            try:
                conn.request(method,path,body,{'Host':f'127.0.0.1:{upstream[1]}',
                    'Origin':f'http://127.0.0.1:{upstream[1]}','Content-Type':'application/json'})
                response=conn.getresponse();data=response.read(2*1024*1024+1)
                if len(data)>2*1024*1024: raise ValueError('Response too large')
                self.reply(response.status,data,response.getheader('Content-Type','application/json'))
            except (OSError,http.client.HTTPException,ValueError):
                self.reply(503,{'error':'Controller unavailable; connection will retry. No restart requested.'})
            finally: conn.close()
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--init-password',action='store_true')
    parser.add_argument('--port',type=int,default=9443)
    parser.add_argument('--connection-check',action='store_true',help='Phone/weather only; no controller or hardware access')
    args=parser.parse_args();runtime=args.project/'runtime'
    auth=runtime/'portal_auth.json'
    if args.init_password:
        if auth.exists(): parser.error('Credentials already exist; preserve them or rotate explicitly')
        while True:
            try:
                password=getpass.getpass('New portal password (12+ characters): ')
                if len(password)<12:
                    print('Please use at least 12 characters. Try again.',flush=True);continue
                if password != getpass.getpass('Confirm: '):
                    print('Passwords differ. Try again.',flush=True);continue
                atomic_json(auth,Login.create(password))
                print('PORTAL_PASSWORD_READY',flush=True);return
            except EOFError:
                parser.error('Interactive input unavailable. Open this command with SSH -tt.')
    login=Login(json.loads(auth.read_text()))
    monitor=None
    if args.connection_check:
        from connection_status import ConnectionStatus
        monitor=ConnectionStatus(args.project)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(runtime/'navigation_tls/server.pem',runtime/'navigation_tls/server.key')
    class DualStackServer(ThreadingHTTPServer):
        address_family=socket.AF_INET6
        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
            super().server_bind()
    server_type=DualStackServer if socket.has_dualstack_ipv6() else ThreadingHTTPServer
    address='::' if socket.has_dualstack_ipv6() else '0.0.0.0'
    server=server_type((address,args.port),handler(login,runtime,f'safeguard.local:{args.port}',monitor=monitor))
    server.daemon_threads=True
    server.socket=context.wrap_socket(server.socket,server_side=True,do_handshake_on_connect=False)
    if monitor:monitor.start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        if monitor:monitor.close()


if __name__=='__main__': main()
