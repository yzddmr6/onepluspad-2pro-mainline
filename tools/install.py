#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reinstall Linux on an OPD2413 with an existing dual-boot partition layout.

Back up the live Android boot set and per-device sensor data, prepare private
ext4 images from a verified generic root, then replace only linux_rootfs and
linux_data. The existing KernelSU switcher activates the Ubuntu boot set.
No GPT, Android userdata, inactive-slot or firmware partition is written.
"""
import argparse
from contextlib import ExitStack
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import tempfile
import time
import uuid

from lib.build_root import REPO, fetch, sha256
from lib.install_tools import ext2simg

PARTS = ('boot', 'init_boot', 'vendor_boot')
KSU_SWITCH = '/data/adb/modules/erhai_switch/system/bin/erhai-switch'
SOCINFO = ('hw_platform', 'platform_subtype', 'platform_subtype_id',
           'platform_version', 'soc_id', 'revision')


def check_firmware(plan):
    supported = json.loads((REPO / 'packaging/installation.json').read_text())
    if plan['firmware'] not in supported['tested_firmware_fingerprints']:
        raise RuntimeError('Firmware is outside the tested installation combination')


def layout_identity(partitions):
    """Partition identity that survives a reboot.

    /dev/block/sdX names follow the UFS LUN probe order, which is not stable
    across boots: the same boot_a node has been observed as sdd12 and sde12 on
    one tablet. A layout is therefore identified by the size and start sector
    of every partition, not by the node it was reached through.
    """
    return {name: (part['bytes'], part['start_512']) for name, part in partitions.items()}


def check_linux_layout(plan):
    ranges = {}
    for name in ('userdata', 'linux_rootfs', 'linux_data'):
        part = plan['partitions'][name]
        disk = re.fullmatch(r'(/dev/block/sd[a-z]+)\d+', part['device'])
        if not disk:
            raise RuntimeError('Unsupported UFS partition path')
        ranges[name] = (disk[1], part['start_512'], part['start_512'] + part['bytes'] // 512)
    userdata, root, home = (ranges[n] for n in ('userdata', 'linux_rootfs', 'linux_data'))
    if (root[0] != userdata[0] or home[0] != userdata[0]
            or root[1] < userdata[2] or home[1] < userdata[2]
            or max(root[1], home[1]) < min(root[2], home[2])):
        raise RuntimeError('Linux partitions must be disjoint and follow Android userdata on the same UFS disk')


def sparse_size(path):
    with path.open('rb') as stream:
        magic, major, minor, header, chunk, block_size, blocks, count, checksum = struct.unpack(
            '<I4H4I', stream.read(28))
    if magic != 0xED26FF3A or major != 1 or header != 28 or chunk != 12 or block_size != 4096:
        raise RuntimeError('Unsupported Android sparse image')
    return block_size * blocks


class Installer:
    def __init__(self, args):
        self.args = args
        self.work = args.work.resolve()
        self.work.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.log = (self.work / 'commands.jsonl').open('a')

    def run(self, command, timeout=60, output=None, combined=False):
        command = list(map(str, command))
        print(f'Running {Path(command[0]).name}' + (f' → {output.name}' if output else ''), flush=True)
        record = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'command': command, 'timeout': timeout}
        self.log.write(json.dumps(record) + '\n')
        self.log.flush()
        started = time.monotonic()
        with output.open('wb') if output else open(os.devnull, 'wb') as stream:
            result = subprocess.run(command, stdout=stream if output else subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout)
        record = {'returncode': result.returncode, 'elapsed_seconds': time.monotonic() - started,
                  'stderr': result.stderr.decode(errors='replace')}
        if not output:
            record['stdout'] = result.stdout.decode(errors='replace')
        self.log.write(json.dumps(record) + '\n')
        self.log.flush()
        if result.returncode:
            raise RuntimeError(f'{command[0]} failed: {record["stderr"][-2000:]}')
        text = record.get('stdout', '') + (record['stderr'] if combined else '')
        return text.replace('\r\n', '\n')

    def android(self, script, timeout=60, output=None):
        identity = ('set -e; test "$(getprop ro.serialno)" = ' + shlex.quote(self.args.serial)
                    + '; test "$(getprop ro.product.model)" = OPD2413; test "$(id -u)" = 0; ')
        return self.run(['adb', '-s', self.args.serial, 'exec-out', 'su', '-c',
                         identity + script], timeout, output)

    def inspect(self, minimum_battery=50, require_linux=True):
        names = 'userdata boot_a init_boot_a vendor_boot_a'
        if require_linux:
            names += ' linux_rootfs linux_data'
        text = self.android('''
echo SLOT=$(getprop ro.boot.slot_suffix)
echo FIRMWARE=$(getprop ro.build.fingerprint)
for name in @PARTITIONS@; do
    dev=$(readlink -f /dev/block/by-name/$name)
    test -b "$dev"
    node=${dev##*/}
    grep -qx "PARTNAME=$name" /sys/class/block/$node/uevent
    echo PART=$name,$dev,$(blockdev --getsize64 "$dev"),$(cat /sys/class/block/$node/start)
done
test -d /mnt/vendor/persist/sensors/registry/registry
dumpsys battery
'''.replace('@PARTITIONS@', names))
        slot = re.search(r'^SLOT=(.*)$', text, re.M)
        if not slot or slot[1] != '_a':
            raise RuntimeError('Only the verified active-slot-A layout is supported')
        battery = re.search(r'^\s*level:\s*(\d+)', text, re.M)
        if not battery or int(battery[1]) < minimum_battery:
            raise RuntimeError(f'Charge in Android to at least {minimum_battery}% before installation')
        parts = {}
        for name, device, size, start in re.findall(r'^PART=([^,]+),([^,]+),(\d+),(\d+)$', text, re.M):
            parts[name] = {'device': device, 'bytes': int(size), 'start_512': int(start)}
        if len(parts) != len(names.split()) or len({p['device'] for p in parts.values()}) != len(parts):
            raise RuntimeError('Partition identity is incomplete or aliases another target')
        for name, minimum in ((('linux_rootfs', 16 << 30), ('linux_data', 8 << 30)) if require_linux else ()):
            if parts[name]['bytes'] < minimum:
                raise RuntimeError(f'{name} is too small')
        return {'serial': self.args.serial, 'slot': slot[1], 'partitions': parts,
                'firmware': re.search(r'^FIRMWARE=(.*)$', text, re.M)[1],
                'battery': int(battery[1])}

    def check_device(self):
        plan = self.inspect(require_linux=False)
        check_firmware(plan)
        print('OPD2413, tested Android firmware, active slot A and battery: OK')

    def backup(self):
        if (self.work / 'backup.json').exists():
            raise RuntimeError('Backup already exists; retain it and select the next phase')
        plan = self.inspect()
        self.android('test -x ' + shlex.quote(KSU_SWITCH))
        directory = self.work / 'android'
        directory.mkdir()
        hashes = {}
        for name in PARTS:
            device = plan['partitions'][name + '_a']['device']
            expected = self.android('sha256sum ' + shlex.quote(device)).split()[0]
            target = directory / (name + '.img')
            self.android('cat ' + shlex.quote(device), 180, target)
            if target.stat().st_size != plan['partitions'][name + '_a']['bytes'] or sha256(target) != expected:
                raise RuntimeError(f'{name}: Android backup readback mismatch')
            hashes[name] = expected
        (directory / 'SHA256SUMS').write_text(''.join(f'{hashes[n]}  {n}.img\n' for n in PARTS))
        plan['android_sha256'] = hashes
        sensor_tar = self.work / 'sensors.tar'
        self.android('tar -C /mnt/vendor/persist -cf - sensors', 60, sensor_tar)
        plan['sensors_sha256'] = sha256(sensor_tar)
        soc = self.work / 'soc0'
        soc.mkdir()
        for name in SOCINFO:
            text = self.android('if test -r /sys/devices/soc0/' + name
                                + '; then cat /sys/devices/soc0/' + name + '; fi')
            if text:
                (soc / name).write_text(text)
        (self.work / 'backup.json').write_text(json.dumps(plan, indent=2) + '\n')
        print('Android boot set and per-device sensor data backed up', flush=True)

    def load_backup(self):
        plan = json.loads((self.work / 'backup.json').read_text())
        if plan['serial'] != self.args.serial or plan['slot'] != '_a':
            raise RuntimeError('Backup belongs to another tablet or unsupported slot')
        for name in PARTS:
            if sha256(self.work / 'android' / (name + '.img')) != plan['android_sha256'][name]:
                raise RuntimeError('Android backup has changed')
        if sha256(self.work / 'sensors.tar') != plan['sensors_sha256']:
            raise RuntimeError('Sensor backup has changed')
        return plan

    def prepare(self):
        plan = self.load_backup()
        check_firmware(plan)
        check_linux_layout(plan)
        converter, converter_record = ext2simg()
        if not self.args.rootfs:
            raise RuntimeError('--rootfs is required for prepare')
        rootfs = self.args.rootfs.resolve()
        manifest = json.loads(rootfs.with_name('manifest.json').read_text())
        if sha256(rootfs) != manifest['rootfs_sha256']:
            raise RuntimeError('Root filesystem does not match its build manifest')
        identity = {
            'project_version': '0.2.1', 'serial': self.args.serial,
            'rootfs_sha256': manifest['rootfs_sha256'],
            'prepared_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'partition_layout': 'existing linux_rootfs and linux_data; GPT unchanged'}
        marker = self.work / 'installation.json'
        if self.args.resume_prepare:
            staged = json.loads(marker.read_text())
            if any(staged[k] != identity[k] for k in ('serial', 'rootfs_sha256', 'project_version')):
                raise RuntimeError('Staged root belongs to different installation inputs')
        else:
            marker.write_text(json.dumps(identity, indent=2) + '\n')
        lock = json.loads((REPO / 'packaging/desktop/source.json').read_text())
        native = self.work / 'native'
        for entry in lock['build_host']['packages']:
            fetch(entry['url'], native / entry['file'], entry['sha256'])
        image = lock['build_host']['image']
        completed = self.work / 'filesystems-ready.json'
        if self.args.resume_prepare and completed.exists():
            if json.loads(completed.read_text()) != json.loads(marker.read_text()):
                raise RuntimeError('Prepared filesystems belong to different installation inputs')
        else:
            container = 'erhai-install-' + uuid.uuid4().hex[:12]
            try:
                self.run(['docker', 'run', '--rm', '--name', container, '--network', 'none', '--cap-add', 'SYS_ADMIN',
                          '-v', f'{self.work}:/work', '-v', f'{rootfs}:/input/rootfs.squashfs:ro',
                          '-v', f'{REPO / "tools/lib/install-images.sh"}:/prepare:ro', image,
                          'bash', '/prepare', str(plan['partitions']['linux_rootfs']['bytes']),
                          str(plan['partitions']['linux_data']['bytes']),
                          f'{os.getuid()}:{os.getgid()}', str(self.args.test_recovery),
                          str(int(self.args.resume_prepare))], 1800)
            except BaseException:
                subprocess.run(['docker', 'rm', '-f', container], capture_output=True)
                raise
        result = {'serial': self.args.serial, 'rootfs_sha256': manifest['rootfs_sha256'],
                  'container': image, 'images': {},
                  'sparse_converter': converter_record,
                  'test_recovery_seconds': self.args.test_recovery}
        for name in ('linux_rootfs', 'linux_data'):
            path = self.work / 'images' / (name + '.img')
            raw = path.with_suffix('.raw')
            digest = self.convert_sparse(converter, raw, path)
            if sparse_size(path) != plan['partitions'][name]['bytes']:
                raise RuntimeError('Sparse image geometry differs from the target')
            result['images'][name] = {'bytes': path.stat().st_size, 'sha256': digest,
                                     'partition_bytes': sparse_size(path)}
        result['ubuntu_sha256'] = dict((line.split()[1].removesuffix('.img'), line.split()[0])
                                      for line in (self.work / 'ubuntu-SHA256SUMS').read_text().splitlines())
        (self.work / 'prepared.json').write_text(json.dumps(result, indent=2) + '\n')
        for name in ('linux_rootfs', 'linux_data'):
            (self.work / 'images' / (name + '.raw')).unlink()
        print('Private installation images prepared; no tablet partition written', flush=True)

    def convert_sparse(self, converter, raw, output):
        # Hash the generated stream while writing it, avoiding another full
        # read of the installation image. timeout bounds the entire pipeline.
        command = (shlex.quote(str(converter)) + ' ' + shlex.quote(str(raw))
                   + ' /dev/stdout | tee ' + shlex.quote(str(output)) + ' | sha256sum')
        text = self.run(['timeout', '-k', '5', '1200', 'bash', '-o', 'pipefail', '-c', command], 1210)
        digest = text.split()[0]
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise RuntimeError('Sparse conversion did not produce a checksum')
        return digest

    def fastboot(self, *args, timeout=60):
        return self.run(['fastboot', '-s', self.args.serial, *args], timeout)

    def fastboot_variable(self, name):
        text = self.run(['fastboot', '-s', self.args.serial, 'getvar', name],
                        timeout=30, combined=True)
        match = re.search(re.escape(name) + r':\s*(\S+)', text)
        if not match:
            raise RuntimeError(f'Fastboot did not report {name}')
        return match[1]

    def wait_adb(self):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            r = subprocess.run(['adb', '-s', self.args.serial, 'get-state'],
                               capture_output=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip() == b'device':
                return
            time.sleep(2)
        raise RuntimeError('Android did not return within 120 seconds')

    def install(self):
        if not self.args.erase_linux:
            raise RuntimeError('Installation erases Linux: --erase-linux is required')
        saved = self.load_backup()
        current = self.inspect()
        if (saved['serial'] != current['serial'] or saved['slot'] != current['slot']
                or saved['firmware'] != current['firmware']
                or layout_identity(saved['partitions']) != layout_identity(current['partitions'])):
            raise RuntimeError('Device layout or firmware changed since backup')
        check_firmware(current)
        check_linux_layout(current)
        prepared = json.loads((self.work / 'prepared.json').read_text())
        if prepared['serial'] != self.args.serial:
            raise RuntimeError('Prepared images belong to another tablet')
        for name, entry in prepared['images'].items():
            if name not in ('linux_rootfs', 'linux_data'):
                raise RuntimeError('Unexpected flash target')
            path = self.work / 'images' / (name + '.img')
            if (sparse_size(path) != current['partitions'][name]['bytes']
                    or path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']):
                raise RuntimeError(f'{name}: image size or checksum mismatch')
        if set(prepared['images']) != {'linux_rootfs', 'linux_data'}:
            raise RuntimeError('Both Linux images are required')
        for name in PARTS:
            live = self.android('sha256sum ' + shlex.quote(current['partitions'][name + '_a']['device'])).split()[0]
            if live != saved['android_sha256'][name]:
                raise RuntimeError('Live Android boot set changed since backup')
        self.run(['adb', '-s', self.args.serial, 'reboot', 'bootloader'])
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            r = subprocess.run(['fastboot', '-s', self.args.serial, 'devices'],
                               capture_output=True, timeout=10)
            if any(line.split()[0] == self.args.serial for line in r.stdout.decode().splitlines() if line.split()):
                break
            time.sleep(2)
        else:
            raise RuntimeError('Selected tablet did not reach fastboot')
        expected = {'product': 'sun', 'current-slot': 'a', 'unlocked': 'yes', 'is-userspace': 'no'}
        for name, value in expected.items():
            if self.fastboot_variable(name) != value:
                raise RuntimeError(f'Unexpected bootloader state: {name}')
        # No partition is changed until both fastboot-reported sizes match.
        for name in ('linux_rootfs', 'linux_data'):
            size = self.fastboot_variable('partition-size:' + name)
            if int(size, 16 if size.startswith('0x') else 10) != current['partitions'][name]['bytes']:
                raise RuntimeError('Fastboot partition geometry differs from Android')
        for name in ('linux_rootfs', 'linux_data'):
            # Sparse DONT_CARE chunks must not leave old filesystem metadata.
            self.fastboot('erase', name, timeout=180)
            self.fastboot('-S', '256M', 'flash', name, self.work / 'images' / (name + '.img'), timeout=1200)
        self.fastboot('reboot')
        self.wait_adb()
        # The existing switcher owns activation and readback of all boot images.
        self.android(shlex.quote(KSU_SWITCH) + ' to-ubuntu --no-reboot', timeout=180)
        (self.work / 'installed.json').write_text(json.dumps({
            'status': 'WRITTEN_AND_BOOT_TRIPLET_VERIFIED; first boot acceptance pending',
            'serial': self.args.serial, 'images': prepared['images'],
            'ubuntu_sha256': prepared['ubuntu_sha256']}, indent=2) + '\n')
        self.run(['adb', '-s', self.args.serial, 'reboot'])
        print('Ubuntu boot requested. Verify first boot before accepting this installation.', flush=True)

    def restore_android(self):
        plan = self.load_backup()
        if self.fastboot_variable('current-slot') != plan['slot'].removeprefix('_'):
            raise RuntimeError('Active slot changed; inspect it before restoring the saved boot set')
        # Explicit recovery uses only this tablet's verified full-partition backup.
        for name in PARTS:
            self.fastboot('flash', name + plan['slot'], self.work / 'android' / (name + '.img'), timeout=180)
        self.fastboot('reboot')
        self.wait_adb()
        restored = self.inspect(minimum_battery=0)
        for name in PARTS:
            got = self.android('sha256sum ' + shlex.quote(restored['partitions'][name + '_a']['device'])).split()[0]
            if got != plan['android_sha256'][name]:
                raise RuntimeError('Android recovery readback mismatch')
        print('Android restored and all three boot partitions verified', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--work', type=Path, required=True, help='Private backup and installation directory')
    parser.add_argument('--rootfs', type=Path, help='Verified generic rootfs.squashfs with manifest.json')
    parser.add_argument('--phase', choices=('check-device', 'backup', 'prepare', 'install', 'restore-android'), required=True)
    parser.add_argument('--erase-linux', action='store_true', help='Permit replacing Linux root and user data')
    parser.add_argument('--resume-prepare', action='store_true',
                        help='Continue the same extracted private root after a pre-image preparation failure')
    parser.add_argument('--test-recovery', type=int, default=0,
                        help='Developer validation: first-boot timeout in seconds (300–1800); '
                             'requires diagnostic access to disarm after verification')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.serial):
        parser.error('Invalid device serial')
    if args.test_recovery and not 300 <= args.test_recovery <= 1800:
        parser.error('--test-recovery must be 300–1800 seconds')
    os.umask(0o077)
    installer = Installer(args)
    with ExitStack() as locks:
        locks.enter_context(installer.log)
        lock = locks.enter_context((installer.work / '.lock').open('w'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase != 'prepare':
            runtime = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir()))
            directory = runtime / f'erhai-device-locks-{os.getuid()}'
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            device_lock = locks.enter_context((directory / (args.serial + '.lock')).open('w'))
            fcntl.flock(device_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            getattr(installer, args.phase.replace('-', '_'))()
        except Exception as error:
            (installer.work / 'failure.json').write_text(json.dumps({
                'phase': args.phase, 'error': str(error)}, indent=2) + '\n')
            raise


if __name__ == '__main__':
    main()
