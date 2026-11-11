# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real file writes at the switcher's failure boundaries."""
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SWITCH = Path(__file__).resolve().parents[1] / 'switch/erhai-switch'
PARTS = ('boot', 'init_boot', 'vendor_boot')


class SwitchFailureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.store, self.dev, self.bin = (root / x for x in ('store', 'dev', 'bin'))
        for path in (self.store, self.dev, self.bin):
            path.mkdir()
        self.wrapper('id', '[ "$1" = -u ] && { echo 0; exit; }; exec /usr/bin/id "$@"')
        self.env = {**os.environ, 'PATH': str(self.bin) + ':' + os.environ['PATH']}
        for kind in ('android', 'ubuntu'):
            directory = self.store / kind
            directory.mkdir()
            for name in PARTS:
                data = (kind + ' ' + name).encode().ljust(4096, b'\0')
                (directory / (name + '.img')).write_bytes(data)
                if kind == 'android':
                    (self.dev / (name + '_a')).write_bytes(data)
            self.sums(kind)
        battery = self.dev / 'power_supply/battery'
        battery.mkdir(parents=True)
        (battery / 'type').write_text('Battery\n')
        (battery / 'capacity').write_text('80\n')
        self.backup = {p.name: p.read_bytes() for p in (self.store / 'android').iterdir()}
        self.original = {p.name: p.read_bytes() for p in self.dev.iterdir() if p.is_file()}

    def tearDown(self):
        self.tmp.cleanup()

    def wrapper(self, name, body):
        p = self.bin / name
        p.write_text('#!/bin/sh\n' + body + '\n')
        p.chmod(0o755)

    def sums(self, kind):
        directory = self.store / kind
        (directory / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256((directory / (n + '.img')).read_bytes()).hexdigest() + '  ' + n + '.img\n'
            for n in PARTS))

    def switch(self, command):
        return subprocess.run(['sh', str(SWITCH), command, '--no-reboot', '--slot', '_a',
                               '--store', str(self.store), '--dev-dir', str(self.dev)],
                              env=self.env, text=True, capture_output=True, timeout=10)

    def test_short_last_image_refused_before_first_write(self):
        (self.store / 'ubuntu/vendor_boot.img').write_bytes(b'short')
        self.sums('ubuntu')
        self.assertNotEqual(self.switch('to-ubuntu').returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in self.dev.iterdir() if p.is_file()}, self.original)

    def test_unknown_mixed_triplet_does_not_replace_backup(self):
        (self.dev / 'vendor_boot_a').write_bytes(b'other'.ljust(4096, b'\0'))
        self.assertNotEqual(self.switch('to-ubuntu').returncode, 0)
        self.assertNotEqual(self.switch('stash-android').returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in (self.store / 'android').iterdir()}, self.backup)

    def test_failed_rollback_keeps_recovery_copy_and_stops(self):
        self.wrapper('dd', 'for arg in "$@"; do case "$arg" in of=*/init_boot_a) echo broken >&2; exit 1;; esac; done; exec /usr/bin/dd "$@"')
        result = self.switch('to-ubuntu')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('rollback-failed', result.stderr)
        self.assertTrue((self.store / '.switch-incomplete').exists())
        self.assertEqual((self.dev / 'boot_a').read_bytes(), self.original['boot_a'])
        self.assertEqual((self.dev / 'vendor_boot_a').read_bytes(), self.original['vendor_boot_a'])
        self.assertNotEqual(self.switch('stash-android').returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in (self.store / 'android').iterdir()}, self.backup)
        self.assertTrue((self.store / '.switch-rollback/boot.img').exists())

    def test_kernel_update_reuses_parent_lock(self):
        import shlex
        source = self.store.parent / 'new-kernel'
        source.mkdir()
        for name in PARTS:
            data = ('erhai.boot=mainline new ' + name).encode().ljust(4096, b'\0')
            (source / (name + '.img')).write_bytes(data)
            (self.dev / (name + '_a')).write_bytes(b'erhai.boot=mainline old'.ljust(4096, b'\0'))
        (source / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256((source / (n + '.img')).read_bytes()).hexdigest() + '  ' + n + '.img\n'
            for n in PARTS))
        self.wrapper('switch-under-test', 'exec sh ' + shlex.join([
            str(SWITCH), '--store', str(self.store), '--dev-dir', str(self.dev), '--slot', '_a']) + ' "$@"')
        result = subprocess.run(['sh', str(SWITCH.with_name('erhai-switch-install-ubuntu-images')), str(source)],
                                env={**self.env, 'ERHAI_SWITCH_STORE': str(self.store),
                                     'ERHAI_SWITCH': str(self.bin / 'switch-under-test')},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in PARTS:
            self.assertEqual((self.dev / (name + '_a')).read_bytes(), (source / (name + '.img')).read_bytes())

    def test_shared_lock_refuses_a_second_writer(self):
        with (self.store / '.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertNotEqual(self.switch('to-ubuntu').returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in self.dev.iterdir() if p.is_file()}, self.original)


if __name__ == '__main__':
    unittest.main()
