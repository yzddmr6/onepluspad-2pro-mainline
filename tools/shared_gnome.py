#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify the immutable shared GNOME recipe import and runtime package inputs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'packaging/shared-gnome'


def load():
    provenance = json.loads((ROOT / 'provenance.json').read_text())
    for name, expected in provenance['files_sha256'].items():
        if hashlib.sha256((ROOT / 'shared' / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Shared GNOME import modified: ' + name)
    binaries = json.loads((ROOT / 'binaries.json').read_text())
    if (binaries['source_repository'], binaries['source_commit']) != (provenance['repository'], provenance['commit']):
        raise ValueError('Shared GNOME binary provenance differs from the source import')
    canonical = {}
    manifests = ('power-button-lock.SHA256SUMS', 'mutter/SHA256SUMS')
    for manifest in manifests:
        for line in (ROOT / 'shared/ubuntu' / manifest).read_text().splitlines():
            digest, name = line.split()
            canonical[name] = digest
    packages = binaries['packages']
    if {pin['file']: pin['sha256'] for pin in packages.values()} != canonical:
        raise ValueError('Shared GNOME binary hashes differ from the canonical manifest')
    return packages


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packages', type=Path, help='Verify all shared runtime debs in this directory')
    args = ap.parse_args()
    packages = load()
    if args.packages:
        for name, pin in packages.items():
            path = args.packages / pin['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
                raise ValueError('Shared GNOME binary mismatch: ' + name)
    print(json.dumps(packages, indent=2))


if __name__ == '__main__':
    main()
