#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Package the erhai-mesa transition together with the common piano-mesa deb."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared-package', type=Path, required=True,
                        help='piano-mesa deb built from packaging/mesa/shared')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package = args.shared_package.resolve()
    fields = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Package', 'Version', 'Architecture'],
                                     text=True)
    metadata = dict(line.split(': ', 1) for line in fields.splitlines())
    if metadata['Package'] != 'piano-mesa' or metadata['Architecture'] != 'arm64':
        parser.error('expected an ARM64 piano-mesa package')
    # Inspect the exact source lock carried by the driver package.
    archive = subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(package)], stdout=subprocess.PIPE)
    import tarfile
    with tarfile.open(fileobj=archive.stdout, mode='r|') as tar:
        provenance = None
        for member in tar:
            if member.name == './usr/share/doc/piano-mesa/build.json':
                provenance = json.load(tar.extractfile(member))
    if archive.wait() or provenance is None:
        parser.error('shared package has no valid provenance')
    source = json.loads((REPO / 'packaging/mesa/shared/mesa/source.json').read_text())
    if provenance['source'] != source:
        parser.error('shared package source differs from the pinned import')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    recipe = REPO / 'packaging/erhai-mesa'
    version = source['version'] + '+erhai' + (recipe / 'VERSION').read_text().strip()
    stage = output / 'stage'
    control = stage / 'DEBIAN'
    control.mkdir(parents=True)
    (control / 'control').write_text((recipe / 'control').read_text().replace('@VERSION@', version).replace(
        '@PIANO_VERSION@', metadata['Version']))
    for name in ('postinst', 'postrm'):
        shutil.copy2(recipe / name, control / name)
        (control / name).chmod(0o755)
    doc = stage / 'usr/share/doc/erhai-mesa'
    doc.mkdir(parents=True)
    shutil.copy2(REPO / 'packaging/mesa/provenance.json', doc / 'source.json')
    (doc / 'copyright').write_text('Copyright 2026 yzddmr6\nLicense: GPL-2.0-only\n'
                                  'See /usr/share/common-licenses/GPL-2.\n')
    transition = output / f'erhai-mesa_{version}_arm64.deb'
    subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(stage), str(transition)],
                   check=True, env=dict(os.environ, DPKG_DEB_THREADS_MAX=str(os.cpu_count() or 1)))
    shutil.copy2(package, output / package.name)
    manifest = {'version': version, 'package': {'file': transition.name, 'sha256': sha(transition)},
                'shared_package': {'file': package.name, 'sha256': sha(package)},
                'depends': 'piano-mesa (>= ' + metadata['Version'] + ')'}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
