#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the KernelSU switch module from the same script used by Ubuntu."""
import argparse
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('out/erhai-switch-v0.2.2.zip'))
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
    source = root / 'switch/ksu-module'
    for path in sorted(source.rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(source))
    archive.write(root / 'switch/erhai-switch', 'erhai-switch')
print(args.output)
