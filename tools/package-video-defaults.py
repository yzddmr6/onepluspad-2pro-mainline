#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Package removable GStreamer/Firefox defaults without changing the host."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata = REPO / 'packaging/erhai-video-defaults'
    version = (metadata / 'VERSION').read_text().strip()
    # Keep temporary files under the selected output, including on failure.
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        root = Path(temporary) / 'package'
        shutil.copytree(metadata / 'tree', root)
        control = root / 'DEBIAN'
        control.mkdir()
        (control / 'control').write_text(
            (metadata / 'control').read_text().replace('@VERSION@', version))
        doc = root / 'usr/share/doc/erhai-video-defaults'
        doc.mkdir(parents=True)
        shutil.copy2(REPO / 'packaging/iris-vaapi/README.md', doc / 'README.md')
        shutil.copy2(REPO / 'LICENSE', doc / 'copyright')
        deb = output / f'erhai-video-defaults_{version}_all.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', root, deb], check=True)
        print(deb)


if __name__ == '__main__':
    main()
