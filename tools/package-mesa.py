#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Package the verified Freedreno OpenGL and Turnip desktop drivers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
PREFIX = 'usr/lib/erhai/mesa'
SCRIPTS = ('preinst', 'postrm')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if platform.machine() not in ('aarch64', 'arm64'):
        parser.error('package dependency scanning requires the native arm64 build environment')
    build = args.build_output.resolve()
    result = json.loads((build / 'build-result.json').read_text())
    identity = json.loads((build / 'input.json').read_text())
    source = json.loads((REPO / 'packaging/mesa/source.json').read_text())
    if (result['input_sha256'] != sha(build / 'input.json')
            or result['profile'] != 'desktop'
            or result['prefix'] != '/usr/lib/erhai/mesa'
            or identity['source']['sha256'] != source['sha256']
            or identity['source']['version'] != source['version']
            or [p['upstream_commit'] for p in identity['source']['patches']]
            != [p['upstream_commit'] for p in source['patches']]):
        parser.error('unverified or incompatible Mesa build')
    for built, pinned in zip(identity['source']['patches'], source['patches']):
        if built['sha256'] not in [pinned['sha256'], *pinned.get('equivalent_sha256', [])]:
            parser.error('Mesa patch identity does not match the source lock')
    stage = build / 'stage'
    for name, digest in result['files_sha256'].items():
        if sha(stage / name) != digest:
            parser.error('build file changed: ' + name)
    for name, target in result['symlinks'].items():
        if os.readlink(stage / name) != target:
            parser.error('build symlink changed: ' + name)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    metadata = REPO / 'packaging/erhai-mesa'
    recipe = {str(p.relative_to(REPO)): sha(p) for p in sorted(metadata.rglob('*')) if p.is_file()}
    recipe[str(Path(__file__).resolve().relative_to(REPO))] = sha(Path(__file__))
    fingerprint = hashlib.sha256(json.dumps({'build': result, 'recipe': recipe}, sort_keys=True).encode()).hexdigest()
    revision = (metadata / 'VERSION').read_text().strip()
    if not revision.isdigit() or int(revision) < 1:
        parser.error('packaging/erhai-mesa/VERSION must be a positive release counter')
    version = source['version'] + '+erhai' + revision + '.b' + fingerprint[:8]
    with tempfile.TemporaryDirectory(prefix='erhai-mesa-') as temporary:
        work = Path(temporary)
        root = work / 'package'
        shutil.copytree(metadata / 'tree', root)
        prefix = root / PREFIX
        for name in sorted(set(result['files_sha256']) | set(result['symlinks'])):
            # Headers, static libraries and pkg-config files are build inputs,
            # not dependencies of an installed desktop.
            if not (name.startswith(PREFIX + '/lib/') and '.so' in Path(name).name
                    or name.startswith(PREFIX + '/share/vulkan/icd.d/')
                    or name.startswith(PREFIX + '/share/glvnd/')
                    or name.startswith(PREFIX + '/share/drirc.d/')):
                continue
            dst = root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if name in result['symlinks']:
                dst.symlink_to(result['symlinks'][name])
            else:
                shutil.copy2(stage / name, dst)
        icds = list((prefix / 'share/vulkan/icd.d').glob('*.json'))
        if len(icds) != 1:
            parser.error('expected exactly one Turnip ICD')
        icd_dir = root / 'usr/share/vulkan/icd.d'
        icd_dir.mkdir(parents=True)
        (icd_dir / 'freedreno_icd.aarch64.json').symlink_to('/' + str(icds[0].relative_to(root)))
        # Every private path the selection entries name must be in this package.
        for config in sorted((metadata / 'tree').rglob('*')):
            if config.is_file():
                text = config.read_text().replace('$prefix', '/' + PREFIX)
                for path in re.findall(r'/usr/lib/erhai/mesa/[^\s:$"]+', text):
                    if not (root / path.lstrip('/')).exists():
                        parser.error(f'{config.name} names {path}, which is not packaged')
        libraries = [p for p in prefix.rglob('*') if p.is_file() and not p.is_symlink() and '.so' in p.name]
        debian = work / 'debian'
        debian.mkdir()
        (debian / 'control').write_text('Source: erhai-mesa\n\nPackage: erhai-mesa\nArchitecture: arm64\n')
        # Private Mesa libraries have no distribution shlibs records. Their
        # complete closure is shipped here; distro dependencies retain the
        # minimum versions derived by dpkg-shlibdeps from their symbol tables.
        deps = subprocess.check_output(
            ['dpkg-shlibdeps', '-O', '--ignore-missing-info', '-l' + str(prefix / 'lib'),
             *['-e' + str(p) for p in libraries]], cwd=work, text=True).strip()
        if not deps.startswith('shlibs:Depends='):
            raise RuntimeError('dependency scan returned no Depends')
        control = root / 'DEBIAN'
        control.mkdir()
        text = (metadata / 'control').read_text().replace('@VERSION@', version).replace(
            '@DEPENDS@', deps.split('=', 1)[1])
        (control / 'control').write_text(text)
        for name in SCRIPTS:
            shutil.copy2(metadata / name, control / name)
            (control / name).chmod(0o755)
        doc = root / 'usr/share/doc/erhai-mesa'
        doc.mkdir(parents=True)
        shutil.copy2(build / ('mesa-' + source['version']) / 'docs/license.rst', doc / 'copyright')
        provenance = {'version': version, 'build': result, 'source': identity['source'],
                      'recipe_sha256': recipe, 'depends': deps.split('=', 1)[1]}
        (doc / 'build.json').write_text(json.dumps(provenance, indent=2) + '\n')
        (control / 'md5sums').write_text(''.join(
            hashlib.md5(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(root)) + '\n'
            for p in sorted(root.rglob('*'))
            if p.is_file() and not p.is_symlink() and control not in p.parents))
        env = dict(os.environ, SOURCE_DATE_EPOCH=(build / 'source-date-epoch').read_text().strip())
        package = output / ('erhai-mesa_' + version + '_arm64.deb')
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(root), str(package)],
                       env=env, check=True)
        provenance['package'] = {'file': package.name, 'sha256': sha(package)}
        (output / 'manifest.json').write_text(json.dumps(provenance, indent=2) + '\n')
        print(json.dumps(provenance['package']))


if __name__ == '__main__':
    main()
