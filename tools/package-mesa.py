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
    parser.add_argument('--shared-repository', type=Path, required=True, help='Complete standard Mesa release batch')
    parser.add_argument('--release-id', required=True, help='Whole OnePlus release batch identifier')
    parser.add_argument('--release-packages', type=Path, action='append', default=[])
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
    ubuntu = json.loads((REPO / 'packaging/mesa/shared/mesa/ubuntu/source.json').read_text())
    if provenance.get('layout') != 'ubuntu-multiarch' or provenance.get('ubuntu') != ubuntu:
        parser.error('shared package must use the pinned standard Ubuntu cohort')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    recipe = REPO / 'packaging/erhai-mesa'
    version = source['version'] + '+erhai' + (recipe / 'VERSION').read_text().strip()
    stage = output / 'stage'
    control = stage / 'DEBIAN'
    control.mkdir(parents=True)
    (control / 'control').write_text((recipe / 'control').read_text().replace('@VERSION@', version).replace(
        '@PIANO_VERSION@', metadata['Version']))
    helper = (REPO / 'packaging/mesa/shared/mesa/ubuntu/conffile-migration.sh').read_text()
    for name in ('preinst', 'postinst', 'postrm'):
        script = (recipe / name).read_text()
        script = script.replace('set -e\n', 'set -e\n' + helper + '\n' +
            f'retire_mesa_conffile erhai-mesa {version} /etc/ld.so.conf.d/00-erhai-mesa.conf "$@"\n', 1)
        (control / name).write_text(script)
        (control / name).chmod(0o755)
    doc = stage / 'usr/share/doc/erhai-mesa'
    doc.mkdir(parents=True)
    shutil.copy2(REPO / 'packaging/mesa/provenance.json', doc / 'source.json')
    (doc / 'copyright').write_text('Copyright 2026 yzddmr6\nLicense: GPL-2.0-only\n'
                                  'See /usr/share/common-licenses/GPL-2.\n')
    transition = output / f'erhai-mesa_{version}_arm64.deb'
    subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(stage), str(transition)],
                   check=True, env=dict(os.environ, SOURCE_DATE_EPOCH='1794355200', DPKG_DEB_THREADS_MAX=str(os.cpu_count() or 1)))
    shutil.copy2(package, output / package.name)
    import importlib.util
    tool = REPO / 'packaging/mesa/shared/tools/release-repository.py'
    spec = importlib.util.spec_from_file_location('release_repository', tool)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    common = module.verify(args.shared_repository)
    if not any(x['package'] == 'piano-mesa' and x['sha256'] == sha(package) for x in common['packages']):
        parser.error('shared repository does not contain this transition package')
    repository = output / args.release_id
    (repository / 'pool').mkdir(parents=True)
    for row in common['packages']:
        if row['source'] in ('mesa','libdrm') or row['package'] == 'piano-mesa':
            shutil.copyfile(args.shared_repository / row['file'], repository / row['file'])
    shutil.copyfile(transition, repository / 'pool' / transition.name)
    defaults = {'erhai-mesa', 'piano-mesa'}
    for directory in args.release_packages:
        for src in directory.rglob('*.deb'):
            dest = repository / 'pool' / src.name
            if dest.exists() and sha(dest) != sha(src):
                parser.error('conflicting release package')
            shutil.copyfile(src, dest)
            defaults.add(module.metadata(src)['Package'])
    module.inventory(repository, args.release_id, 'erhai', defaults)
    # The verification tool advances independently of immutable driver packages.
    checker = REPO / 'tools/check-host-mesa.py'
    checker_source = json.loads((REPO / 'packaging/mesa/checker-provenance.json').read_text())
    if sha(checker) != checker_source['sha256']:
        parser.error('host Mesa checker differs from its pinned source')
    shutil.copyfile(checker, repository / checker.name)
    (repository / checker.name).chmod(0o755)
    (repository / 'SHA256SUMS').write_text(''.join(
        f'{sha(p)}  {p.relative_to(repository)}\n' for p in sorted(repository.rglob('*'))
        if p.is_file() and p.name != 'SHA256SUMS'))
    module.verify(repository)
    manifest = {'version': version, 'package': {'file': transition.name, 'sha256': sha(transition)},
                'shared_package': {'file': package.name, 'sha256': sha(package)},
                'depends': 'piano-mesa (>= ' + metadata['Version'] + ')', 'repository': repository.name}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
