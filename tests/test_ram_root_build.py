# SPDX-License-Identifier: GPL-2.0-only
"""RAM desktop images must identify their root independently of old outputs."""
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('ram_boot', TOOLS / 'build-mainline-boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class RamRootBuildTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.image = self.root / 'root.squashfs'
        self.image.write_bytes(b'explicit root input')
        self.url = 'http://192.0.2.1:8000/desktop.squashfs'
        self.output = self.root / 'boot'

    def invoke(self, *args):
        with patch.object(sys, 'argv', [str(TOOLS / 'build-mainline-boot.py'),
                          '--output', str(self.output), *args]):
            boot.main()

    def rejected(self, *args):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke(*args)
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_desktop_has_no_implicit_root(self):
        self.rejected('--profile', 'desktop')

    def test_both_file_and_url_are_required(self):
        self.rejected('--profile', 'desktop', '--rootfs', str(self.image))
        self.rejected('--profile', 'desktop', '--rootfs-url', self.url)

    def test_installed_profile_does_not_accept_a_ram_root(self):
        self.rejected('--profile', 'persistent', '--rootfs', str(self.image),
                      '--rootfs-url', self.url)

    def test_extra_cmdline_cannot_replace_the_identified_root(self):
        for extra in ('erhai.rootfs=http://other/root', 'erhai.rootfs.sha256=wrong',
                      'erhai.root=PARTLABEL=other'):
            with self.subTest(extra=extra):
                self.rejected('--profile', 'desktop', '--rootfs', str(self.image),
                              '--rootfs-url', self.url, '--cmdline-extra', extra)

    def test_url_cannot_insert_a_kernel_argument(self):
        self.rejected('--profile', 'desktop', '--rootfs', str(self.image),
                      '--rootfs-url', self.url + ' erhai.root=/dev/other')

    def test_packer_and_manifest_identify_the_same_root(self):
        image = self.root / 'arch/arm64/boot/Image'
        image.parent.mkdir(parents=True)
        image.write_bytes(b'kernel fixture')
        dtb = self.root / 'board.dtb'
        dtb.write_bytes(b'dtb fixture')
        ramdisk = self.root / 'initramfs'
        ramdisk.write_bytes(b'ramdisk fixture')
        calls = []

        def run(command, **kwargs):
            if command[0] == 'git':
                return subprocess.CompletedProcess(command, 0,
                    stdout='commit\n' if command[-1] == 'HEAD' else '')
            calls.append(command)
            Path(command[command.index('--output') + 1]).write_bytes(b'boot fixture')
            return subprocess.CompletedProcess(command, 0)

        with patch.object(boot.subprocess, 'run', side_effect=run), \
                patch.object(boot, 'sink_layout', return_value='none'), \
                contextlib.redirect_stdout(io.StringIO()):
            self.invoke('--profile', 'desktop', '--rootfs', str(self.image),
                        '--rootfs-url', self.url, '--kernel-out', str(self.root),
                        '--dtb', str(dtb), '--initramfs', str(ramdisk))
        expected = hashlib.sha256(self.image.read_bytes()).hexdigest()
        manifest = json.loads((self.output / 'manifest.json').read_text())
        self.assertEqual(manifest['ram_rootfs'], {'url': self.url, 'sha256': expected})
        cmdline = calls[0][calls[0].index('--cmdline') + 1]
        self.assertEqual(manifest['cmdline'], cmdline)
        self.assertIn('erhai.rootfs.sha256=' + expected, cmdline.split())
        self.assertIn('erhai.rootfs=' + self.url, cmdline.split())
        self.assertIn('erhai.watchdog=900', cmdline.split())
        self.assertIn('erhai.session=5400', cmdline.split())

    def package(self, name):
        deb = self.root / f'{name}.deb'
        deb.write_bytes(b'diagnostics package fixture')
        return deb

    def test_debug_package_needs_a_ram_desktop(self):
        self.rejected('--debug-package', str(self.package('erhai-debug')))

    def test_only_the_diagnostics_package_is_carried(self):
        deb = self.package('erhai-device')
        with patch.object(boot.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [], 0, stdout='Package: erhai-device\nVersion: 1\n')):
            self.rejected('--profile', 'desktop', '--rootfs', str(self.image),
                          '--rootfs-url', self.url, '--debug-package', str(deb))

    @unittest.skipUnless(shutil.which('cpio'), 'needs cpio to read the archive independently')
    def test_setup_ramdisk_appends_the_diagnostics_package(self):
        image = self.root / 'arch/arm64/boot/Image'
        image.parent.mkdir(parents=True)
        image.write_bytes(b'kernel fixture')
        dtb = self.root / 'board.dtb'
        dtb.write_bytes(b'dtb fixture')
        initramfs = self.root / 'initramfs'
        initramfs.write_bytes(gzip.compress(b'shared initramfs fixture'))
        deb = self.package('erhai-debug')
        calls = []

        def run(command, **kwargs):
            if command[0] == 'git':
                return subprocess.CompletedProcess(command, 0,
                    stdout='commit\n' if command[-1] == 'HEAD' else '')
            if command[0] == 'dpkg-deb':
                return subprocess.CompletedProcess(
                    command, 0, stdout='Package: erhai-debug\nVersion: 0.3.0+b1\n')
            calls.append((command, Path(command[command.index('--ramdisk') + 1]).read_bytes()))
            Path(command[command.index('--output') + 1]).write_bytes(b'boot fixture')
            return subprocess.CompletedProcess(command, 0)

        with patch.object(boot.subprocess, 'run', side_effect=run), \
                patch.object(boot, 'sink_layout', return_value='none'), \
                contextlib.redirect_stdout(io.StringIO()):
            self.invoke('--profile', 'desktop', '--rootfs', str(self.image),
                        '--rootfs-url', self.url, '--kernel-out', str(self.root),
                        '--dtb', str(dtb), '--initramfs', str(initramfs),
                        '--debug-package', str(deb), '--cmdline-extra', 'erhai.session=1800')
        command, ramdisk = calls[0]
        shared = initramfs.read_bytes()
        self.assertEqual(ramdisk[:len(shared)], shared)
        archive = gzip.decompress(ramdisk[len(shared):])
        listing = subprocess.run(['cpio', '-it', '--quiet'], input=archive,
                                 capture_output=True, check=True).stdout.decode().split()
        self.assertEqual(listing[-1], 'usr/lib/erhai/debug/erhai-debug.deb')
        carried = subprocess.run(['cpio', '-i', '--to-stdout', '--quiet', listing[-1]],
                                 input=archive, capture_output=True, check=True).stdout
        self.assertEqual(carried, deb.read_bytes())
        cmdline = command[command.index('--cmdline') + 1].split()
        self.assertEqual(cmdline.count('erhai.debug=1'), 1)
        manifest = json.loads((self.output / 'manifest.json').read_text())
        self.assertEqual(manifest['debug_package']['version'], '0.3.0+b1')
        self.assertEqual(manifest['inputs_sha256']['erhai-debug.deb'],
                         hashlib.sha256(deb.read_bytes()).hexdigest())
        self.assertEqual(manifest['inputs_sha256']['initramfs.cpio.gz'],
                         hashlib.sha256(shared).hexdigest())
        self.assertEqual(sorted(p.name for p in self.output.iterdir()),
                         ['boot-mainline.img', 'manifest.json'])


if __name__ == '__main__':
    unittest.main()
