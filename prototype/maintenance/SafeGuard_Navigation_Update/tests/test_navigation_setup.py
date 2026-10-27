import importlib.util
import json
import os
from pathlib import Path
import plistlib
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest


SPEC = importlib.util.spec_from_file_location("setup_navigation", Path(__file__).resolve().parents[1] / "setup_navigation.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class NavigationSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.project = Path(cls.temporary.name) / "SafeGuard_Main"
        (cls.project / "scripts").mkdir(parents=True)
        (cls.project / "scripts/navigation_bridge.py").write_text("# placeholder for TLS tests\n")
        cls.first = module.setup(cls.project, "172.20.10.8")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_certificate_chain_names_and_constraints(self):
        result = self.first
        module.openssl("verify", "-CAfile", result["ca"], "-purpose", "sslserver",
                       "-verify_ip", "172.20.10.8", result["cert"])
        module.openssl("verify", "-CAfile", result["ca"], "-verify_hostname", "safeguard.local", result["cert"])
        with self.assertRaises(ValueError):
            module.openssl("verify", "-CAfile", result["ca"], "-verify_ip", "172.20.10.9", result["cert"])
        constraints = module.openssl("x509", "-in", result["ca"], "-noout", "-ext", "nameConstraints")
        self.assertIn("critical", constraints)
        self.assertIn("safeguard.local", constraints)
        self.assertIn("172.20.10.8", constraints)

    def test_profile_is_only_the_public_root_and_private_material_is_limited(self):
        result = self.first
        profile = plistlib.loads(Path(result["profile"]).read_bytes())
        payloads = profile["PayloadContent"]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["PayloadType"], "com.apple.security.root")
        self.assertEqual(payloads[0]["PayloadContent"], Path(result["ca_der"]).read_bytes())
        self.assertFalse(profile["PayloadRemovalDisallowed"])
        files = sorted(p.name for p in Path(result["directory"]).iterdir())
        self.assertEqual(files, sorted(module.OUTPUT_NAMES))
        self.assertFalse(any("ca-signing" in str(p) for p in self.project.rglob("*")))
        if os.name == "posix":
            self.assertEqual(Path(result["key"]).stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(result["directory"]).stat().st_mode & 0o777, 0o700)

    def test_same_ip_reuses_but_different_ip_needs_explicit_regeneration(self):
        result = module.setup(self.project, "172.20.10.8")
        self.assertTrue(result["reused"])
        self.assertEqual(result["fingerprint_sha256"], self.first["fingerprint_sha256"])
        original = Path(result["cert"]).read_bytes()
        with self.assertRaisesRegex(ValueError, "IP has changed"):
            module.setup(self.project, "172.20.10.9")
        self.assertEqual(Path(result["cert"]).read_bytes(), original)

    def test_tls_handshake_uses_normal_certificate_verification(self):
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.minimum_version = ssl.TLSVersion.TLSv1_2
        server_context.load_cert_chain(self.first["cert"], self.first["key"])
        client_context = ssl.create_default_context(cafile=self.first["ca"])
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)
        errors = []

        def serve():
            try:
                connection, address = listener.accept()
                with server_context.wrap_socket(connection, server_side=True) as secure:
                    self.assertEqual(secure.recv(2), b"ok")
                    secure.sendall(b"ok")
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            with socket.create_connection(listener.getsockname(), timeout=5) as connection:
                with client_context.wrap_socket(connection, server_hostname="172.20.10.8") as secure:
                    secure.sendall(b"ok")
                    self.assertEqual(secure.recv(2), b"ok")
        finally:
            thread.join(5)
            listener.close()
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)

    def test_invalid_ip_does_not_create_setup(self):
        for ip in ("8.8.8.8", "127.0.0.1", "::1", "172.20.10.8;echo bad", "not an address"):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                module.private_ipv4(ip)

    def test_regeneration_retains_old_identity_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "scripts").mkdir()
            (project / "scripts/navigation_bridge.py").write_text("# placeholder\n")
            first = module.setup(project, "172.20.10.8")
            old_certificate = Path(first["cert"]).read_bytes()
            changed = module.setup(project, "172.20.10.9", regenerate=True)
            self.assertFalse(changed["reused"])
            self.assertNotEqual(changed["fingerprint_sha256"], first["fingerprint_sha256"])
            backup, = (project / "runtime").glob("navigation_tls_backup_*")
            self.assertEqual((backup / "server.pem").read_bytes(), old_certificate)
            module.validate_existing(Path(changed["directory"]), "172.20.10.9")


if __name__ == "__main__":
    unittest.main()
