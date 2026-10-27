#!/usr/bin/env python3
"""SafeGuard navigation-only IPv4 fix. Run on Pi with sudo. No Wi-Fi changes."""
import datetime, hashlib, os, secrets, subprocess, sys, time
from pathlib import Path
BASE_HASH = 'ac96c88879546c0b241ac24d05a279083405b3d3006bf6607ce32a51c98fb654'
NEW_HASH = '86e125343d6437ce51b1ba1681567e305e5d8e355f0753870a0f53c543411c22'
UNIT_HASH = '5f51a00112cc28732523b958d4d3bc6243f9ff4cb9aa6c2cd3ee70da8098ff37'
CHANGES = [("if not ipv4 or not ipv6 or not has_global:raise ValueError('Waiting for wlan0 IPv4 and Wi-Fi global IPv6 address')", "if not ipv4:raise ValueError('Waiting for wlan0 private IPv4 address')"), ('def receiver_command(project,current_ip,tls):', 'def receiver_command(project,current_ip,tls,ipv6_addresses=()):'), ("    return [sys.executable,str(Path(project)/'scripts/navigation_bridge.py'),", "    command = [sys.executable,str(Path(project)/'scripts/navigation_bridge.py'),"), ("'--host',current_ip,'--hostname','safeguard.local','--ipv6-interface','wlan0','--prefer-hostname',", "'--host',current_ip,'--hostname','safeguard.local','--prefer-hostname',"), ("'--state-file',str(Path(project)/'runtime/navigation_location.json')]", "'--state-file',str(Path(project)/'runtime/navigation_location.json')]\n    if ipv6_addresses:command.extend(['--ipv6-interface','wlan0'])\n    return command"), ('receiver_command(project,addresses[0],tls)', 'receiver_command(project,addresses[0],tls,addresses[1])')]

SERVICE = 'safeguard-navigation.service'
LIB = Path('/usr/local/lib/safeguard-navigation')
UNIT = Path('/etc/systemd/system') / SERVICE
DROP = Path(str(UNIT) + '.d') / '90-network-readonly.conf'
OVERRIDE = '# SafeGuard IPv4-compatible receiver; no network writes\n[Service]\nExecStartPre=\n'

def transform(source):
    h = hashlib.sha256(source.encode()).hexdigest()
    if h == NEW_HASH:
        return source
    if h != BASE_HASH:
        raise ValueError('Installed receiver differs from the reviewed version; no changes made.')
    for old, new in CHANGES:
        if source.count(old) != 1:
            raise ValueError('Unexpected receiver source; no changes made.')
        source = source.replace(old, new)
    if hashlib.sha256(source.encode()).hexdigest() != NEW_HASH:
        raise ValueError('Patch verification failed')
    compile(source, 'run_receiver.py', 'exec')
    return source

def command(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=35).stdout

def atomic_write(path, data):
    temporary = path.with_name(path.name + '.ipv4-new')
    with temporary.open('xb') as f:
        f.write(data)
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)

def main():
    if os.geteuid() != 0:
        raise ValueError('Run: sudo python3 ' + Path(__file__).name)
    runtime = LIB / 'run_receiver.py'
    for p in (UNIT, runtime, DROP.parent, DROP):
        if p.is_symlink():
            raise ValueError('Unexpected symlink: ' + str(p))
    if hashlib.sha256(UNIT.read_bytes()).hexdigest() != UNIT_HASH:
        raise ValueError('Service unit differs from reviewed V2; no changes made.')
    drop_paths = command('systemctl', 'show', SERVICE, '--property=DropInPaths', '--value').strip().split()
    if any(p != str(DROP) for p in drop_paths):
        raise ValueError('Unreviewed service override exists; no changes made.')
    if DROP.exists() and DROP.read_text() != OVERRIDE:
        raise ValueError('Different override already exists; no changes made.')
    original = runtime.read_bytes()
    replacement = transform(original.decode()).encode()
    if original == replacement and DROP.exists():
        print('ALREADY INSTALLED; no files or services changed.')
        print(command('systemctl', 'is-active', SERVICE).strip())
        return
    backup = Path('/var/backups') / ('safeguard-navigation-ipv4-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
    backup.mkdir(mode=0o700)
    (backup/'run_receiver.py').write_bytes(original)
    old_drop = DROP.read_bytes() if DROP.exists() else None
    if old_drop is not None:
        (backup/'90-network-readonly.conf').write_bytes(old_drop)
    (backup/'service.unit').write_bytes(UNIT.read_bytes())
    print('BACKUP:', backup, flush=True)
    # The reviewed unit has no ExecStop/ExecStopPost network action.
    # Only this navigation unit is stopped; no sensor service or network service is touched.
    command('systemctl', 'stop', SERVICE)
    try:
        atomic_write(runtime, replacement)
        DROP.parent.mkdir(exist_ok=True)
        atomic_write(DROP, OVERRIDE.encode())
        command('systemctl', 'daemon-reload')
        command('systemctl', 'start', SERVICE)
    except Exception:
        atomic_write(runtime, original)
        if old_drop is None:
            DROP.unlink(missing_ok=True)
        else:
            atomic_write(DROP, old_drop)
        command('systemctl', 'daemon-reload')
        print('Installation failed; files restored. Navigation left stopped. Network unchanged.', flush=True)
        raise
    print('INSTALLED: IPv4 supported; automatic network modification disabled.')
    print('PHONE: https://safeguard.local:8443/')
    print('Network settings, certificates, main, ESP32, camera and radar files were not changed.')
    print('Phone connectivity still needs verification.')
    time.sleep(2)
    print(command('journalctl', '-u', SERVICE, '-n', '18', '--no-pager'))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STOPPED:', error, file=sys.stderr)
        raise SystemExit(1)
