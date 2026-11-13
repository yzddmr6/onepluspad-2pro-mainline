#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""The keyboard cover's Bluetooth touchpad must stay a clickpad.

The cover carries a clickpad: one mechanical button under the touch
surface. Over Bluetooth its HID descriptor advertises a plain touchpad
with BTN_LEFT and BTN_RIGHT instead of INPUT_PROP_BUTTONPAD, so
libinput never pins the pressing finger at button press. A second
finger landing during a held click is swallowed by the two-finger
gesture state machine and click-and-drag produces no pointer motion
at all. The quirk below marks the device a buttonpad so libinput pins
the pressing finger and the drag works like on every other clickpad.

The regression test keeps the quirk scoped to the Bluetooth twin (the
pogo-serial device already sets INPUT_PROP_BUTTONPAD in the kernel
driver), keeps BTN_LEFT which clickpads need as the click indicator,
and keeps BTN_RIGHT dropped.
"""
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
QUIRKS = (REPO / 'packaging/erhai-device-support/tree/usr/share/libinput'
          / '31-erhai-pogo-keyboard.quirks')


def section(source, name):
    for block in source.split('['):
        if block.startswith(name + ']'):
            return block
    raise AssertionError(f'quirk section [{name}] not found')


class PogoKeyboardTouchpadQuirksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert QUIRKS.is_file(), f'{QUIRKS} is missing'
        cls.body = section(QUIRKS.read_text(),
                           'OnePlus Pad 2 Pro Keyboard Touchpad')

    def test_matches_bluetooth_touchpad(self):
        self.assertIn('MatchName=OnePlus Pad 2 Pro Keyboard Touchpad',
                      self.body)
        self.assertIn('MatchBus=bluetooth', self.body)
        self.assertIn('MatchVendor=0x22D9', self.body)
        self.assertIn('MatchProduct=0x3869', self.body)
        self.assertIn('MatchUdevType=touchpad', self.body)

    def test_reports_buttonpad(self):
        self.assertIn('AttrInputProp=+INPUT_PROP_BUTTONPAD', self.body)

    def test_drops_bogus_right_button(self):
        self.assertIn('AttrEventCode=-BTN_RIGHT', self.body)

    def test_keeps_left_click_indicator(self):
        self.assertNotIn('-BTN_LEFT', self.body)


if __name__ == '__main__':
    unittest.main()
