#!/usr/bin/env python3
"""Local HTTPS receiver for a foreground iPhone navigation demonstration.

No actuator/control endpoints. Phone geolocation is OS-provided location, not a
claim that a raw GNSS fix was acquired. Weather and location freshness are
validated separately by the main-program adapter.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import os
import plistlib
from pathlib import Path
import secrets
import re
import socket
import subprocess
import ssl
import sys
import threading
import time

MAX_REQUEST_BYTES = 4096
MAX_SOURCE_AGE_S = 15.0
FUTURE_TOLERANCE_S = 5.0


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out
    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite number")
        return parsed
    def constant(value):
        raise ValueError("non-finite number")
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                        parse_float=number, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds")


class BridgeError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class LocationStore:
    """One pairing per receiver run; monotonic sequence and original phone time."""
    def __init__(self, path, *, max_accuracy_m=200.0, clock=time.monotonic,
                 wall_clock=time.time, pairing_code=None):
        if not finite(max_accuracy_m) or not 0 < max_accuracy_m <= 10000:
            raise ValueError("max_accuracy_m must be > 0 and <= 10000")
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError("state file may not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_accuracy_m = float(max_accuracy_m)
        self.clock, self.wall_clock = clock, wall_clock
        self.lock = threading.RLock()
        self.receiver_session = secrets.token_hex(16)
        self.pairing_code = pairing_code or f"{secrets.randbelow(100000000):08d}"
        if len(self.pairing_code) != 8 or not self.pairing_code.isascii() or not self.pairing_code.isdigit():
            raise ValueError("pairing code must contain eight ASCII digits")
        self.pairing_deadline = self.clock() + 600
        self.pair_attempts = 0
        self.token = None
        self.closed = False
        self.last_seq = 0
        self.last_position_ms = None
        self.last_sample_age = None
        self.last_sample_mono = None
        self.last_error = None
        self.accepted_count = 0
        self.state = {}
        self.invalidate("receiver_started", seq=0)

    def _write(self, state):
        temporary = self.path.with_name(self.path.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.state = state

    def _base(self, seq):
        wall, mono = self.wall_clock(), self.clock()
        if not finite(wall) or wall <= 0 or not finite(mono) or mono < 0:
            raise BridgeError(503, "Pi clock is invalid")
        return {"schema_version": 1, "source": "IPHONE_NAVIGATION",
                "receiver_session": self.receiver_session, "seq": seq,
                "received_wall_s": wall, "received_utc": utc(wall),
                "rx_monotonic_s": mono}

    def invalidate(self, status, *, seq=None):
        with self.lock:
            state = self._base(self.last_seq if seq is None else seq)
            state.update(valid=False, latitude=None, longitude=None, accuracy_m=None,
                         position_timestamp_ms=None, source_age_at_receive_s=None,
                         status=str(status)[:160])
            self._write(state)
            return dict(state)

    def pair(self, payload):
        with self.lock:
            if self.closed:
                raise BridgeError(503, "Receiver stopped")
            if self.token is not None:
                raise BridgeError(409, "Already paired. Restart receiver to pair another phone.")
            if self.clock() >= self.pairing_deadline:
                raise BridgeError(403, "Pairing code expired. Restart receiver.")
            if self.pair_attempts >= 10:
                raise BridgeError(429, "Pairing locked. Restart receiver.")
            self.pair_attempts += 1
            code = payload.get("code")
            if not isinstance(code, str) or not hmac.compare_digest(code.encode(), self.pairing_code.encode()):
                raise BridgeError(403, "Incorrect pairing code")
            self.token = secrets.token_urlsafe(32)
            self.pairing_code = ""  # Code cannot authorize a second client.
            return {"token": self.token, "receiver_session": self.receiver_session,
                    "last_seq": self.last_seq, "max_accuracy_m": self.max_accuracy_m}

    def authorized(self, authorization):
        with self.lock:
            return (not self.closed and isinstance(authorization, str) and self.token is not None and
                    hmac.compare_digest(authorization.encode(), ("Bearer " + self.token).encode()))

    def accept(self, payload):
        with self.lock:
            if self.closed:
                raise BridgeError(503, "Receiver stopped")
            seq = payload.get("seq")
            if type(seq) is not int or not self.last_seq < seq <= 9007199254740991:
                raise BridgeError(409, "Sequence must increase; refresh status before retry")
            if type(payload.get("valid")) is not bool:
                raise BridgeError(400, "valid must be boolean")
            if payload["valid"] is False:
                self.last_seq = seq
                self.last_error = None
                return self.invalidate("phone_stopped_or_unavailable")
            lat, lon, accuracy, stamp = (payload.get("latitude"), payload.get("longitude"),
                                         payload.get("accuracy_m"), payload.get("position_timestamp_ms"))
            if not finite(lat) or not -90 <= lat <= 90 or not finite(lon) or not -180 <= lon <= 180:
                raise BridgeError(400, "Latitude/longitude invalid")
            if not finite(accuracy) or not 0 <= accuracy <= self.max_accuracy_m:
                raise BridgeError(422, "Location accuracy is insufficient")
            if not finite(stamp) or stamp <= 0:
                raise BridgeError(400, "Position timestamp invalid")
            state = self._base(seq)
            source_age = state["received_wall_s"] - stamp / 1000
            if stamp == self.last_position_ms and self.last_sample_mono is not None:
                if state["rx_monotonic_s"] < self.last_sample_mono:
                    raise BridgeError(503, "Pi monotonic clock regressed")
                source_age = max(source_age, self.last_sample_age + state["rx_monotonic_s"] - self.last_sample_mono)
            if source_age >= MAX_SOURCE_AGE_S:
                raise BridgeError(422, "Phone location is older than 15 seconds")
            if source_age < -FUTURE_TOLERANCE_S:
                raise BridgeError(422, "Phone time is ahead of Pi; check automatic date/time")
            if self.last_position_ms is not None and stamp < self.last_position_ms:
                raise BridgeError(409, "Position timestamp regressed")
            state.update(valid=True, latitude=float(lat), longitude=float(lon),
                         accuracy_m=float(accuracy), position_timestamp_ms=float(stamp),
                         source_age_at_receive_s=max(0.0, source_age), status="phone_location_received")
            self._write(state)
            self.last_seq, self.last_position_ms = seq, stamp
            self.last_sample_age, self.last_sample_mono = max(0.0, source_age), state["rx_monotonic_s"]
            self.accepted_count += 1
            self.last_error = None
            return dict(state)

    def close(self):
        with self.lock:
            self.closed = True
            self.invalidate("receiver_stopped")

    def status(self):
        with self.lock:
            state = dict(self.state)
            if state.get("valid"):
                mono, wall = self.clock(), self.wall_clock()
                elapsed = mono - state["rx_monotonic_s"]
                age = max(wall - state["position_timestamp_ms"] / 1000,
                          state["source_age_at_receive_s"] + elapsed)
                state["age_s"] = max(0.0, age)
                if elapsed < 0 or age < -FUTURE_TOLERANCE_S or age >= MAX_SOURCE_AGE_S:
                    state.update(valid=False, status="phone_location_expired")
            return {"location": state, "last_seq": self.last_seq,
                    "accepted_count": self.accepted_count, "last_error": self.last_error,
                    "max_accuracy_m": self.max_accuracy_m}


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 8

    def handle_error(self, request, client_address):
        error = sys.exc_info()[1]
        if isinstance(error, ssl.SSLError):
            print('[TLS] Client handshake failed (' + str(error.reason) +
                  '). Check certificate trust on that client; receiver is still running.', flush=True)
        elif isinstance(error, (ConnectionError, TimeoutError)):
            print('[NETWORK] Client connection ended; receiver is still running.', flush=True)
        else:
            super().handle_error(request, client_address)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


class IPv6BridgeServer(BridgeServer):
    address_family = socket.AF_INET6

    def verify_request(self, request, client_address):
        peer = ipaddress.IPv6Address(client_address[0].split("%")[0])
        local = ipaddress.IPv6Address(self.server_address[0].split("%")[0])
        if local.is_loopback:
            return peer.is_loopback
        if local.is_link_local:
            return peer.is_link_local
        return any(peer in network for network in getattr(self, "allowed_peer_networks", ()))

    def server_bind(self):
        # This socket must never claim IPv4 or listen on a wildcard interface.
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()


def link_local_bindings(interface):
    """Read existing, usable link-local addresses; never modify networking."""
    if not isinstance(interface, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", interface):
        raise ValueError("IPv6 interface name is invalid")
    scope_id = socket.if_nametoindex(interface)
    result = subprocess.run(["ip", "-j", "-6", "address", "show", "dev", interface],
                            capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        raise ValueError("Cannot read IPv6 addresses on " + interface)
    try:
        items = json.loads(result.stdout)
        addresses = set()
        for item in items:
            if item.get("ifname") != interface or item.get("ifindex") != scope_id:
                continue
            for entry in item.get("addr_info", []):
                if entry.get("family") != "inet6" or entry.get("scope") != "link":
                    continue
                flags = entry.get("flags", [])
                if entry.get("tentative") or entry.get("dadfailed") or any(x in flags for x in ("tentative", "dadfailed")):
                    continue
                address = ipaddress.IPv6Address(entry["local"])
                if address.is_link_local and not address.is_multicast:
                    addresses.add(str(address))
        if not addresses:
            raise ValueError("No usable link-local IPv6 address on " + interface + ". Enable IPv6 on that interface first.")
        return [(address, scope_id) for address in sorted(addresses)]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Unexpected ip address output") from exc


def wlan_ipv6_bindings(interface):
    # Keep the original interface-name validation and link-local path.
    local = link_local_bindings(interface)
    result = subprocess.run(["ip", "-j", "-6", "address", "show", "dev", interface],
                            capture_output=True, text=True, timeout=5, check=True)
    bindings = [(address, scope, ()) for address, scope in local]
    for item in json.loads(result.stdout):
        if item.get("ifname") != interface or item.get("ifindex") != socket.if_nametoindex(interface):
            continue
        for entry in item.get("addr_info", []):
            if entry.get("family") != "inet6" or entry.get("scope") != "global":
                continue
            flags = entry.get("flags", [])
            if entry.get("tentative") or entry.get("dadfailed") or any(x in flags for x in ("tentative", "dadfailed")):
                continue
            address = ipaddress.IPv6Address(entry["local"])
            prefix = entry.get("prefixlen")
            if not isinstance(prefix, int) or isinstance(prefix, bool) or not 64 <= prefix <= 128:
                continue
            if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local or address.ipv4_mapped:
                continue
            network = ipaddress.IPv6Network((address, prefix), strict=False)
            bindings.append((str(address), 0, (network,)))
    return bindings


def make_handler(store, *, host, port, ca_der, mobile_html, bootstrap=False,
                 https_port=8443, profile_bytes=None, hostname=None, prefer_hostname=False):
    allowed_names = [host]
    if hostname is not None:
        # The provided certificate is specifically issued for this name.
        if hostname != "safeguard.local":
            raise ValueError("Only the certificate name safeguard.local is supported")
        allowed_names.append(hostname)
    expected_hosts = {f"{name}:{port}" for name in allowed_names}
    fingerprint = hashlib.sha256(ca_der).hexdigest().upper()
    fingerprint = ":".join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))
    cert_link = "/SafeGuard_Navigation.mobileconfig" if profile_bytes is not None else "/safeguard-root.cer"
    setup_pages = {}
    for page_host in allowed_names:
        link_host = hostname if prefer_hostname and hostname else page_host
        setup = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SafeGuard 연결 준비</title><style>body{{font:17px system-ui;max-width:650px;margin:32px auto;padding:20px;line-height:1.6}}a{{display:block;padding:14px;margin:12px 0;background:#e7f0ff;border-radius:10px;overflow-wrap:anywhere}}code{{overflow-wrap:anywhere;font-size:12px}}</style><h1>SafeGuard 아이폰 연결 준비</h1><p>이 Pi에만 연결하는 시연용 HTTPS 인증서입니다. 기기 관리(MDM), VPN, 프록시 설정은 포함하지 않습니다.</p><ol><li>아래 인증서를 받기 전에 Pi 창의 SHA-256 지문과 이 페이지의 지문이 같은지 확인하세요.</li><li>인증서 다운로드 후 설정 → 일반 → VPN 및 기기 관리에서 SafeGuard 인증서를 설치합니다.</li><li>설정 → 일반 → 정보 → 인증서 신뢰 설정에서 이 SafeGuard 인증서만 신뢰하도록 설정합니다.</li><li>아래 HTTPS 화면을 열고 Pi 창의 8자리 연결 코드를 입력합니다.</li></ol><p>인증서 SHA-256</p><code>{fingerprint}</code><a href="{cert_link}">1. SafeGuard 공개 인증서 다운로드</a><a href="https://{page_host}:{https_port}/">2. 위치 전달 화면 열기</a><p>시연 후 설정에서 이 인증서를 삭제할 수 있습니다. 비밀 키는 다운로드되지 않습니다.</p></html>'''.encode()
        if link_host != page_host:
            setup = setup.replace(f'https://{page_host}:{https_port}/'.encode(),
                                  f'https://{link_host}:{https_port}/'.encode())
        setup_pages[f"{page_host}:{port}"] = setup

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "SafeGuardNavigation"
        sys_version = ""

        def setup(self):
            if isinstance(self.request, ssl.SSLSocket):
                self.request.do_handshake()
            super().setup()

        def log_message(self, *args):
            pass  # Never log credentials, bodies, positions, or arbitrary URL text.

        def send_bytes(self, status, body, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Permissions-Policy", "geolocation=(self)")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(body)

        def reply(self, status, payload):
            self.send_bytes(status, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())

        def valid_host(self):
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or hosts[0] not in expected_hosts:
                self.reply(403, {"error": "Host rejected. Use an exact address printed by Pi."})
                return False
            return True

        def authenticate(self):
            values = self.headers.get_all("Authorization", [])
            if len(values) != 1 or not store.authorized(values[0]):
                self.reply(401, {"error": "Pair this phone first"})
                return False
            return True

        def do_GET(self):
            if not self.valid_host():
                return
            if bootstrap:
                if self.path == "/":
                    self.send_bytes(200, setup_pages[self.headers["Host"]], "text/html; charset=utf-8")
                elif self.path == "/SafeGuard_Navigation.mobileconfig" and profile_bytes is not None:
                    self.send_bytes(200, profile_bytes, "application/x-apple-aspen-config")
                elif self.path == "/safeguard-root.cer":
                    self.send_bytes(200, ca_der, "application/x-x509-ca-cert")
                else:
                    self.reply(404, {"error": "Not found"})
                return
            if self.path == "/":
                self.send_bytes(200, mobile_html, "text/html; charset=utf-8")
            elif self.path == "/api/status":
                if self.authenticate():
                    self.reply(200, store.status())
            else:
                self.reply(404, {"error": "Not found"})

        def do_POST(self):
            if not self.valid_host():
                return
            if bootstrap:
                self.reply(405, {"error": "Certificate download only"})
                return
            origins = self.headers.get_all("Origin", [])
            if origins != ["https://" + self.headers["Host"]]:
                self.reply(403, {"error": "Origin rejected"})
                return
            if self.path not in ("/api/pair", "/api/location"):
                self.reply(404, {"error": "Not found"})
                return
            if self.path == "/api/location" and not self.authenticate():
                return
            if self.headers.get("Transfer-Encoding") is not None:
                self.reply(400, {"error": "Transfer encoding unsupported"})
                return
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or len(lengths[0]) > 5 or not lengths[0].isascii() or not lengths[0].isdigit():
                self.reply(411, {"error": "One content length required"})
                return
            size = int(lengths[0])
            if not 0 < size <= MAX_REQUEST_BYTES:
                self.reply(413, {"error": "Request too large or empty"})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                self.reply(415, {"error": "application/json required"})
                return
            try:
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("Incomplete request")
                data = strict_json(raw)
                result = store.pair(data) if self.path == "/api/pair" else store.accept(data)
                self.reply(200, result)
            except BridgeError as exc:
                with store.lock:
                    store.last_error = str(exc)
                self.reply(exc.status, {"error": str(exc)})
            except (ValueError, UnicodeError, OSError) as exc:
                with store.lock:
                    store.last_error = "Invalid request or state write failed"
                self.reply(400 if isinstance(exc, (ValueError, UnicodeError)) else 503,
                           {"error": store.last_error})

    return Handler


def ca_der_bytes(path):
    data = Path(path).read_bytes()
    if len(data) > 32768:
        raise ValueError("CA certificate exceeds size limit")
    if b"PRIVATE KEY" in data:
        raise ValueError("--ca must be a public certificate only")
    if b"-----BEGIN CERTIFICATE-----" in data:
        data = ssl.PEM_cert_to_DER_cert(data.decode("ascii"))
    return data


def load_profile(path, ca_der):
    raw = Path(path).read_bytes()
    if len(raw) > 65536:
        raise ValueError("Certificate profile too large")
    profile = plistlib.loads(raw)
    payloads = profile.get("PayloadContent") if isinstance(profile, dict) else None
    if (not isinstance(profile, dict) or profile.get("PayloadType") != "Configuration" or not isinstance(payloads, list)
            or len(payloads) != 1 or not isinstance(payloads[0], dict)
            or payloads[0].get("PayloadType") != "com.apple.security.root"
            or payloads[0].get("PayloadContent") != ca_der):
        raise ValueError("Profile must contain only the matching public root certificate")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Pi's specific IPv4 on the shared hotspot")
    parser.add_argument("--hostname", choices=("safeguard.local",), default="safeguard.local")
    parser.add_argument("--ipv6-interface", help="Also listen on this Wi-Fi interface’s usable IPv6 addresses")
    parser.add_argument("--prefer-hostname", action="store_true", help="Use the certificate DNS name for all HTTPS links")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--http-port", type=int, default=8081)
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--profile", type=Path, help="Optional cert-only iOS mobileconfig")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--max-accuracy-m", type=float, default=200)
    args = parser.parse_args()
    servers = []
    started_servers = []
    store = None
    try:
        address = ipaddress.IPv4Address(args.host)
        if address.is_unspecified or address.is_multicast or not address.is_private:
            raise ValueError("Use the Pi's private, specific IPv4 address")
        if not (1024 <= args.port <= 65535 and 1024 <= args.http_port <= 65535) or args.port == args.http_port:
            raise ValueError("Use two different unprivileged ports (1024..65535)")
        ca = ca_der_bytes(args.ca)
        profile = load_profile(args.profile, ca) if args.profile else None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.cert, args.key)
        mobile = Path(__file__).with_name("navigation_phone.html").read_bytes()
        bindings = wlan_ipv6_bindings(args.ipv6_interface) if args.ipv6_interface else []
        # Bind every socket before touching shared state. A failed/duplicate
        # launch cannot invalidate the existing receiver's state file.
        secure = BridgeServer((args.host, args.port), BaseHTTPRequestHandler)
        servers.append(secure)
        bootstrap = BridgeServer((args.host, args.http_port), BaseHTTPRequestHandler)
        servers.append(bootstrap)
        listeners = [(secure, False), (bootstrap, True)]
        for ipv6, scope, networks in bindings:
            for port, is_bootstrap in ((args.port, False), (args.http_port, True)):
                listener = IPv6BridgeServer((ipv6, port, 0, scope), BaseHTTPRequestHandler)
                listener.allowed_peer_networks = networks
                servers.append(listener)
                listeners.append((listener, is_bootstrap))
        store = LocationStore(args.state_file, max_accuracy_m=args.max_accuracy_m)
        for listener, is_bootstrap in listeners:
            listener.RequestHandlerClass = make_handler(store, host=args.host,
                hostname=args.hostname, port=args.http_port if is_bootstrap else args.port,
                ca_der=ca, mobile_html=mobile, bootstrap=is_bootstrap,
                https_port=args.port, profile_bytes=profile if is_bootstrap else None,
                prefer_hostname=args.prefer_hostname)
            if not is_bootstrap:
                listener.socket = context.wrap_socket(listener.socket, server_side=True,
                                                      do_handshake_on_connect=False)
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            started_servers.append(server)
        fingerprint = hashlib.sha256(ca).hexdigest().upper()
        print("SafeGuard iPhone navigation receiver", flush=True)
        print(f"Setup: http://{args.host}:{args.http_port}/", flush=True)
        if not args.prefer_hostname:
            print(f"Phone: https://{args.host}:{args.port}/", flush=True)
        print(f"Setup (name): http://{args.hostname}:{args.http_port}/", flush=True)
        print(f"Phone (name): https://{args.hostname}:{args.port}/", flush=True)
        for ipv6, scope, networks in bindings:
            print(f"IPv6 listening: {ipv6} (same Wi-Fi network clients)", flush=True)
        print("CA SHA-256: " + ":".join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2)), flush=True)
        print("PAIRING CODE (8 digits, one phone, 10 minutes): " + store.pairing_code, flush=True)
        print("State file: " + str(args.state_file.resolve()), flush=True)
        print("Keep this window open. Ctrl+C stops and invalidates location.", flush=True)
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping navigation receiver.", flush=True)
    except (OSError, ValueError, ssl.SSLError, subprocess.SubprocessError) as exc:
        parser.exit(2, "Navigation receiver failed: " + str(exc) + "\n")
    finally:
        if store is not None:
            store.close()
        for server in servers:
            # Only call shutdown if serve_forever was started; unstarted
            # listeners are closed directly during setup errors.
            if server in started_servers:
                server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
