# SPDX-License-Identifier: GPL-2.0-only
"""Test the original Ubuntu input boundary."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
spec = importlib.util.spec_from_file_location('desktop_rootfs', REPO / 'tools/build-desktop-rootfs.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DesktopRootTest(unittest.TestCase):
    def test_modified_layer_stops_before_output_or_container(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'minimal.squashfs').write_bytes(b'not the official Desktop layer')
            output = base / 'output'
            argv = ['build-desktop-rootfs.py', '--layers', str(base),
                    '--device-deb', 'unused.deb', '--output', str(output)]
            with mock.patch.object(sys, 'argv', argv), \
                 mock.patch.object(builder, 'run') as command, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr, \
                 self.assertRaises(SystemExit) as raised:
                builder.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertIn('not the pinned original Ubuntu layer', stderr.getvalue())
            command.assert_not_called()
            self.assertFalse(output.exists())


    def test_cache_requires_matching_pins_and_read_only_mounts(self):
        lock = json.loads((REPO / 'packaging/desktop/source.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cache = base / 'cache'
            cache.mkdir()
            for name in ('minimal', 'standard'):
                (cache / name).mkdir()
            output = base / 'output'
            argv = ['build-desktop-rootfs.py', '--layers', str(base),
                    '--layer-cache', str(cache), '--device-deb', 'unused.deb',
                    '--output', str(output)]
            pins = {Path(s['path']).name: s['sha256'] for s in lock['layers']}
            for manifest, error in (([], 'does not match'),
                                    (lock['layers'], 'read-only original layer mount')):
                (cache / 'layers.json').write_text(json.dumps(manifest))
                with mock.patch.object(sys, 'argv', argv), \
                     mock.patch.object(builder, 'sha256', side_effect=lambda p: pins[p.name]), \
                     mock.patch.object(builder, 'run') as command, \
                     contextlib.redirect_stderr(io.StringIO()) as stderr, \
                     self.assertRaises(SystemExit) as raised:
                    builder.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn(error, stderr.getvalue())
                command.assert_not_called()
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
