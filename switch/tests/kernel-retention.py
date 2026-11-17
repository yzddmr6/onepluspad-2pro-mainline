#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the real image installer and APT parser using temporary file stores."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / 'switch/erhai-switch-install-ubuntu-images'
RETENTION = REPO / 'packaging/erhai-device-support/tree/usr/libexec/erhai-kernel-retention'


def run(*args):
    subprocess.run(list(map(str, args)), check=True)


def check(root):
    conf = REPO / 'packaging/erhai-device-support/tree/usr/lib/tmpfiles.d/erhai-kernel-retention.conf'
    run('systemd-tmpfiles', '--root', root, '--create', conf)
    policy = (root / 'etc/apt/apt.conf.d/90-erhai-kernel-retention').read_text()
    assert os.uname().release in policy, policy
    assert 'ubuntu.prev' not in policy


def main():
    if os.getuid() != 0:
        raise SystemExit('Run as root or in a root-mapped user namespace; only temporary files are changed')
    with tempfile.TemporaryDirectory(prefix='erhai-retention-test-') as temporary:
        root = Path(temporary)
        store = root / 'var/lib/erhai/switch'
        releases = ['7.2.0-erhai-a', '7.2.0-erhai-b', '7.2.0-erhai-c']
        for release in releases:
            source = root / 'usr/lib/erhai/boot' / release
            source.mkdir(parents=True)
            sums = []
            for name in ('boot', 'init_boot', 'vendor_boot'):
                payload = (release + name).encode()
                (source / (name + '.img')).write_bytes(payload)
                sums.append(hashlib.sha256(payload).hexdigest() + '  ' + name + '.img\n')
            (source / 'SHA256SUMS').write_text(''.join(sums))
            (source / 'meta.json').write_text(json.dumps({'kernel_release': release, 'package': 'erhai-kernel-image-' + release}))
            run('sh', INSTALLER, source, '--store', store, '--no-activate')
            identity = json.loads((store / 'ubuntu/kernel.json').read_text())
            assert identity['kernel_release'] == release
            assert 'kernel_release' not in json.loads((store / 'ubuntu/meta.json').read_text())
        check(root)
        # Reinstalling the archived previous set must preserve its identity
        # before rotating the directory from which it was read.
        run('sh', INSTALLER, store / 'ubuntu.prev', '--store', store, '--no-activate')
        assert json.loads((store / 'ubuntu/kernel.json').read_text())['kernel_release'] == releases[1]
    print('KERNEL_RETENTION_INSTALLER_AND_APT_PASS')


if __name__ == '__main__':
    main()
