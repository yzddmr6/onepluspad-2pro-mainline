#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build and test pinned Ubuntu GNOME Settings in a disposable ARM64 chroot."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from lib.build_root import fetch, sha256, HOST_CA, CHROOT_PATH

REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / 'packaging/gnome-control-center'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def prepare(out, lock):
    for item in lock['patches']:
        if sha256(REPO / item['path']) != item['sha256']:
            raise SystemExit('Settings patch differs from source.json: ' + item['path'])
    downloads = out / 'downloads'
    archives = [fetch(lock['base_url'] + name, downloads / name, digest)
                for name, digest in lock['archives'].items()]
    source = out / 'root/build/source'
    source.mkdir(parents=True)
    run('tar', '-xf', str(archives[0]), '--strip-components=1', '-C', str(source))
    run('tar', '-xf', str(archives[1]), '-C', str(source))
    patches = source / 'debian/patches'
    series = patches / 'series'
    names = []
    for item in lock['patches']:
        name = 'erhai-' + Path(item['path']).name
        shutil.copyfile(REPO / item['path'], patches / name)
        names.append(name)
    series.write_text(series.read_text().rstrip() + '\n' + '\n'.join(names) + '\n')
    return source


def build(out, lock, pins, jobs, base_archive):
    base = fetch(pins['build_root']['url'], base_archive or
                 out / 'downloads' / pins['build_root']['archive'], pins['build_root']['sha256'])
    root = out / 'root'
    root.mkdir()
    with tarfile.open(base) as tar:
        members = [m for m in tar.getmembers()
                   if not (m.isdev() or m.name.lstrip('./').startswith('dev/'))]
        tar.extractall(root, members=members, filter='fully_trusted', numeric_owner=True)
    source = prepare(out, lock)
    apt = pins['apt']
    (root / 'etc/apt/sources.list.d/ubuntu.sources').write_text(
        f'Types: deb\nURIs: {apt["uri"]}\nSuites: {" ".join(apt["suites"])}\n'
        f'Components: {" ".join(apt["components"])}\n'
        'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
    (root / 'etc/apt/apt.conf.d/99erhai-build').write_text(
        'APT::Sandbox::User "root";\nAcquire::Check-Valid-Until "false";\n'
        'APT::Install-Recommends "false";\nAcquire::Languages "none";\n'
        'Acquire::https::CaInfo "/etc/apt/erhai-build-ca.crt";\n')
    shutil.copyfile(HOST_CA, root / 'etc/apt/erhai-build-ca.crt')
    resolver = root / 'etc/resolv.conf'
    resolver.unlink(missing_ok=True)
    shutil.copyfile('/etc/resolv.conf', resolver)
    policy = root / 'usr/sbin/policy-rc.d'
    policy.write_text('#!/bin/sh\nexit 101\n')
    policy.chmod(0o755)
    (root / 'dev').mkdir(exist_ok=True)
    script = '''set -eu
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
test "$VERSION_ID" = 26.04
test "$(dpkg --print-architecture)" = arm64
cd /build/source
apt-get update
apt-get install -y build-essential dpkg-dev
apt-get build-dep -y .
export DEB_BUILD_OPTIONS="parallel=$1"
export PYTHONHASHSEED=0
export SOURCE_DATE_EPOCH=$(dpkg-parsechangelog -STimestamp)
dpkg-buildpackage -b -us -uc -j"$1"
dpkg-query -W -f='${binary:Package}\\t${Version}\\n' > /build/build-packages.tsv
'''
    # A private mount/PID namespace releases every bind mount even on failure.
    wrapper = '''set -eu
mount --make-rprivate /
mount --rbind /dev "$1/dev"
mount -t proc proc "$1/proc"
mount -t sysfs -o ro,nosuid,nodev,noexec sysfs "$1/sys"
shift
exec chroot "$@"
'''
    command = ['unshare', '--mount', '--pid', '--fork', '--kill-child',
               '/bin/sh', '-c', wrapper, 'sh', str(root), str(root),
               '/usr/bin/env', '-i', 'PATH=' + CHROOT_PATH, 'HOME=/root',
               'LC_ALL=C.UTF-8', 'QEMU_CPU=max,pauth-impdef=on',
               '/bin/sh', '-s', '--', str(jobs)]
    with (out / 'build.log').open('w') as log:
        run(*command, input=script, text=True, stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, QEMU_CPU='max,pauth-impdef=on'))
    binary = source / 'debian/gnome-control-center/usr/bin/gnome-control-center'
    shutil.copyfile(binary, out / 'gnome-control-center')
    (out / 'gnome-control-center').chmod(0o755)
    shutil.copyfile(root / 'build/build-packages.tsv', out / 'build-packages.tsv')
    for artifact in (root / 'build').iterdir():
        if artifact.suffix in ('.deb', '.ddeb', '.buildinfo', '.changes'):
            shutil.copyfile(artifact, out / artifact.name)
    # Read the compiled resource from the delivered program, not the source UI.
    resources = subprocess.check_output(['gresource', 'list', str(binary)], text=True)
    resource = next(line for line in resources.splitlines() if line.endswith('/cc-about-page.ui'))
    ui = subprocess.check_output(['gresource', 'extract', str(binary), resource])
    if b'author_group' not in ui or b'github.com/yzddmr6/onepluspad-2pro-mainline' not in ui:
        raise SystemExit('The compiled About page is missing the author row')
    (out / 'cc-about-page.ui').write_bytes(ui)
    info = {'source': lock, 'build_root': pins, 'builder_sha256': sha256(__file__),
            'binary_sha256': sha256(out / 'gnome-control-center'),
            'build_packages_sha256': sha256(out / 'build-packages.tsv'),
            'tests': 'dpkg-buildpackage -b (standard Debian tests enabled)'}
    (out / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    print('Built and tested GNOME Settings:', out / 'gnome-control-center', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New build/output directory')
    parser.add_argument('--base-archive', type=Path, help='Cached original Ubuntu Base archive')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('run with sudo; ARM64 binfmt must be configured')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.umask(0o022)
    with (out / '.build.lock').open('w') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            build(out, json.loads((INPUTS / 'source.json').read_text()),
                  json.loads((INPUTS / 'build-root.json').read_text()), args.jobs,
                  args.base_archive.resolve() if args.base_archive else None)
        finally:
            root = out / 'root'
            for name in ('testlog.txt', 'testlog.json', 'meson-log.txt'):
                path = root / 'build/source/obj-aarch64-linux-gnu/meson-logs' / name
                if path.is_file():
                    shutil.copyfile(path, out / name)
            if root.exists():
                shutil.rmtree(root)
            shutil.rmtree(out / 'downloads', ignore_errors=True)
    (out / '.build.lock').unlink()


if __name__ == '__main__':
    main()
