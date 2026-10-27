#!/usr/bin/env python3
"""Start the local navigation receiver; leave this terminal open during the demo."""
import argparse
from pathlib import Path
import subprocess
import sys

from setup_navigation import setup


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", type=Path, default=Path.home()/"SafeGuard_Main")
    p.add_argument("--ip")
    args = p.parse_args()
    project = args.project.resolve()
    if not (project/"scripts/navigation_bridge.py").is_file():
        p.exit(2, "Run install_navigation.py first.\n")
    try:
        tls = setup(project, ip=args.ip)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        p.exit(2, "Navigation setup stopped: " + str(exc) + "\n")
    print("Local certificate SHA256: " + tls["fingerprint_sha256"], flush=True)
    command = [sys.executable, str(project/"scripts/navigation_bridge.py"),
               "--host", tls["host"], "--cert", str(tls["cert"]),
               "--key", str(tls["key"]), "--ca", str(tls["ca"]),
               "--profile", str(tls["profile"]),
               "--state-file", str(project/"runtime/navigation_location.json")]
    try:
        return subprocess.call(command)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
