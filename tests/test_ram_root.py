# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the initramfs HTTP/hash boundary before any mount or handoff.

RAM_ROOT_SHELL may be a JSON command array, e.g. a qemu-aarch64 invocation
of the pinned ARM64 BusyBox followed by 'sh'. Only mount is substituted;
downloads, chunk assembly and hashing run in the selected real shell.
"""
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class RamRootIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http_dir = tempfile.TemporaryDirectory()
        cls.web = Path(cls.http_dir.name)
        cls.payload = b'root image bytes\n' * 100
        (cls.web / 'root.squashfs').write_bytes(cls.payload)
        parts = cls.web / 'chunked.squashfs.parts'
        parts.mkdir()
        (parts / 'part00').write_bytes(cls.payload[:800])
        (parts / 'part01').write_bytes(cls.payload[800:])
        broken = cls.web / 'truncated.squashfs.parts'
        broken.mkdir()
        (broken / 'part00').write_bytes(cls.payload[:800])
        cls.digest = hashlib.sha256(cls.payload).hexdigest()
        cls.server = http.server.ThreadingHTTPServer(
            ('127.0.0.1', 0), functools.partial(QuietHandler, directory=cls.http_dir.name))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.http_dir.cleanup()

    def fetch(self, filename, digest, mounted):
        source = (REPO / 'initramfs/init-ncm').read_text()
        start = source.index('\tif [ -n "$ROOTFS_URL" ]; then\n')
        end = source.index('\n\tif [ -n "$ROOTFS_URL" ] &&', start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'run/evidence').mkdir(parents=True)
            section = source[start:end].replace('/run/', f'{root}/run/').replace(
                '/newroot', f'{root}/newroot')
            script = root / 'fetch.sh'
            script.write_text('mount() { echo "$*" >> ' +
                              shlex.quote(str(root / 'mounts')) + '; }\n' + section +
                              '\necho RETURNED_TO_INITRAMFS\n')
            shell = json.loads(os.environ.get('RAM_ROOT_SHELL', '["sh"]'))
            result = subprocess.run(shell + [str(script)], capture_output=True,
                                    text=True, timeout=15, env={**os.environ,
                'ROOTFS_URL': f'http://127.0.0.1:{self.server.server_port}/{filename}',
                'ROOTFS_SHA': digest, 'SWITCHROOT': '1'})
            evidence = (root / 'run/evidence/rootfs.txt').read_text()
            self.assertEqual(result.returncode, 0, evidence + result.stderr)
            self.assertIn('RETURNED_TO_INITRAMFS', result.stdout)
            self.assertEqual((root / 'mounts').exists(), mounted, evidence)
            self.assertEqual('SWITCHROOT_PENDING' in evidence, mounted, evidence)
            if mounted:
                self.assertEqual((root / 'run/rootfs.sqfs').read_bytes(), self.payload)
            return evidence

    def test_whole_file_with_matching_hash(self):
        self.fetch('root.squashfs', self.digest, True)

    def test_complete_chunks_with_matching_hash(self):
        self.fetch('chunked.squashfs', self.digest, True)

    def test_wrong_hash_never_reaches_mount(self):
        self.assertIn('SHA256 MISMATCH', self.fetch('root.squashfs', '0' * 64, False))

    def test_missing_chunk_never_reaches_mount(self):
        self.fetch('truncated.squashfs', self.digest, False)

    def test_missing_hash_never_reaches_mount(self):
        self.fetch('root.squashfs', '', False)

    def test_failed_download_never_reaches_mount(self):
        self.fetch('missing.squashfs', self.digest, False)


class CarriedDebugPackageTest(unittest.TestCase):
    """A setup session installs its carried package with the overlay's dpkg.

    mount, umount and chroot are recorded instead of run; the copy, cleanup
    and status handling run in the selected real shell.
    """

    def install(self, dpkg_status):
        source = (REPO / 'initramfs/init-ncm').read_text()
        start = source.index('install_carried_debug() {')
        function = source[start:source.index('\n}\n', start) + 3]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'newroot/run').mkdir(parents=True)
            package = root / 'erhai-debug.deb'
            package.write_bytes(b'package fixture')
            calls = root / 'calls'
            staged = root / 'newroot/run/erhai-setup/erhai-debug.deb'
            stubs = (f'CARRIED_DEBUG={shlex.quote(str(package))}\n'
                     f'mount() {{ echo "mount $*" >> {shlex.quote(str(calls))}; }}\n'
                     f'umount() {{ echo "umount $*" >> {shlex.quote(str(calls))}; }}\n'
                     f'chroot() {{ echo "chroot $*" >> {shlex.quote(str(calls))}; '
                     f'cmp -s {shlex.quote(str(package))} {shlex.quote(str(staged))} || return 9; '
                     f'return {dpkg_status}; }}\n')
            script = root / 'install.sh'
            script.write_text(stubs + function.replace('/newroot', f'{root}/newroot')
                              + 'install_carried_debug\necho "status=$?"\n')
            shell = json.loads(os.environ.get('RAM_ROOT_SHELL', '["sh"]'))
            result = subprocess.run(shell + [str(script)], capture_output=True, text=True,
                                    timeout=15)
            self.assertFalse((root / 'newroot/run/erhai-setup').exists())
            newroot = f'{root}/newroot'
            self.assertEqual(calls.read_text().splitlines(), [
                f'mount -o bind /dev {newroot}/dev',
                f'mount -t proc proc {newroot}/proc',
                f'chroot {newroot} /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin '
                '/usr/bin/dpkg --install /run/erhai-setup/erhai-debug.deb',
                f'umount {newroot}/proc',
                f'umount {newroot}/dev'])
            return result.stdout.strip()

    def test_installed_package_is_reported(self):
        self.assertEqual(self.install(0), 'status=0')

    def test_failed_installation_still_releases_the_overlay(self):
        self.assertEqual(self.install(1), 'status=1')


if __name__ == '__main__':
    unittest.main()
