#!/usr/bin/env python3
"""Create a local, certificate-only HTTPS identity for the iPhone demo.

This does not install anything on the phone or change system trust on the Pi.
The user explicitly installs/trusts the public certificate on their own phone.
The signing CA private key is destroyed after generating this server identity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid


CERT_NAME = "SafeGuard Local Navigation Demo"
DNS_NAME = "safeguard.local"
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(s) for s in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
OUTPUT_NAMES = ("server.pem", "server.key", "root_ca.pem", "root_ca.cer",
                "SafeGuard_Navigation.mobileconfig", "setup.json")


def private_ipv4(value):
    try:
        address = ipaddress.IPv4Address(str(value))
    except ipaddress.AddressValueError as error:
        raise ValueError("--ip must be the Pi's private IPv4 address") from error
    if not any(address in network for network in PRIVATE_NETWORKS):
        raise ValueError("--ip must be a private LAN IPv4 address (10.*, 172.16-31.*, or 192.168.*)")
    return str(address)


def detect_ip():
    """Read local interface/route information; never query a location service."""
    if shutil.which("ip") is None:
        raise ValueError("Cannot detect the Pi IP. Run hostname -I, then add --ip <Pi IPv4>.")
    result = subprocess.run(["ip", "-j", "-4", "address", "show", "scope", "global"],
                            capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        raise ValueError("Cannot inspect network interfaces. Supply --ip explicitly.")
    try:
        entries = json.loads(result.stdout)
        candidates = set()
        for interface in entries:
            for entry in interface.get("addr_info", []):
                if entry.get("family") != "inet":
                    continue
                try:
                    candidates.add(private_ipv4(entry["local"]))
                except (ValueError, KeyError):
                    pass
        # This asks the kernel which local source address it would use. It does
        # not connect to 1.1.1.1 or send a packet there.
        route = subprocess.run(["ip", "-j", "-4", "route", "get", "1.1.1.1"],
                               capture_output=True, text=True, timeout=5, check=False)
        if route.returncode == 0:
            routes = json.loads(route.stdout)
            if routes and routes[0].get("prefsrc") in candidates:
                return routes[0]["prefsrc"]
        if len(candidates) == 1:
            return next(iter(candidates))
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError("Cannot inspect network addresses. Supply --ip explicitly.") from error
    raise ValueError("No unambiguous LAN IP. Run hostname -I and supply --ip <Pi IPv4>.")


def openssl(*arguments):
    result = subprocess.run(["openssl", *map(str, arguments)], capture_output=True,
                            text=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("OpenSSL " + str(arguments[0]) + " failed: " + result.stderr.strip()[:500])
    return result.stdout


def fingerprint(der):
    raw = hashlib.sha256(der).hexdigest().upper()
    return ":".join(raw[i:i + 2] for i in range(0, len(raw), 2))


def result_paths(directory, ip, reused):
    der = (directory / "root_ca.cer").read_bytes()
    return {"host": ip, "ip": ip, "directory": str(directory),
            "cert": str(directory / "server.pem"),
            "key": str(directory / "server.key"),
            "ca": str(directory / "root_ca.pem"),
            "ca_der": str(directory / "root_ca.cer"),
            "profile": str(directory / "SafeGuard_Navigation.mobileconfig"),
            "fingerprint_sha256": fingerprint(der), "reused": reused}


def validate_existing(directory, ip):
    for name in OUTPUT_NAMES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Existing HTTPS setup is incomplete. Use --regenerate to replace it explicitly.")
    try:
        metadata = json.loads((directory / "setup.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Invalid existing HTTPS setup. Use --regenerate explicitly.") from error
    if metadata.get("schema_version") != 1 or metadata.get("ip") != ip:
        raise ValueError("Pi IP has changed. Use --regenerate; the phone will need the new certificate installed/trusted.")
    actual_fingerprint = fingerprint((directory / "root_ca.cer").read_bytes())
    if metadata.get("fingerprint_sha256") != actual_fingerprint:
        raise ValueError("Saved CA fingerprint differs. Refusing to reuse this setup.")
    ca = directory / "root_ca.pem"
    cert = directory / "server.pem"
    key = directory / "server.key"
    openssl("x509", "-in", ca, "-noout", "-checkend", "86400")
    openssl("x509", "-in", cert, "-noout", "-checkend", "86400")
    openssl("verify", "-CAfile", ca, "-purpose", "sslserver", "-verify_ip", ip, cert)
    openssl("verify", "-CAfile", ca, "-purpose", "sslserver", "-verify_hostname", DNS_NAME, cert)
    sans = openssl("x509", "-in", cert, "-noout", "-ext", "subjectAltName")
    entries = {entry.strip() for entry in sans.splitlines()[1:] for entry in entry.split(",")}
    if entries != {"DNS:" + DNS_NAME, "IP Address:" + ip}:
        raise ValueError("Unexpected certificate names. Use --regenerate explicitly.")
    public_cert = openssl("x509", "-in", cert, "-pubkey", "-noout")
    public_key = openssl("pkey", "-in", key, "-pubout")
    if public_cert.strip() != public_key.strip():
        raise ValueError("HTTPS server key does not match its certificate.")
    import ssl
    if ssl.PEM_cert_to_DER_cert(ca.read_text(encoding="ascii")) != (directory / "root_ca.cer").read_bytes():
        raise ValueError("Public CA files differ. Refusing to reuse this setup.")
    profile = plistlib.loads((directory / "SafeGuard_Navigation.mobileconfig").read_bytes())
    contents = profile.get("PayloadContent", [])
    if (profile.get("PayloadType") != "Configuration" or len(contents) != 1 or
            contents[0].get("PayloadType") != "com.apple.security.root" or
            contents[0].get("PayloadContent") != (directory / "root_ca.cer").read_bytes()):
        raise ValueError("Profile must contain only this local root certificate.")
    if os.name == "posix":
        os.chmod(directory, 0o700)
        os.chmod(key, 0o600)


def setup(project, ip=None, regenerate=False):
    project = Path(project).expanduser().resolve()
    if not (project / "scripts" / "navigation_bridge.py").is_file():
        raise ValueError("Install the navigation update into SafeGuard_Main before setup.")
    if shutil.which("openssl") is None:
        raise ValueError("OpenSSL is missing. Install it on the Pi with: sudo apt install openssl")
    ip = private_ipv4(ip) if ip is not None else detect_ip()
    runtime = project / "runtime"
    if runtime.is_symlink():
        raise ValueError("runtime must be a real directory inside SafeGuard_Main")
    runtime.mkdir(mode=0o700, exist_ok=True)
    directory = runtime / "navigation_tls"
    if directory.is_symlink():
        raise ValueError("navigation_tls must not be a symbolic link")
    if directory.exists() and not regenerate:
        validate_existing(directory, ip)
        return result_paths(directory, ip, True)
    if directory.exists() and not directory.is_dir():
        raise ValueError("navigation_tls is not a directory")

    # Keep all unfinished materials private. TemporaryDirectory removes the CA
    # key even when signing or output validation fails.
    old_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="navigation_tls_build_", dir=runtime) as temporary:
            work = Path(temporary)
            destination = work / "ready"
            destination.mkdir(mode=0o700)
            ca_key = work / "ca-signing.key"
            ca_config = work / "ca.cnf"
            ca_config.write_text("""[req]
