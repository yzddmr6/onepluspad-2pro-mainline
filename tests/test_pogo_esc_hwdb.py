#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""erhai-device-support must ship the Bluetooth Esc hwdb remap and apply it.

The cover's Esc key reports consumer usage 0x0224 (AC Back).  Over the
pogo serial link the kernel driver maps it to KEY_ESC; over Bluetooth the
generic HID path produces KEY_BACK instead, which GNOME ignores.  The
package ships a hwdb entry that maps scan code c0224 to esc and marks the
Consumer Control interface as a keyboard so libinput reads it, then
postinst rebuilds the compiled database and re-registers already paired
devices so the fix applies without re-pairing.
"""
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / 'packaging/erhai-device-support'
HWDB = PACKAGE / 'tree/usr/lib/udev/hwdb.d/99-erhai-pogo-esc.hwdb'


class PogoEscHwdbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hwdb = HWDB.read_text()
        cls.postinst = (PACKAGE / 'postinst').read_text()
        cls.postrm = (PACKAGE / 'postrm').read_text()

    def test_hwdb_matches_consumer_control_device(self):
        self.assertIn('evdev:name:OnePlus Pad 2 Pro Keyboard Consumer Control:*', self.hwdb)
        self.assertIn('evdev:input:b0005v22D9p3869*', self.hwdb)

    def test_hwdb_maps_ac_back_to_esc(self):
        self.assertIn('KEYBOARD_KEY_c0224=esc', self.hwdb)

    def test_hwdb_syntax(self):
        modalias = assignment = 0
        for line in self.hwdb.splitlines():
            if not line or line.startswith('#'):
                continue
            if line.startswith((' ', '\t')):
                assignment += 1
            else:
                self.assertTrue(line.startswith('evdev:'), line)
                modalias += 1
        self.assertGreaterEqual(modalias, 1)
        self.assertGreaterEqual(assignment, 1)

    def test_postinst_rebuilds_hwdb_and_reloads_udev(self):
        self.assertIn('systemd-hwdb update', self.postinst)
        self.assertIn('udevadm control --reload', self.postinst)

    def test_postinst_replays_existing_bluetooth_devices(self):
        self.assertIn('/sys/bus/hid/devices/0005:22D9:3869.', self.postinst)
        self.assertIn('event*/uevent', self.postinst)
        self.assertIn('remove', self.postinst)
        self.assertIn('add', self.postinst)

    def test_postrm_drops_compiled_rule(self):
        self.assertIn('systemd-hwdb update', self.postrm)
        self.assertIn('udevadm control --reload', self.postrm)


if __name__ == '__main__':
    unittest.main()
