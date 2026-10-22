# SPDX-License-Identifier: GPL-2.0-only
"""erhai-firefox: the shipped signing key and the pinned image input."""
import base64
import hashlib
import json
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
TREE = REPO / 'packaging/erhai-firefox/tree'
KEY = Path('/etc/apt/keyrings/packages.mozilla.org.asc')
# Published in Mozilla's instructions for its APT repository.
MOZILLA_FINGERPRINT = '35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3'


def first_key_fingerprint(armored):
    """The v4 fingerprint of the primary key in an ASCII-armored key block."""
    lines = armored.splitlines()
    start = lines.index('-----BEGIN PGP PUBLIC KEY BLOCK-----') + 1
    while lines[start].strip():  # armor headers end at the first empty line
        start += 1
    body = []
    for line in lines[start + 1:]:
        if line.startswith(('=', '-----END')):
            break
        body.append(line.strip())
    data = base64.b64decode(''.join(body))
    header = data[0]
    if header & 0x40:  # new packet format
        tag, first = header & 0x3f, data[1]
        if first < 192:
            length, offset = first, 2
        elif first < 224:
            length, offset = ((first - 192) << 8) + data[2] + 192, 3
        else:
            length, offset = int.from_bytes(data[2:6], 'big'), 6
    else:
        tag, size = (header >> 2) & 0x0f, 1 << (header & 3)
        length, offset = int.from_bytes(data[1:1 + size], 'big'), 1 + size
    packet = data[offset:offset + length]
    if tag != 6 or packet[0] != 4:
        raise ValueError('not a version 4 public key packet')
    return hashlib.sha1(b'\x99' + len(packet).to_bytes(2, 'big') + packet).hexdigest().upper()


class FirefoxSourceTest(unittest.TestCase):
    def test_shipped_key_is_mozillas(self):
        armored = (TREE / KEY.relative_to('/')).read_text()
        self.assertEqual(first_key_fingerprint(armored), MOZILLA_FINGERPRINT)

    def test_source_is_verified_with_the_shipped_key(self):
        source = (TREE / 'etc/apt/sources.list.d/mozilla.sources').read_text()
        self.assertEqual(re.findall(r'^Signed-By: (.+)$', source, re.M), [str(KEY)])
        self.assertIn('URIs: https://packages.mozilla.org/apt\n', source)

    def test_image_installs_the_pinned_mozilla_build(self):
        lock = json.loads((REPO / 'packaging/desktop/source.json').read_text())
        pinned = [p for p in lock['runtime_packages'] if p['package'] == 'firefox']
        self.assertEqual(len(pinned), 1)
        self.assertTrue(pinned[0]['url'].startswith('https://packages.mozilla.org/apt/pool/'))
        self.assertRegex(pinned[0]['sha256'], r'^[0-9a-f]{64}$')
        # Ubuntu's transitional package sorts higher, so only an exact
        # version request selects Mozilla's build in the image.
        self.assertIn(f'firefox={pinned[0]["version"]}', lock['runtime_seeds'])


if __name__ == '__main__':
    unittest.main()
