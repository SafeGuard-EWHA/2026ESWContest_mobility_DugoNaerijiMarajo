"""Private, expiring pairing memory. Never persist a raw location bearer token."""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(value, out)
    os.chmod(temp, 0o600)
    os.replace(temp, path)


class PairingMemory:
    def __init__(self, path, wallclock=time.time):
        self.path = Path(path)
        self.wallclock = wallclock
        self.digest = ''
        self.expires = 0
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            digest = value['sha256']
            expires = float(value['expires'])
            if len(digest) == 64 and all(c in '0123456789abcdef' for c in digest) and expires > wallclock():
                self.digest, self.expires = digest, expires
        except (OSError, ValueError, KeyError, TypeError):
            pass

    @property
    def paired(self):
        return bool(self.digest) and self.wallclock() < self.expires

    def accept(self, token):
        return self.paired and hmac.compare_digest(self.digest, hashlib.sha256(token.encode()).hexdigest())

    def save(self, token):
        self.digest = hashlib.sha256(token.encode()).hexdigest()
        self.expires = self.wallclock() + 7 * 86400
        atomic_json(self.path, {'sha256': self.digest, 'expires': self.expires})

    def clear(self):
        self.digest = ''
        self.expires = 0
        atomic_json(self.path, {'sha256': '', 'expires': 0})
