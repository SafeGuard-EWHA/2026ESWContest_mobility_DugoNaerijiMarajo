"""IPv6 loopback transport + synthetic location; not an actual iPhone test."""
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ipv6_bridge_tested', ROOT/'patch/scripts/navigation_bridge.py')
nav = importlib.util.module_from_spec(spec);spec.loader.exec_module(nav)

class IPv6Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=nav.LocationStore(Path(self.temp.name)/'state.json',pairing_code='12345678')
    def server(self,bootstrap=False,ssl_context=None,prefer_hostname=False):
        server=nav.IPv6BridgeServer(('::1',0),nav.BaseHTTPRequestHandler)
        port=server.server_port
        server.RequestHandlerClass=nav.make_handler(self.store,host='172.20.10.8',hostname='safeguard.local',port=port,
            ca_der=b'certificate',mobile_html=b'PHONE',bootstrap=bootstrap,https_port=8443,prefer_hostname=prefer_hostname)
        self.assertEqual(server.socket.getsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY),1)
        if ssl_context:server.socket=ssl_context.wrap_socket(server.socket,server_side=True,do_handshake_on_connect=False)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def close():server.shutdown();server.server_close();thread.join(3)
        self.addCleanup(close)
        return port
    def request(self,port,path='/',body=None,host=None,origin=None,token=None,tls=None,extra_headers=''):
        host=host or 'safeguard.local:'+str(port)
        payload=json.dumps(body).encode() if body is not None else b''
        headers='Host: '+host+'\r\n'+extra_headers
        if origin is not None:headers+='Origin: '+origin+'\r\n'
        if token:headers+='Authorization: Bearer '+token+'\r\n'
        if body is not None:headers+='Content-Type: application/json\r\nContent-Length: '+str(len(payload))+'\r\n'
        message=(('POST' if body is not None else 'GET')+' '+path+' HTTP/1.1\r\n'+headers+'Connection: close\r\n\r\n').encode()+payload
        with socket.create_connection(('::1',port),timeout=3) as raw:
            transport=tls.wrap_socket(raw,server_hostname='safeguard.local') if tls else raw
            try:
                transport.sendall(message)
                response=http.client.HTTPResponse(transport);response.begin()
                return response.status,response.read()
            finally:
                if tls:transport.close()
    def test_ipv6_bootstrap_keeps_name_in_secure_link(self):
        port=self.server(bootstrap=True)
        status,body=self.request(port)
        self.assertEqual(status,200);self.assertIn(b'https://safeguard.local:8443/',body)
        self.assertNotIn(b'https://172.20.10.8:8443/',body)
        status,body=self.request(port,host='172.20.10.8:'+str(port))
        self.assertEqual(status,200);self.assertIn(b'https://172.20.10.8:8443/',body)
        self.assertEqual(self.request(port,host='evil.local:'+str(port))[0],403)
        self.assertEqual(self.request(port,extra_headers='Host: evil.local\r\n')[0],403)
    def test_demo_numeric_bootstrap_always_links_to_certified_hostname(self):
        port=self.server(bootstrap=True,prefer_hostname=True)
        status,body=self.request(port,host='172.20.10.8:'+str(port))
        self.assertEqual(status,200)
        self.assertIn(b'https://safeguard.local:8443/',body)
        self.assertNotIn(b'https://172.20.10.8:8443/',body)
    def test_named_origin_must_match_host_not_merely_allowlisted(self):
        port=self.server();host='safeguard.local:'+str(port)
        self.assertEqual(self.request(port,'/api/pair',{'code':'12345678'},origin='https://172.20.10.8:'+str(port))[0],403)
        self.assertEqual(self.request(port,'/api/pair',{'code':'12345678'},origin='http://'+host)[0],403)
        self.assertEqual(self.request(port,'/api/pair',{'code':'12345678'},origin='https://'+host)[0],200)
    def test_actual_ipv6_https_with_certificate_and_name_verified(self):
        directory=Path(self.temp.name);key=directory/'key.pem';cert=directory/'cert.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),
            '-days','1','-subj','/CN=safeguard.local','-addext','subjectAltName=DNS:safeguard.local'],
            check=True,capture_output=True,timeout=15)
        server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_context.load_cert_chain(cert,key)
        client_context=ssl.create_default_context(cafile=str(cert))
        port=self.server(ssl_context=server_context);origin='https://safeguard.local:'+str(port)
        self.assertEqual(self.request(port,tls=client_context),(200,b'PHONE'))
        status,body=self.request(port,'/api/pair',{'code':'12345678'},origin=origin,tls=client_context)
        self.assertEqual(status,200);token=json.loads(body)['token']
        sample={'valid':True,'seq':1,'latitude':37.5,'longitude':127.0,'accuracy_m':10,'position_timestamp_ms':time.time()*1000}
        status,body=self.request(port,'/api/location',sample,origin=origin,token=token,tls=client_context)
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['valid'])
        status,body=self.request(port,'/api/location',{'valid':False,'seq':2},origin=origin,token=token,tls=client_context)
        self.assertEqual(status,200);self.assertFalse(json.loads(body)['valid'])
    def test_only_usable_link_local_addresses_of_requested_interface(self):
        entries=[{'ifindex':3,'ifname':'wlan0','addr_info':[
            {'family':'inet6','scope':'link','local':'fe80::abcd'},
            {'family':'inet6','scope':'global','local':'2001:db8::4'},
            {'family':'inet6','scope':'link','local':'fe80::11','tentative':True},
            {'family':'inet6','scope':'link','local':'fe80::12','flags':['dadfailed']}]}]
        result=types.SimpleNamespace(returncode=0,stdout=json.dumps(entries))
        with mock.patch.object(nav.socket,'if_nametoindex',return_value=3),mock.patch.object(nav.subprocess,'run',return_value=result) as run:
            self.assertEqual(nav.link_local_bindings('wlan0'),[('fe80::abcd',3)])
            self.assertEqual(run.call_args.args[0],['ip','-j','-6','address','show','dev','wlan0'])
            result.stdout='[]'
            with self.assertRaisesRegex(ValueError,'No usable'):nav.link_local_bindings('wlan0')
        for name in ('wlan0;touch x','', 'x'*16):
            with self.assertRaises(ValueError):nav.link_local_bindings(name)

if __name__=='__main__':unittest.main()
