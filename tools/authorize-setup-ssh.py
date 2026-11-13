#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add the operator's SSH public key to a copy of an Erhai v2 RAM setup boot image."""
import argparse
import base64
from pathlib import Path
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('public_key', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    fields = args.public_key.read_bytes().strip().split()
    if len(fields) < 2 or fields[0] != b'ssh-ed25519':
        parser.error('expected an OpenSSH Ed25519 public key')
    wire = base64.b64decode(fields[1], validate=True)
    if len(wire) != 51 or wire[:19] != b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20':
        parser.error('invalid Ed25519 public key')
    data = bytearray(args.image.read_bytes())
    if len(data) < 4096 or data[:8] != b'ANDROID!' or struct.unpack_from('<I', data, 40)[0] != 2:
        parser.error('expected an Android boot header v2')
    command = data[64:576].split(b'\x00', 1)[0] + data[608:1632].split(b'\x00', 1)[0]
    words = command.split()
    if b'erhai.debug=1' not in words or not any(w.startswith(b'erhai.rootfs.sha256=') for w in words):
        parser.error('expected an Erhai RAM desktop setup image')
    words = [w for w in words if not w.startswith(b'erhai.setup_key=')]
    command = b' '.join([*words, b'erhai.setup_key=' + fields[1]])
    if len(command) > 1534:
        parser.error('kernel command line exceeds boot header capacity')
    data[64:576] = command[:511].ljust(512, b'\x00')
    data[608:1632] = command[511:].ljust(1024, b'\x00')
    with args.output.open('xb') as output:
        output.write(data)


if __name__ == '__main__':
    main()
