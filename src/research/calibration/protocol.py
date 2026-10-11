"""Load the locked study protocol and refuse to run against an altered one.

A protocol only constrains anything if it is fixed before results exist and
cannot drift afterwards. `lock` records the SHA-256 of the YAML with a
timestamp; `load` recomputes the hash and raises if it differs, so an edit made
after seeing a result stops the pipeline instead of quietly changing what the
result means.

    python -m src.research.calibration.protocol lock
    python -m src.research.calibration.protocol show
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src import config

PATH = config.PROJECT_ROOT / 'docs/research/research_protocol.yaml'
LOCK = config.PROJECT_ROOT / 'results/research/protocol_lock.json'


class ProtocolChanged(RuntimeError):
    """The protocol file no longer matches its lock."""


def digest(path=None):
    # Line endings are normalised so a checkout on another platform hashes alike.
    raw = Path(path or PATH).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()


def lock(path=None, lock_path=None, now=None):
    """Record the protocol hash. Refuses to overwrite a lock for the same version."""
    path, lock_path = Path(path or PATH), Path(lock_path or LOCK)
    protocol = yaml.safe_load(path.read_text(encoding='utf-8'))
    current = digest(path)
    history = []
    if lock_path.exists():
        existing = json.loads(lock_path.read_text(encoding='utf-8'))
        if existing['protocol_version'] == protocol['protocol_version']:
            if existing['sha256'] != current:
                raise ProtocolChanged(
                    f"{protocol['protocol_version']} is already locked with a different hash. "
                    'A changed protocol needs a new protocol_version.')
            return existing
        # A new version supersedes the old lock but never erases it.
        history = existing.get('history', []) + [
            {k: existing[k] for k in ('protocol_version', 'sha256', 'locked_at')}]
    record = {
        'protocol_version': protocol['protocol_version'], 'sha256': current,
        'locked_at': (now or datetime.now(timezone.utc)).isoformat(),
        'path': config.portable(path),
        'statement': 'Locked before any model was fitted on the study dataset.',
        'history': history,
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(record, indent=1), encoding='utf-8')
    return record


def load(path=None, lock_path=None, require_lock=True):
    """Return the protocol with its hash, verifying it against the lock."""
    path, lock_path = Path(path or PATH), Path(lock_path or LOCK)
    protocol = yaml.safe_load(path.read_text(encoding='utf-8'))
    current = digest(path)
    if require_lock:
        if not lock_path.exists():
            raise ProtocolChanged('The protocol has not been locked; run the lock command first.')
        record = json.loads(lock_path.read_text(encoding='utf-8'))
        if record['protocol_version'] != protocol['protocol_version'] or record['sha256'] != current:
            raise ProtocolChanged(
                'docs/research/research_protocol.yaml differs from its lock. Results produced under '
                'the locked protocol cannot be mixed with a changed one; create a new protocol_version.')
        protocol['_locked_at'] = record['locked_at']
    protocol['_sha256'] = current
    return protocol


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if command == 'lock':
        print(json.dumps(lock(), indent=1))
    else:
        protocol = load(require_lock=LOCK.exists())
        print(json.dumps({'protocol_version': protocol['protocol_version'], 'sha256': protocol['_sha256'],
                          'locked_at': protocol.get('_locked_at')}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
