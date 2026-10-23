#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the erhai-sensors package from pinned inputs, without root.

    tools/build-sensors.py --output <dir> [--work <dir>] [--jobs N] [--clean]

Every input is named in packaging/sensors/: sources.json pins the Ubuntu Base
build root, the archive snapshot the build dependencies come from, the three
source archives and the patches; rom-config.json pins the stock sensor
configuration. Archives are downloaded into cache/sensors/ once and checked by
SHA-256 on every use. Nothing is taken from a previous build's output.

The binaries have to link against Ubuntu 26.04 arm64, so they are built in a
disposable arm64 chroot unpacked from the pinned Ubuntu Base, entered through
an unprivileged user namespace and run by qemu-user binfmt. No sudo is needed
and the host's own packages are not involved. The chroot is kept in the work
directory for the next build of the same inputs; changed inputs need a new
work directory, and --clean removes it after a successful build.

Only the host CA bundle crosses into the chroot, for TLS to the snapshot
service; package integrity is still checked against the archive keyring of the
pinned build root.
"""
import argparse
import calendar
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('erhai_build_root', REPO / 'tools/lib/build_root.py')
roots = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(roots)
WS, HOST_CA = roots.WS, roots.HOST_CA
sha256, fetch = roots.sha256, roots.fetch
chroot, capture, prepare_root = roots.chroot, roots.capture, roots.prepare_root

INPUTS = REPO / 'packaging/sensors'
PACKAGE = REPO / 'packaging/erhai-sensors'
PREFIX = 'usr/lib/erhai/sensors'
RPCD_ROOT = 'usr/share/erhai-sensors/hexagonrpcd'
STATE = '/var/lib/erhai/sensors'
MAINTAINER = 'yzddmr6 <46088090+yzddmr6@users.noreply.github.com>'
# What the package takes from the staged installs. Headers, pkg-config files,
# the CHRE client, the mock SSC server and the proxy's own unit, rules and
# D-Bus policy are build by-products: Ubuntu's iio-sensor-proxy keeps owning
# the latter.
PAYLOAD = ('bin/hexagonrpcd', 'bin/ssccli', 'libexec/iio-sensor-proxy')
LIBRARIES = ('libhexagonrpc.so.', 'libssc.so.')


def die(message):
    raise SystemExit(f'build-sensors: {message}')


def verify_recipe(lock, rom):
    for source in lock['sources']:
        for patch in source['patches']:
            if sha256(INPUTS / patch['file']) != patch['sha256']:
                die(f'{patch["file"]} does not match the pinned SHA-256')
    listed = set()
    for entry in rom['files']:
        path = INPUTS / entry['file']
        if not path.is_file() or path.stat().st_size != entry['size'] or sha256(path) != entry['sha256']:
            die(f'{entry["file"]} does not match rom-config.json')
        listed.add(path)
    stray = sorted(str(p.relative_to(INPUTS)) for p in (INPUTS / 'rom').rglob('*')
                   if p.is_file() and p not in listed)
    if stray:
        die(f'packaging/sensors/rom holds files rom-config.json does not list: {stray}')


BUILD = r'''
src=/build/src
stage=/build/stage
# A previous build's libssc in the build root must not satisfy this one.
rm -rf /build/tree "$stage" /@PREFIX@
mkdir -p /build/tree "$stage"
unpack() { tar -xf "$src/$1" -C /build/tree; }
apply() { local dir=$1; shift; for p in "$@"; do patch -d "/build/tree/$dir" -p1 --batch --fuzz=0 -i "$src/patches/$p"; done; }
setup() {
	meson setup "$1" "$2" --prefix=/@PREFIX@ --libdir=lib --bindir=bin \
		--libexecdir=libexec --buildtype=release --wrap-mode=nofallback \
		-Dc_link_args=-Wl,-rpath,/@PREFIX@/lib "${@:3}"
}

# hexagonrpc: the FastRPC file server and its client library
unpack @HEX_ARCHIVE@
apply @HEX_DIR@ @HEX_PATCHES@
setup /build/hex /build/tree/@HEX_DIR@
meson compile -C /build/hex -j @JOBS@
meson test -C /build/hex --print-errorlogs
meson install -C /build/hex --no-rebuild --destdir "$stage"

# libssc: installed into the build root as well, for iio-sensor-proxy's
# pkg-config lookup; the build root is disposable.
unpack @SSC_ARCHIVE@
apply @SSC_DIR@ @SSC_PATCHES@
setup /build/ssc /build/tree/@SSC_DIR@
meson compile -C /build/ssc -j @JOBS@
# Only the request-encoding test: the others need the mock SSC server.
/build/ssc/tests/tests-delivery
meson install -C /build/ssc --no-rebuild
meson install -C /build/ssc --no-rebuild --destdir "$stage"

# iio-sensor-proxy with SSC support; its unit, rules and policy stay unused
unpack @ISP_ARCHIVE@
apply @ISP_DIR@ @ISP_PATCHES@
PKG_CONFIG_PATH=/@PREFIX@/lib/pkgconfig setup /build/isp /build/tree/@ISP_DIR@ \
	-Dssc-support=enabled -Dudevrulesdir=/@PREFIX@/unused/udev \
	-Dsystemdsystemunitdir=/@PREFIX@/unused/systemd
meson compile -C /build/isp -j @JOBS@
meson install -C /build/isp --no-rebuild --destdir "$stage"
'''


def build(root, lock, archives, jobs, epoch, log):
    build_dir = root / 'build'
    if build_dir.exists():
        shutil.rmtree(build_dir)
    (build_dir / 'src/patches').mkdir(parents=True)
    for source in lock['sources']:
        shutil.copyfile(archives[source['name']], build_dir / 'src' / source['archive'])
        for patch in source['patches']:
            shutil.copyfile(INPUTS / patch['file'],
                            build_dir / 'src/patches' / Path(patch['file']).name)
    by_name = {s['name']: s for s in lock['sources']}
    script = BUILD
    for key, name in (('HEX', 'hexagonrpc'), ('SSC', 'libssc'), ('ISP', 'iio-sensor-proxy')):
        source = by_name[name]
        script = script.replace(f'@{key}_ARCHIVE@', source['archive'])
        script = script.replace(f'@{key}_DIR@', source['directory'])
        script = script.replace(f'@{key}_PATCHES@',
                                ' '.join(Path(p['file']).name for p in source['patches']))
    script = script.replace('@PREFIX@', PREFIX).replace('@JOBS@', str(jobs))
    flags = '-O2 -g0 -ffile-prefix-map=/build/tree=. -ffile-prefix-map=/build=.'
    print('  building hexagonrpc, libssc and iio-sensor-proxy', flush=True)
    chroot(root, script, env={'SOURCE_DATE_EPOCH': str(epoch), 'CFLAGS': flags}, log=log)
    return build_dir / 'stage'


def stage_package(stage, work, rom, lock, recipe):
    """Assemble the package root from the tree, the staged binaries and the ROM config."""
    pkg = work / 'package'
    if pkg.exists():
        shutil.rmtree(pkg)
    for entry in sorted((PACKAGE / 'tree').rglob('*')):
        if entry.is_dir() or '__pycache__' in entry.parts:
            continue
        if entry.is_symlink():
            die(f'packaging tree carries a symlink: {entry}')
        target = pkg / entry.relative_to(PACKAGE / 'tree')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(entry, target)
        target.chmod(0o755 if entry.stat().st_mode & 0o100 else 0o644)
    prefix = stage / PREFIX
    for name in PAYLOAD:
        target = pkg / PREFIX / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(prefix / name, target)
        target.chmod(0o755)
    (pkg / PREFIX / 'lib').mkdir(parents=True, exist_ok=True)
    for library in sorted((prefix / 'lib').iterdir()):
        if not library.name.startswith(LIBRARIES):
            continue
        target = pkg / PREFIX / 'lib' / library.name
        if library.is_symlink():
            target.symlink_to(os.readlink(library))
        else:
            shutil.copyfile(library, target)
            target.chmod(0o644)
    served = pkg / RPCD_ROOT
    for entry in rom['files']:
        target = served / entry['install']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(INPUTS / entry['file'], target)
        target.chmod(0o644)
    # Machine data stays in /var/lib; the served tree only points at it.
    for link, target in (('sensors/registry', f'{STATE}/persist/registry'),
                         ('sensors/sns_reg_version', f'{STATE}/persist/sns_reg_version'),
                         ('socinfo', f'{STATE}/socinfo')):
        (served / link).symlink_to(target)
    doc = pkg / 'usr/share/doc/erhai-sensors'
    doc.mkdir(parents=True)
    (doc / 'copyright').write_text(
        'erhai-sensors bundles unmodified or patched builds of:\n'
        + ''.join(f'  {s["name"]} {s["version"]}  {s["url"]}  ({s["license"]})\n'
                  for s in lock['sources'])
        + '\nThe applied patches and the exact source hashes are listed in build.json and\n'
        'kept in packaging/sensors/ of the OnePlus Pad 2 Pro mainline integration\n'
        'repository. The files under /usr/share/erhai-sensors/hexagonrpcd/sensors are\n'
        f'unmodified stock sensor configuration of the OnePlus firmware {rom["release"]}.\n'
        '\nOn Debian and Ubuntu systems the complete text of the GNU General Public\n'
        'License version 3 is in /usr/share/common-licenses/GPL-3.\n')
    (doc / 'build.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return pkg


def tree_digest(root):
    digest = hashlib.sha256()
    for entry in sorted(root.rglob('*')):
        relative = entry.relative_to(root).as_posix()
        if entry.is_symlink():
            digest.update(f'l {relative} {os.readlink(entry)}\n'.encode())
        elif entry.is_dir():
            digest.update(f'd {relative}\n'.encode())
        else:
            digest.update(f'f {relative} {entry.stat().st_mode & 0o777:o} {sha256(entry)}\n'.encode())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=WS / 'out/erhai-sensors-candidate')
    parser.add_argument('--work', type=Path, default=WS / 'out/sensors-build')
    parser.add_argument('--cache', type=Path, default=WS / 'cache/sensors')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--clean', action='store_true',
                        help='remove the work directory, build root included, after success')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 12:
        parser.error('--jobs must be between 1 and 12')
    for tool in ('unshare', 'dpkg-deb'):
        if shutil.which(tool) is None:
            die(f'{tool} is required')
    if not Path('/proc/sys/fs/binfmt_misc/qemu-aarch64').is_file():
        die('arm64 binfmt (qemu-user-static) is required to run the build root')
    if not HOST_CA.is_file():
        die(f'{HOST_CA} is required for TLS to the snapshot service')

    lock = json.loads((INPUTS / 'sources.json').read_text())
    rom = json.loads((INPUTS / 'rom-config.json').read_text())
    verify_recipe(lock, rom)
    base = WS / 'cache' / lock['build_root']['archive']
    fetch(lock['build_root']['url'], base, lock['build_root']['sha256'])
    archives = {s['name']: fetch(s['url'], args.cache / s['archive'], s['sha256'])
                for s in lock['sources']}

    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    with open(work / '.lock', 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = work / 'build.log'
        log.write_text('')
        root = prepare_root(work, lock, base, log)
        # The snapshot instant is the newest input, and it is fixed.
        epoch = calendar.timegm(time.strptime(lock['apt']['snapshot'], '%Y%m%dT%H%M%SZ'))
        stage = build(root, lock, archives, args.jobs, epoch, log)

        installed = capture(root, "dpkg-query -W -f='${Package} ${Version}\\n'").splitlines()
        # The ROM files are covered by rom-config.json, which pins each of them.
        recipe_files = {str(p.relative_to(REPO)): sha256(p)
                        for p in sorted([*INPUTS.rglob('*'), *PACKAGE.rglob('*')])
                        if p.is_file() and '__pycache__' not in p.parts
                        and (INPUTS / 'rom') not in p.parents}
        recipe_files['tools/build-sensors.py'] = sha256(Path(__file__))
        recipe_files['tools/lib/build_root.py'] = sha256(REPO / 'tools/lib/build_root.py')
        recipe = {'sources': [{k: s[k] for k in ('name', 'version', 'url', 'sha256', 'upstream_commit')}
                              | {'patches': [{'file': p['file'], 'sha256': p['sha256']} for p in s['patches']]}
                              for s in lock['sources']],
                  'build_root': lock['build_root'], 'apt_snapshot': lock['apt']['snapshot'],
                  'build_packages': installed, 'recipe_sha256': recipe_files,
                  'rom_release': rom['release']}
        pkg = stage_package(stage, work, rom, lock, recipe)

        # Dependencies of the private binaries, derived from their symbols by
        # the build root's own dpkg-shlibdeps against Ubuntu 26.04.
        scan = root / 'build/scan'
        if scan.exists():
            shutil.rmtree(scan)
        shutil.copytree(pkg, scan / 'root', symlinks=True)
        (scan / 'debian').mkdir()
        (scan / 'debian/control').write_text('Source: erhai-sensors\n\nPackage: erhai-sensors\nArchitecture: arm64\n')
        elves = [f'/build/scan/root/{PREFIX}/{name}' for name in PAYLOAD] + \
            [f'/build/scan/root/{PREFIX}/lib/{p.name}' for p in (pkg / PREFIX / 'lib').iterdir()
             if not p.is_symlink()]
        depends = capture(root, f'cd /build/scan && dpkg-shlibdeps -O --ignore-missing-info '
                                f'-l/build/scan/root/{PREFIX}/lib ' + ' '.join('-e' + e for e in elves)).strip()
        if not depends.startswith('shlibs:Depends='):
            die('dpkg-shlibdeps returned no Depends')
        depends = depends.split('=', 1)[1]
        shutil.rmtree(root / 'build')

        release = (PACKAGE / 'VERSION').read_text().split('#')[0].strip()
        if not release or not release[0].isdigit() or any(c in release for c in '~+ \n'):
            die('packaging/erhai-sensors/VERSION must hold one release counter like 0.1.0')
        templates = hashlib.sha256()
        for name in ('control', 'postinst', 'prerm', 'postrm'):
            templates.update(f'{name} {sha256(PACKAGE / name)}\n'.encode())
        payload = tree_digest(pkg)
        build_id = hashlib.sha256(f'{payload}\n{templates.hexdigest()}\n{depends}\n'.encode()).hexdigest()[:8]
        version = f'{release}+b{build_id}'

        debian = pkg / 'DEBIAN'
        debian.mkdir()
        size = sum((p.stat().st_size + 1023) // 1024 if p.is_file() and not p.is_symlink() else 1
                   for p in pkg.rglob('*') if debian not in p.parents and p != debian)
        text = (PACKAGE / 'control').read_text()
        for key, value in (('@VERSION@', version), ('@MAINTAINER@', MAINTAINER),
                           ('@INSTALLED_SIZE@', str(size)), ('@DEPENDS@', depends)):
            text = text.replace(key, value)
        (debian / 'control').write_text(text)
        for name in ('postinst', 'prerm', 'postrm'):
            shutil.copyfile(PACKAGE / name, debian / name)
            (debian / name).chmod(0o755)
        (debian / 'md5sums').write_text(''.join(
            f'{hashlib.md5(p.read_bytes()).hexdigest()}  {p.relative_to(pkg).as_posix()}\n'
            for p in sorted(pkg.rglob('*'))
            if p.is_file() and not p.is_symlink() and debian not in p.parents))
        # Modes are the package's, not the build host umask's.
        pkg.chmod(0o755)
        for entry in pkg.rglob('*'):
            if entry.is_symlink():
                continue
            if entry.is_dir() or entry.stat().st_mode & 0o100:
                entry.chmod(0o755)
            else:
                entry.chmod(0o644)

        output.mkdir(parents=True, exist_ok=True)
        deb = output / f'erhai-sensors_{version}_arm64.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(pkg), str(deb)],
                       env=dict(os.environ, SOURCE_DATE_EPOCH=str(epoch)), check=True,
                       stdout=subprocess.DEVNULL)
        shutil.rmtree(pkg)
        manifest = {'status': 'OFFLINE_CANDIDATE', 'version': version, 'depends': depends,
                    'payload_sha256': payload, 'source_date_epoch': epoch, **recipe,
                    'package': {'file': deb.name, 'sha256': sha256(deb), 'bytes': deb.stat().st_size}}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if args.clean:
        shutil.rmtree(work)
    print(json.dumps(manifest['package'], indent=2))


if __name__ == '__main__':
    main()
