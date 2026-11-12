#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Assemble pinned Ubuntu Desktop layers and explicit device debs in a container."""
import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from lib.build_root import REPO, WS, fetch, sha256


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def metadata(path):
    fields = subprocess.check_output(
        ['dpkg-deb', '-f', str(path), 'Package', 'Version', 'Architecture'], text=True)
    return dict(line.split(': ', 1) for line in fields.splitlines())


def main():
    from shared_gnome import load as load_shared_gnome
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layers', type=Path, required=True,
                        help='Original ISO casper directory, containing the two pinned squashfs files')
    parser.add_argument('--device-deb', type=Path, action='append', required=True,
                        help='Explicit erhai package from a matching component build; repeat as needed')
    parser.add_argument('--dependency-deb', type=Path, action='append', default=[],
                        help='Explicit arm64/all dependency archive; made available to APT without forcing installation')
    parser.add_argument('--release-repository', type=Path, help='Complete verified release batch retained in the image')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--cache', type=Path, default=WS / 'cache/desktop-rootfs')
    parser.add_argument('--layer-cache', type=Path,
                        help='Read-only mounts of the pinned original layers with layers.json')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--memory-mib', type=int, default=4096,
                        help='Container RAM limit in MiB; total RAM plus swap is limited to twice this value')
    parser.add_argument('--timeout', type=int, default=1800, help='Container assembly limit in seconds')
    args = parser.parse_args()
    shared_gnome = load_shared_gnome()
    if args.jobs < 1 or args.timeout < 1 or args.memory_mib < 512:
        parser.error('--jobs and --timeout must be positive; --memory-mib must be at least 512')
    lock_path = REPO / 'packaging/desktop/source.json'
    lock = json.loads(lock_path.read_text())
    for spec in lock['layers']:
        path = args.layers.resolve() / Path(spec['path']).name
        if sha256(path) != spec['sha256']:
            parser.error(f'{path} is not the pinned original Ubuntu layer')
    layer_cache = args.layer_cache.resolve() if args.layer_cache else None
    if layer_cache:
        if json.loads((layer_cache / 'layers.json').read_text()) != lock['layers']:
            parser.error('layer cache does not match the pinned original Ubuntu layers')
        for name in ('minimal', 'standard'):
            directory = layer_cache / name
            if not directory.is_dir() or not os.path.ismount(directory) or not (
                    os.statvfs(directory).f_flag & os.ST_RDONLY):
                parser.error(f'{directory}: expected a read-only original layer mount')
    gunyahvm = json.loads((REPO / 'packaging/gunyahvm/source.json').read_text())
    gunyahvm_pins = {p['package']: p for p in gunyahvm['packages']}
    selected = {}
    selected_paths = {}
    for path in args.device_deb:
        path = path.resolve()
        info = metadata(path)
        name = info['Package']
        if not (name.startswith('erhai-') or name in shared_gnome or name in ('qcom-npu-runtime', 'qcom-npu-demo-model', 'piano-mesa', 'piano-snap-graphics', 'resources', 'gunyahvm',
                                                     'gunyahvm-runtime', 'gunyahvm-guest-kernel', 'gunyahvm-guest-mesa')) or info['Architecture'] not in ('arm64', 'all'):
            parser.error(f'{path}: expected an arm64/all device or shared application package')
        if name in selected:
            parser.error(f'duplicate package input: {name}')
        selected_paths[name] = path
        digest = sha256(path)
        if name in shared_gnome:
            pin = shared_gnome[name]
            if info['Version'] != pin['version'] or digest != pin['sha256']:
                parser.error(f'{name} differs from the pinned shared GNOME package')
        if name in gunyahvm_pins:
            pin = gunyahvm_pins[name]
            if info['Version'] != pin['version'] or digest != pin['sha256']:
                parser.error(f'{name} differs from the pinned GunyahVM release')
        if name == 'resources':
            resource = json.loads((REPO / 'packaging/resources/source.json').read_text())['binary']
            if info['Version'] != resource['version'] or digest != resource['sha256']:
                parser.error('Resources differs from the pinned shared binary input')
        selected[name] = {'file': path.name, 'sha256': digest, **info}
    if {'erhai-settings', 'erhai-device'} & selected.keys():
        missing = shared_gnome.keys() - selected.keys()
        if missing:
            parser.error('The product image requires all shared GNOME packages: ' + ', '.join(sorted(missing)))
    if {'erhai-apps', 'erhai-device'} & selected.keys():
        missing = gunyahvm_pins.keys() - selected.keys()
        if missing:
            parser.error('The product image requires all GunyahVM packages: ' + ', '.join(sorted(missing)))
    if {'erhai-apps', 'erhai-device'} & selected.keys():
        missing = {'qcom-npu-runtime', 'qcom-npu-demo-model', 'erhai-npu-firmware'} - selected.keys()
        if missing:
            parser.error('The product image requires the NPU runtime and offline demo model: ' + ', '.join(sorted(missing)))
    dependencies = {}
    for path in args.dependency_deb:
        path = path.resolve()
        info = metadata(path)
        if info['Architecture'] not in ('arm64', 'all'):
            parser.error(f'{path}: dependency is not arm64/all')
        if info['Package'] in selected or info['Package'] in dependencies:
            parser.error(f'duplicate package input: {info["Package"]}')
        dependencies[info['Package']] = {'file': path.name, 'sha256': sha256(path), **info}
    batch = None
    if args.release_repository:
        import importlib.util
        spec = importlib.util.spec_from_file_location('release_repository', REPO / 'packaging/mesa/shared/tools/release-repository.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        batch = module.verify(args.release_repository)
        if batch['product'] != 'erhai':
            parser.error('release batch belongs to another product')
        missing = selected.keys() - {row['package'] for row in batch['packages']}
        if missing:
            parser.error('explicit release packages absent from batch: ' + ', '.join(sorted(missing)))
        for row in batch['packages']:
            name = row['package']; path = args.release_repository / row['file']
            existing = selected.get(name) or dependencies.get(name)
            if existing:
                if existing['sha256'] != row['sha256']:
                    parser.error('release batch differs from explicit package: ' + name)
                continue
            info = metadata(path)
            dependencies[name] = {'file': path.name, 'sha256': row['sha256'], **info}
            args.dependency_deb.append(path)
    if {'erhai-apps', 'erhai-device'} & selected.keys():
        for pin in gunyahvm['dependencies']:
            info = dependencies.get(pin['package'])
            if not info or (info['Version'], info['Architecture'], info['sha256']) != (
                    pin['version'], pin['architecture'], pin['sha256']):
                parser.error(f"Missing or mismatched GunyahVM dependency: {pin['package']}")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'repo').mkdir()
    (out / 'native').mkdir()
    if batch:
        shutil.copytree(args.release_repository, out / 'release-repository')
        (out / 'release-repository-id').write_text(batch['id'] + '\n')
    assembly_script = out / 'assemble.local.sh'
    assembly_script.write_bytes((REPO / 'tools/lib/desktop-rootfs.sh').read_bytes())
    shutil.copyfile(REPO / 'packaging/erhai-device-support/tree/usr/sbin/erhai-remove-generic-kernels',
                    out / 'remove-generic-kernels')
    cache = args.cache.resolve()
    runtime = [fetch(p['url'], cache / p['file'], p['sha256'])
               for p in lock['runtime_packages']]
    native = [fetch(p['url'], cache / p['file'], p['sha256'])
              for p in lock['build_host']['packages']]

    # Immutable archive inputs may share an inode with the download/build cache.
    # Inputs on another filesystem fall back to an ordinary file copy.
    def stage(source, destination):
        try:
            os.link(source, destination)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            shutil.copyfile(source, destination)

    for i, path in enumerate(runtime + list(selected_paths.values()) + args.dependency_deb):
        stage(path, out / 'repo' / f'{i:04d}.deb')
    for i, path in enumerate(native):
        stage(path, out / 'native' / f'{i:04d}.deb')
    with (out / 'repo/Packages').open('wb') as index, (out / 'repo-index.log').open('wb') as log:
        run(['dpkg-scanpackages', '--multiversion', '.'], cwd=out / 'repo',
            stdout=index, stderr=log)
    seeds = [f'{name}={info["Version"]}' for name, info in selected.items()]
    seeds += lock['runtime_seeds']
    host_image = lock['build_host']['image']
    image_info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', host_image]))[0]
    if image_info['Architecture'] != lock['build_host']['architecture']:
        parser.error('the assembly container architecture does not match the tool lock')
    inputs = {'integration_commit': subprocess.check_output(
                  ['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
              'integration_dirty': bool(subprocess.check_output(
                  ['git', '-C', str(REPO), 'status', '--porcelain'], text=True)),
              'ubuntu': {'iso': lock['iso'], 'layers': lock['layers']},
              'build_host': lock['build_host'], 'build_host_id': image_info['Id'],
              'shared_application_sources': {'gunyahvm': gunyahvm, 'gnome': shared_gnome},
              'device_packages': selected, 'dependency_packages': dependencies,
              'runtime_packages': lock['runtime_packages'],
              'requested_packages': seeds, 'release_repository': batch}
    (out / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    name = 'erhai-desktop-build-' + uuid.uuid4().hex[:12]
    command = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
               # The rootful Docker daemon does not inherit the caller's user slice.
               '--memory', f'{args.memory_mib}m', '--memory-swap', f'{args.memory_mib * 2}m',
               '--env', 'QEMU_CPU=max,pauth-impdef=on', '--cap-add', 'SYS_ADMIN', '--security-opt', 'apparmor=unconfined',
               '--volume', f'{out}:/work',
               '--volume', f'{args.layers.resolve()}:/layers:ro',
               '--volume', f'{assembly_script}:/assemble:ro',
               host_image, '/bin/bash', '/assemble', str(args.jobs), *seeds]
    if layer_cache:
        options = ['--env', 'ERHAI_LAYER_CACHE=1']
        for layer_name in ('minimal', 'standard'):
            options += ['--volume', f'{layer_cache / layer_name}:/work/{layer_name}:ro']
        command[2:2] = options
    (out / 'build-command.local.json').write_text(json.dumps(command, indent=2) + '\n')
    started = time.monotonic()
    try:
        with (out / 'build.log').open('w') as log:
            run(command, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
    except BaseException:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        raise
    result = {'status': 'OFFLINE_ASSEMBLED_NOT_DEVICE_TESTED',
              'elapsed_seconds': time.monotonic() - started,
              'rootfs_sha256': sha256(out / 'rootfs.squashfs'),
              'scope': 'Official Desktop originals plus APT-installed device/runtime packages; '
                       'no machine data injection, partition activation or hardware validation.'}
    (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
