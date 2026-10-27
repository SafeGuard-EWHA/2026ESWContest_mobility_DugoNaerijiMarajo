"""Local monitoring UI. Control callbacks request an action; they never actuate hardware."""

from __future__ import annotations

import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


_MAX_REQUEST_BYTES = 1024
_MAX_STATE_BYTES = 2 * 1024 * 1024
_MAX_AMBIENT_BYTES = 64 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON number")


def _finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _ambient_details(state_path, config, now=None):
    """Display-only provenance. Never overwrite the C++ controller's inputs."""
    profile = config.get("profile")
    demo = config.get("demo", {})
    settings = config.get("ambient_provider", {})
    if (profile not in ("REAL", "HARDWARE_DEMO") or
            (profile == "HARDWARE_DEMO" and demo.get("override_temperature") is True) or
            not isinstance(settings, dict) or settings.get("enabled") is not True):
        return None
    invalid = {"valid": False, "temp_c": None, "status": "provenance_unavailable"}
    try:
        with Path(state_path).with_name("ambient_status.json").open("rb") as stream:
            raw = stream.read(_MAX_AMBIENT_BYTES + 1)
        if len(raw) > _MAX_AMBIENT_BYTES:
            raise ValueError("ambient provenance too large")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant, parse_float=_finite_float)
        if (not isinstance(data, dict) or data.get("source") != "REAL_AMBIENT" or
                data.get("provider") != "open_meteo" or
                data.get("data_kind") != "model_estimate" or
                data.get("onsite_measurement") is not False or
                type(data.get("valid")) is not bool):
            raise ValueError("invalid ambient provenance")
        if data["valid"] and not _finite(data.get("temp_c")):
            raise ValueError("invalid ambient temperature")
        rx = data.get("rx_monotonic_s")
        current = time.monotonic() if now is None else now
        if not _finite(rx) or not 0 <= current - rx < 3.0:
            data.update(valid=False, temp_c=None, status="provenance_stale")
        elif data["valid"] is False:
            data["temp_c"] = None
        return data
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return invalid


def start_dashboard(state_file, config, operator_callback):
    """Start a daemon HTTP thread and return its server, or None when disabled.

    config may be the complete config with a ``dashboard`` object or the
    dashboard settings themselves: enabled=True, host='127.0.0.1', port=8080.
    Only localhost binding is allowed. Port 0 is useful for automated tests.
    operator_callback(action) must enqueue/record the request without directly
    bypassing the main controller's return/rearm conditions. An explicit False
    return rejects a request; other returns mean delivery, not execution.
    Call server.shutdown() followed by server.server_close() during cleanup.
    """
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise TypeError("dashboard configuration must be an object")
    settings = config.get("dashboard", config)
    if not isinstance(settings, dict):
        raise TypeError("dashboard settings must be an object")
    enabled = settings.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("dashboard.enabled must be a boolean")
    if not enabled:
        return None
    if not callable(operator_callback):
        raise TypeError("operator_callback must be callable")
    host = settings.get("host", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("dashboard.host must be 127.0.0.1 or localhost")
    port = settings.get("port", 8080)
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("dashboard.port must be an integer from 0 to 65535")

    state_path = Path(state_file)
    page = Path(__file__).with_name("dashboard.html").read_bytes()
    callback_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "SafeGuardLocal"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(3.0)

        def log_message(self, format, *args):
            pass

        def _send(self, status, payload, content_type="application/json; charset=utf-8"):
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _local_request(self):
            bound_port = self.server.server_address[1]
            allowed_hosts = {f"127.0.0.1:{bound_port}", f"localhost:{bound_port}"}
            if bound_port == 80:
                allowed_hosts.update({"127.0.0.1", "localhost"})
            if self.headers.get("Host", "").lower() not in allowed_hosts:
                self._send(403, {"ok": False, "error": "local_host_required"})
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin.lower() not in {"http://" + host for host in allowed_hosts}:
                self._send(403, {"ok": False, "error": "same_origin_required"})
                return False
            if self.headers.get("Sec-Fetch-Site", "") == "cross-site":
                self._send(403, {"ok": False, "error": "same_origin_required"})
                return False
            return True

        def do_GET(self):
            if not self._local_request():
                return
            path = urlsplit(self.path).path
            if path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif path == "/api/state":
                try:
                    with state_path.open("rb") as stream:
                        raw = stream.read(_MAX_STATE_BYTES + 1)
                    if len(raw) > _MAX_STATE_BYTES:
                        raise ValueError("state too large")
                    state = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                                       parse_constant=_reject_constant)
                    if not isinstance(state, dict):
                        raise ValueError("state must be an object")
                    # Metadata is scoped to this run directory and this input mode.
                    # It is informational; the C++ ambient validity/value remain intact.
                    state.pop("ambient_provider", None)
                    provenance = _ambient_details(state_path, config)
                    if provenance is not None:
                        state["ambient_provider"] = provenance
                    self._send(200, state)
                except (OSError, UnicodeError, ValueError, RecursionError):
                    self._send(503, {"status": "WAITING", "reason": "state_unavailable"})
            else:
                self._send(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            if not self._local_request():
                return
            if urlsplit(self.path).path != "/api/control":
                self._send(404, {"ok": False, "error": "not_found"})
                return
            if self.headers.get("Transfer-Encoding") is not None:
                self._send(400, {"ok": False, "error": "unsupported_transfer_encoding"})
                return
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1:
                self._send(411, {"ok": False, "error": "content_length_required"})
                return
            try:
                length = int(lengths[0])
            except (ValueError, TypeError):
                self._send(400, {"ok": False, "error": "invalid_content_length"})
                return
            if not 0 < length <= _MAX_REQUEST_BYTES:
                self._send(413, {"ok": False, "error": "invalid_body_size"})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._send(415, {"ok": False, "error": "json_required"})
                return
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("incomplete body")
                request = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                     parse_constant=_reject_constant)
                expected_keys = {"action", "stop_request_id"} if isinstance(request, dict) and request.get("action") == "manual_resume" else {"action"}
                if (not isinstance(request, dict) or set(request) != expected_keys
                        or not isinstance(request["action"], str)
                        or request["action"] not in ("clear", "rearm", "manual_stop", "manual_resume")):
                    raise ValueError("invalid action")
                if request["action"] == "manual_resume" and (not isinstance(request["stop_request_id"], str) or not 0 < len(request["stop_request_id"]) <= 64):
                    raise ValueError("invalid stop identity")
            except (ValueError, UnicodeError, OSError, RecursionError):
                self._send(400, {"ok": False, "error": "invalid_request"})
                return
            try:
                with callback_lock:
                    accepted = operator_callback(request if request["action"] == "manual_resume" else request["action"]) is not False
            except Exception:
                self._send(503, {"ok": False, "error": "request_delivery_failed"})
                return
            if not accepted:
                self._send(409, {"ok": False, "error": "request_rejected"})
                return
            self._send(202, {"ok": True, "accepted": True, "action": request["action"]})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="safeguard-dashboard", daemon=True)
    server.dashboard_thread = thread
    thread.start()
    return server