prompt = no
distinguished_name = dn
x509_extensions = ca_ext
[dn]
CN = SafeGuard Local Navigation Demo
O = SafeGuard Local Demo
[ca_ext]
basicConstraints = critical,CA:true,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
nameConstraints = critical,permitted;DNS:safeguard.local,permitted;IP:""" + ip + "/255.255.255.255\n", encoding="ascii")
            openssl("req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
                    "-days", "30", "-config", ca_config,
                    "-keyout", ca_key, "-out", destination / "root_ca.pem")
            key = destination / "server.key"
            request = work / "server.csr"
            openssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256",
                    "-subj", "/CN=safeguard.local/O=SafeGuard Local Demo",
                    "-keyout", key, "-out", request)
            extension = work / "server.cnf"
            extension.write_text("""[server_ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
subjectAltName = DNS:safeguard.local,IP:""" + ip + "\n", encoding="ascii")
            openssl("x509", "-req", "-in", request, "-CA", destination / "root_ca.pem",
                    "-CAkey", ca_key, "-set_serial", str(uuid.uuid4().int),
                    "-days", "30", "-sha256", "-extfile", extension,
                    "-extensions", "server_ext", "-out", destination / "server.pem")
            ca_key.unlink()
            openssl("x509", "-in", destination / "root_ca.pem", "-outform", "DER",
                    "-out", destination / "root_ca.cer")
            der = (destination / "root_ca.cer").read_bytes()
            profile_id = "local.safeguard.navigation." + uuid.uuid4().hex
            profile = {
                "PayloadType": "Configuration", "PayloadVersion": 1,
                "PayloadIdentifier": profile_id,
                "PayloadUUID": str(uuid.uuid4()).upper(),
                "PayloadDisplayName": CERT_NAME,
                "PayloadOrganization": "SafeGuard Local Demo",
                "PayloadDescription": "Certificate only for this Pi's local navigation demo. No device management, VPN or Wi-Fi settings. Remove after the demo.",
                "PayloadRemovalDisallowed": False,
                "PayloadContent": [{
                    "PayloadType": "com.apple.security.root", "PayloadVersion": 1,
                    "PayloadIdentifier": profile_id + ".root",
                    "PayloadUUID": str(uuid.uuid4()).upper(),
                    "PayloadDisplayName": CERT_NAME,
                    "PayloadCertificateFileName": "safeguard-root.cer",
                    "PayloadContent": der,
                }],
            }
            (destination / "SafeGuard_Navigation.mobileconfig").write_bytes(plistlib.dumps(profile))
            metadata = {"schema_version": 1, "ip": ip, "dns_name": DNS_NAME,
                        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "fingerprint_sha256": fingerprint(der),
                        "certificate_days": 30, "ca_private_key_retained": False,
                        "phone_trust_installed": False}
            (destination / "setup.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            for name in OUTPUT_NAMES:
                os.chmod(destination / name, 0o600 if name in ("server.key", "setup.json") else 0o644)
            validate_existing(destination, ip)
            backup = None
            if directory.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
                backup = runtime / ("navigation_tls_backup_" + stamp)
                directory.rename(backup)
            try:
                destination.rename(directory)
            except OSError:
                if backup is not None and not directory.exists():
                    backup.rename(directory)
                raise
    finally:
        os.umask(old_umask)
    return result_paths(directory, ip, False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.home() / "SafeGuard_Main")
    parser.add_argument("--ip", help="Pi private IPv4 on the shared hotspot; auto-detected if omitted")
    parser.add_argument("--regenerate", action="store_true", help="replace HTTPS identity, preserving a backup; trust the new certificate on the phone")
    args = parser.parse_args()
    try:
        result = setup(args.project, args.ip, args.regenerate)
    except (OSError, ValueError, subprocess.SubprocessError, plistlib.InvalidFileException) as error:
        parser.exit(2, "Navigation HTTPS setup stopped: " + str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    project = args.project.expanduser().resolve()
    command = ["python3", str(project / "scripts/navigation_bridge.py"),
               "--host", result["host"], "--cert", result["cert"], "--key", result["key"],
               "--ca", result["ca"], "--profile", result["profile"],
               "--state-file", str(project / "runtime/navigation_location.json")]
    print("Start the local navigation receiver:\n" + shlex.join(command))
    print("The iPhone certificate has NOT been installed automatically. Follow the supplied iPhone setup steps.")


if __name__ == "__main__":
    main()
