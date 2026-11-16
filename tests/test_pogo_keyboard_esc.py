#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""The pogo keyboard's Esc key must stay mapped to KEY_ESC.

The cover's physical Esc key reports the consumer usage 0x0224 (AC Back),
not the keyboard usage 0x29.  It once mapped to KEY_BACK, which GNOME
ignores, so the key did nothing.  The regression test keeps 0x0224 on
KEY_ESC, keeps the keyboard usage 0x29 (Esc) on key code 1 (KEY_ESC) in
the hid table and guards the rest of the media table the fix must not
touch.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
DRIVER = REPO / 'kernel/linux/drivers/input/keyboard/oneplus-pogo-keyboard.c'

MEDIA_ENTRY = re.compile(
    r'\{\s*(0x[0-9a-fA-F]+)\s*,\s*(KEY_\w+)\s*(?:,\s*(KEY_\w+)\s*)?\}')
EXPECTED_MEDIA = {
    0x006f: ('KEY_BRIGHTNESSUP', 'KEY_F2'),
    0x0070: ('KEY_BRIGHTNESSDOWN', 'KEY_F1'),
    0x00b5: ('KEY_NEXTSONG', 'KEY_F9'),
    0x00b6: ('KEY_PREVIOUSSONG', 'KEY_F7'),
    0x00cd: ('KEY_PLAYPAUSE', 'KEY_F8'),
    0x00e2: ('KEY_MUTE', 'KEY_F10'),
    0x00e9: ('KEY_VOLUMEUP', 'KEY_F12'),
    0x00ea: ('KEY_VOLUMEDOWN', 'KEY_F11'),
    0x01d0: ('KEY_FN', None),
    0x0224: ('KEY_ESC', None),
    0x0244: ('KEY_APPSELECT', None),
    0x02fa: ('KEY_ASSISTANT', None),
    0x038e: ('KEY_SCREENLOCK', 'KEY_F6'),
    0x0390: ('KEY_LANGUAGE', None),
    0x0391: ('KEY_MICMUTE', 'KEY_F3'),
    0x0392: ('KEY_TOUCHPAD_TOGGLE', 'KEY_F4'),
    0x0393: ('KEY_SEARCH', None),
    0x0394: ('KEY_FULL_SCREEN', None),
    0x0398: ('KEY_PROG1', None),
    0x0399: ('KEY_PROG2', None),
}


def table_body(source, name):
    match = re.search(name + r'\[\w*\]\s*=\s*\{(.*?)\};', source, re.S)
    assert match, f'{name} table not found'
    return match.group(1)


@unittest.skipUnless(DRIVER.is_file(), 'kernel/linux checkout is missing')
class PogoKeyboardEscTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DRIVER.read_text()
        cls.media = {int(usage, 16): (code, fn or None)
                     for usage, code, fn
                     in MEDIA_ENTRY.findall(table_body(cls.source, 'pogo_kb_media_keys'))}
        hid = [int(value) for value in
               re.findall(r'\d+', table_body(cls.source, 'pogo_kb_hid_keys'))]
        assert len(hid) == 256, f'hid table has {len(hid)} entries'
        cls.hid = hid

    def test_esc_media_usage_reports_key_esc(self):
        self.assertEqual(self.media[0x0224], ('KEY_ESC', None))

    def test_esc_keyboard_usage_still_maps_to_key_esc(self):
        self.assertEqual(self.hid[0x29], 1)

    def test_media_table_otherwise_unchanged(self):
        self.assertEqual(self.media, EXPECTED_MEDIA)

    def test_media_key_codes_registered_as_capabilities(self):
        # keybit bits come from the table itself; a media code that is not
        # registered can never reach userspace.
        self.assertIn('__set_bit(pogo_kb_media_keys[i].code, kbd->keybit)',
                      self.source)


if __name__ == '__main__':
    unittest.main()
