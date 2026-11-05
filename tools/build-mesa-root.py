#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build and package erhai-mesa on a host that is not ARM64, without root.

    tools/build-mesa-root.py --output <dir> [--work <dir>] [--jobs N] [--clean]

tools/build-mesa.py and tools/package-mesa.py need Ubuntu 26.04 arm64. Here
they run unchanged inside a disposable arm64 build root: the Ubuntu Base and
the archive snapshot pinned in packaging/mesa/build-root.json, entered through
an unprivileged user namespace and run by qemu-user binfmt, in the same way as
tools/build-sensors.py. The Mesa archive and patch stay pinned only in
packaging/mesa/source.json; the archive is downloaded into the cache once and
checked by SHA-256 on every use.

Fresh attempts unpack the pinned source; --resume continues a failed attempt's
frozen compile recipe and compatible objects. Previous package payloads are
never build inputs. The build root is kept in the work
directory for the next run of the same inputs; changed inputs need a new work
directory, and --clean removes it after a successful build. The output holds
the package, its manifest, the build identity and a record of the build root.
"""
import argparse
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / 'packaging/mesa'
# The recipe copied into the build root: exactly what the native build uses.
RECIPE = ('tools/build-mesa.py', 'tools/package-mesa.py', 'packaging/mesa', 'packaging/erhai-mesa',
          'tools/lib/build_root.py', 'LICENSE')
BINFMT = Path('/proc/sys/fs/binfmt_misc/qemu-aarch64')

# Build-root mechanics are shared; neither package builder imports the other.
_spec = importlib.util.spec_from_file_location('erhai_build_root', REPO / 'tools/lib/build_root.py')
root_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(root_tools)
WS = root_tools.WS


def die(message):
    raise SystemExit(f'build-mesa-root: {message}')


def interpreter():
    """The qemu-user binary that runs the build root, for the build record."""
    fields = dict(line.replace(':', '').split(' ', 1) for line in BINFMT.read_text().splitlines()
                  if ' ' in line)
    path = Path(fields['interpreter'].strip()).resolve()
    version = subprocess.run([str(path), '--version'], capture_output=True, text=True).stdout
    return {'path': str(path), 'sha256': root_tools.sha256(path),
            'version': version.splitlines()[0] if version else '', 'flags': fields.get('flags', '').strip()}


def native_nir(build, ninja, log):
    """Execute Mesa's architecture-independent NIR generator with host Python.

    Use a one-target Ninja file so host-side manifest regeneration cannot
    mistake the SDK's pkg-config paths for missing host build dependencies.
    Only the interpreter is replaced with this host's Python (Mesa requires
    Python >= 3.10). Generator arguments and output remain the SDK's rule.
    """
    directory = build / 'out/build'
    target = 'src/compiler/nir/nir_opt_algebraic.c'
    sdk_ninja = json.loads((build / 'out/input.json').read_text())['tools']['ninja']
    native_input = None
    if ninja == 'ninja' and platform.machine() == 'x86_64':
        spec = json.loads((INPUTS / 'native-tools.json').read_text())['ninja']
        if spec['version'] == sdk_ninja:
            cache = WS / 'cache/mesa-native-tools'
            archive = root_tools.fetch(spec['url'], cache / spec['file'], spec['sha256'])
            binary = cache / ('ninja-' + spec['version'])
            if not binary.is_file() or root_tools.sha256(binary) != spec['binary_sha256']:
                contents = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(archive)])
                with tarfile.open(fileobj=io.BytesIO(contents)) as package:
                    binary.write_bytes(package.extractfile('./' + spec['member']).read())
                binary.chmod(0o755)
            if root_tools.sha256(binary) != spec['binary_sha256']:
                die('native Ninja does not match its input manifest')
            ninja, native_input = str(binary), spec
    ninja_version = subprocess.check_output([ninja, '--version'], text=True).strip()
    if ninja_version != sdk_ninja:
        die(f'native Ninja {ninja_version} differs from SDK {sdk_ninja}; '
            'use the same version to preserve command hashes in the build log')
    command = subprocess.check_output([ninja, '-C', str(directory), '-t', 'commands', target],
                                      text=True).strip()
    argv = shlex.split(command)
    if '\n' in command or len(argv) != 4 or not argv[1].endswith('/nir_opt_algebraic.py') \
            or argv[2:] != ['--out', target]:
        die('unexpected NIR generation rule; do not execute it as a native helper')
    if sys.version_info < (3, 10):
        die('the pinned Mesa generator requires host Python >= 3.10')
    sdk_command = command
    python = Path('/usr/bin/python3')
    sdk_python = build.parent / 'usr/bin/python3'
    configured_python = build.parent / argv[0].lstrip('/')
    if sdk_python.resolve() != configured_python.resolve():
        die('the SDK default Python differs from the configured generator interpreter')
    command = shlex.join([str(python), *argv[1:]])
    if command != sdk_command:
        # Both names resolve to the same SDK interpreter. Keep the command
        # identical in both Ninja invocations, otherwise the ARM64 build
        # regenerates this expensive target because its command hash changed.
        rules = directory / 'build.ninja'
        text = rules.read_text()
        old = ' COMMAND = ' + sdk_command + '\n'
        if text.count(old) != 1:
            die('cannot identify the single NIR generator rule')
        rules.write_text(text.replace(old, ' COMMAND = ' + command + '\n'))
    info = json.loads(subprocess.check_output([str(python), '-c',
        'import json,sys,mako,markupsafe; assert sys.version_info >= (3,10); print(json.dumps(dict('
        'python=sys.version,mako=mako.__version__,markupsafe=markupsafe.__version__)))'], text=True))
    info.update(python_sha256=root_tools.sha256(python),
                ninja_sha256=root_tools.sha256(Path(shutil.which(ninja))),
                ninja_version=ninja_version,
                generator_sha256=root_tools.sha256(directory / argv[1]),
                command=command, sdk_command=sdk_command,
                sdk_python_sha256=root_tools.sha256(sdk_python.resolve()),
                native_tool_input=native_input,
                scope='native build-only Python generator; target compilation stays in ARM64 SDK')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ninja', dir=directory) as recipe:
        recipe.write('rule native_nir\n  command = ' + command + '\n'
                     'build ' + target + ': native_nir\n')
        recipe.flush()
        with log.open('a') as output:
            subprocess.run([ninja, '-C', str(directory), '-f', recipe.name, target], check=True,
                           env=dict(os.environ, PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1'),
                           stdout=output, stderr=subprocess.STDOUT)
    info['generated_sha256'] = root_tools.sha256(directory / target)
    (build / 'out/native-generator.json').write_text(json.dumps(info, indent=2) + '\n')
    return info


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory for the package and its records')
    parser.add_argument('--work', type=Path, default=WS / 'out/mesa-root-build')
    parser.add_argument('--cache', type=Path, default=WS / 'cache/mesa')
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--target', choices=('desktop', 'gpu-2404'), default='desktop',
                        help='desktop deb (Ubuntu 26.04) or core24 graphics content snap')
    parser.add_argument('--resume', action='store_true',
                        help='continue this work directory after a failed build; source/flags must match')
    parser.add_argument('--native-nir', action='store_true',
                        help='run the NIR Python generator on the host using its original Ninja command; '
                             'requires Python >= 3.10 and Mako on the host')
    parser.add_argument('--ninja', default='ninja', help='native Ninja executable for --native-nir')
    parser.add_argument('--clean', action='store_true',
                        help='remove the work directory, build root included, after success')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 12:
        parser.error('--jobs must be between 1 and 12, the limit of tools/build-mesa.py')
    if shutil.which('unshare') is None:
        die('unshare is required')
    if not BINFMT.is_file():
        die('arm64 binfmt (qemu-user-static) is required to run the build root')
    if not root_tools.HOST_CA.is_file():
        die(f'{root_tools.HOST_CA} is required for TLS to the snapshot service')

    source = json.loads((INPUTS / 'source.json').read_text())
    content = args.target == 'gpu-2404'
    pinfile = INPUTS / ('build-root-core24.json' if content else 'build-root.json')
    pins = json.loads(pinfile.read_text())
    recipe_names = RECIPE + (('tools/package-mesa-snap.py', 'packaging/mesa-snap') if content else ())
    base = root_tools.fetch(pins['build_root']['url'], WS / 'cache' / pins['build_root']['archive'],
                            pins['build_root']['sha256'])
    archive = root_tools.fetch(source['source_url'], args.cache / source['archive'], source['sha256'])
    bootstrap = [(entry, root_tools.fetch(entry['url'], args.cache / entry['file'], entry['sha256']))
                 for entry in pins.get('build_tools', [])]

    output = args.output.resolve()
    if output.exists():
        die(f'{output} exists; select a new --output')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    with open(work / '.lock', 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = work / 'build.log'
        if not args.resume:
            log.write_text('')
        root = root_tools.prepare_root(work, pins, base, log)
        build = root / 'build'
        if build.exists() and not args.resume:
            shutil.rmtree(build)
        if args.resume:
            if not (build / 'out/input.json').is_file():
                die('--resume requires a configured build from this work directory')
            if (build / 'debs').exists():
                die('packaging already started; use a fresh work directory')
            identity = json.loads((build / 'out/input.json').read_text())
            if identity['source'] != source or identity['profile'] != args.target \
                    or identity['recipe_sha256'] != root_tools.sha256(build / 'recipe/tools/build-mesa.py'):
                die('the frozen compile recipe/source differs from this attempt')
            if root_tools.sha256(build / 'recipe/packaging/mesa' / pinfile.name) != root_tools.sha256(pinfile):
                die('the SDK/tool pins differ from this attempt')
        for name in (() if args.resume else recipe_names):
            path = REPO / name
            if path.is_dir():
                shutil.copytree(path, build / 'recipe' / name,
                                ignore=shutil.ignore_patterns('__pycache__'))
            else:
                (build / 'recipe' / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, build / 'recipe' / name)
        (build / 'inputs').mkdir(exist_ok=True)
        shutil.copyfile(archive, build / 'inputs' / source['archive'])
        for entry, path in (() if args.resume else bootstrap):
            shutil.copyfile(path, build / 'inputs' / entry['file'])
            inside = '/build/inputs/' + entry['file']
            if entry['kind'] == 'deb':
                root_tools.chroot(root, f'dpkg -i {inside}', log=log)
            elif entry['kind'] == 'wheel':
                root_tools.chroot(root, 'rm -rf /opt/erhai-meson\n'
                                 f'python3 -m zipfile -e {inside} /opt/erhai-meson\n'
                                 "printf '%s\\n' '#!/bin/sh' 'PYTHONPATH=/opt/erhai-meson exec python3 -m mesonbuild.mesonmain \"$@\"' > /usr/local/bin/meson\n"
                                 'chmod 755 /usr/local/bin/meson\n', log=log)
            else:
                die('unknown build tool format: ' + entry['kind'])
        print(f'  building Mesa {source["version"]} ({args.target} profile) and packaging it '
              f'under qemu-user; progress in {log}', flush=True)
        packager = 'package-mesa-snap.py' if content else 'package-mesa.py'
        native = None
        if args.native_nir:
            if not args.resume:
                root_tools.chroot(root, (
                    f'python3 -u /build/recipe/tools/build-mesa.py --profile {args.target} '
                    f'--source-archive /build/inputs/{source["archive"]} --output /build/out --configure-only\n'),
                    log=log)
            native = native_nir(build, args.ninja, log)
        root_tools.chroot(root, (
            f'python3 -u /build/recipe/tools/build-mesa.py --profile {args.target} --jobs {args.jobs} '
            f'--source-archive /build/inputs/{source["archive"]} --output /build/out\n'
            f'python3 -u /build/recipe/tools/{packager} --build-output /build/out --output /build/debs\n'),
            log=log)

        installed = root_tools.capture(root, "dpkg-query -W -f='${Package} ${Version}\\n'").splitlines()
        output.mkdir(parents=True)
        manifest = json.loads((build / 'debs/manifest.json').read_text())
        package = build / 'debs' / manifest['package']['file']
        if root_tools.sha256(package) != manifest['package']['sha256']:
            die('the package does not match its manifest')
        for path in (package, build / 'debs/manifest.json', build / 'out/input.json',
                     build / 'out/build-result.json', build / 'out/build/meson-logs/meson-log.txt'):
            shutil.copy2(path, output / path.name)
        # One entry per recipe file, keyed by its repository path.
        frozen = build / 'recipe'
        recipe = {str(path.relative_to(frozen)): root_tools.sha256(path)
                  for name in recipe_names
                  for path in ([frozen / name] if (frozen / name).is_file()
                               else sorted((frozen / name).rglob('*')))
                  if path.is_file() and '__pycache__' not in path.parts}
        recipe['tools/build-mesa-root.py'] = root_tools.sha256(Path(__file__))
        record = {'build_root': pins['build_root'], 'apt_snapshot': pins['apt']['snapshot'],
                  'build_root_pins_sha256': root_tools.sha256(pinfile),
                  'build_tools': pins.get('build_tools', []),
                  'recipe_sha256': recipe, 'interpreter': interpreter(),
                  'build_packages': installed, 'package': manifest['package']}
        if native:
            record['native_generator'] = native
        (output / 'build-root.json').write_text(json.dumps(record, indent=2) + '\n')
        # Keep identified objects for validation; --clean removes the SDK.
    if args.clean:
        shutil.rmtree(work)
    print(json.dumps(manifest['package']))


if __name__ == '__main__':
    main()
