# SPDX-License-Identifier: GPL-2.0-only
"""Exercise ramdisk-only upgrades through the switcher's plain-file backend."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SWITCH = Path(__file__).resolve().parents[1] / 'switch/erhai-switch'
PARTS = ('boot', 'init_boot', 'vendor_boot')


class TripletTest(unittest.TestCase):
    def exercise(self, changed):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            store, devices, commands = base / 'store', base / 'devices', base / 'commands'
            for path in (store / 'ubuntu', store / 'android', devices, commands):
                path.mkdir(parents=True, exist_ok=True)
            # The --dev-dir backend uses only the regular files below; let
            # this regression run without privileges or access to real disks.
            (commands / 'id').write_text('#!/bin/sh\n[ "$1" = -u ] && { echo 0; exit; }\nexec /usr/bin/id "$@"\n')
            (commands / 'id').chmod(0o755)
            battery = devices / 'power_supply/battery'
            battery.mkdir(parents=True)
            (battery / 'type').write_text('Battery\n')
            (battery / 'capacity').write_text('80\n')
            originals = {}
            for kind in ('ubuntu', 'android'):
                sums = []
                for name in PARTS:
                    marker = 'erhai.boot=mainline-dev' if kind == 'ubuntu' else 'android'
                    data = f'{marker} {kind} {name}'.encode().ljust(4096, b'\0')
                    (store / kind / f'{name}.img').write_bytes(data)
                    sums.append(f'{hashlib.sha256(data).hexdigest()}  {name}.img\n')
                    if kind == 'ubuntu':
                        originals[name] = data
                        (devices / f'{name}_a').write_bytes(data)
                (store / kind / 'SHA256SUMS').write_text(''.join(sums))
            if changed:
                (devices / f'{changed}_a').write_bytes(b'old ramdisk'.ljust(4096, b'\0'))
            android_before = {p.name: p.read_bytes() for p in (store / 'android').iterdir()}
            args = ['sh', str(SWITCH), '--slot', '_a', '--store', str(store), '--dev-dir', str(devices)]
            env = {**os.environ, 'PATH': str(commands) + os.pathsep + os.environ['PATH']}
            status = subprocess.run(args + ['status'], env=env, text=True, capture_output=True, check=True)
            self.assertIn('installed now:    ' + ('unknown' if changed else 'ubuntu'), status.stdout)
            result = subprocess.run(args + ['to-ubuntu', '--no-reboot'], env=env, text=True,
                                    capture_output=True, check=True)
            if changed:
                self.assertNotIn('already installed; nothing to write', result.stdout)
            else:
                self.assertIn('already installed; nothing to write', result.stdout)
            for name in PARTS:
                self.assertEqual((devices / f'{name}_a').read_bytes(), originals[name])
            self.assertEqual({p.name: p.read_bytes() for p in (store / 'android').iterdir()}, android_before)

    def test_vendor_ramdisk_only_change_is_written(self):
        self.exercise('vendor_boot')

    def test_generic_ramdisk_only_change_is_written(self):
        self.exercise('init_boot')

    def test_complete_matching_triplet_is_not_rewritten(self):
        self.exercise(None)


if __name__ == '__main__':
    unittest.main()
