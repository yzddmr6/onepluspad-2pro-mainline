# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the shipped cleanup command without operating on host packages."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'packaging/erhai-device-support/tree/usr/sbin/erhai-remove-generic-kernels'

class CleanupTest(unittest.TestCase):
    def run_cleanup(self, leftover=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = root / 'before'
            before.write_text('ii linux-generic-hwe-26.04\nii linux-image-7.0.0-14-generic\n'
                              'ii linux-modules-7.0.0-14-generic\nii linux-main-modules-zfs-7.0.0-14-generic\n'
                              'rc linux-image-6.17.0-1-generic\nii kdump-tools\n'
                              'ii linux-firmware\nii erhai-kernel-image-current\nii erhai-kernel-image-rollback\n'
                              'ii linux-headers-7.0.0-14\nii linux-image-6.12-custom\n')
            (root / 'dpkg-query').write_text('#!/bin/sh\nif [ ! -f "$CASE_ROOT/removed" ]; then cat "$CASE_ROOT/before"; fi\n')
            (root / 'dpkg').write_text('#!/bin/sh\nexit 0\n')
            (root / 'apt-mark').write_text('#!/bin/sh\nexit 0\n')
            (root / 'apt-get').write_text('#!/bin/sh\nprintf "%s\\n" "$@" >"$CASE_ROOT/args"\n' +
                                         ('' if leftover else 'touch "$CASE_ROOT/removed"\n'))
            for name in ['dpkg-query', 'dpkg', 'apt-mark', 'apt-get']:
                (root / name).chmod(0o755)
            result = subprocess.run(['sh', str(SCRIPT), '--image'], capture_output=True, text=True,
                                    env={**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'],
                                         'CASE_ROOT': str(root)})
            args = (root / 'args').read_text().splitlines()
            self.assertEqual(args[:3], ['--yes', '--purge', 'remove'])
            self.assertEqual(set(args[3:]), {
                'linux-generic-hwe-26.04', 'linux-image-7.0.0-14-generic',
                'linux-modules-7.0.0-14-generic', 'linux-main-modules-zfs-7.0.0-14-generic',
                'linux-image-6.17.0-1-generic', 'kdump-tools'})
            return result

    def test_removes_only_unused_generic_packages(self):
        self.assertEqual(self.run_cleanup().returncode, 0)

    def test_remaining_packages_are_a_failure(self):
        result = self.run_cleanup(leftover=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Generic kernel packages remain', result.stderr)

if __name__ == '__main__':
    unittest.main()
