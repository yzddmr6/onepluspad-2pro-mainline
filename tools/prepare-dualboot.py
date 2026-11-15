#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare the supported OPD2413 512 GB layout from a temporary Linux desktop.

Print the plan and save a GPT backup by default. Applying the plan destroys
Android userdata; the caller must explicitly request --erase-android.
Partition editing uses the distribution's sgdisk, not a private GPT writer.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess

GIB = 1024 ** 3
SECTOR = 4096
DISK = '/dev/sda'


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=30,
                                   env={**os.environ, 'LC_ALL': 'C'})


def layout_commands(disk, info, last):
    """Keep userdata's identity and start; reserve 200 GiB Android and 60 GiB root."""
    start = int(re.search(r'First sector: (\d+)', info)[1])
    end = int(re.search(r'Last sector: (\d+)', info)[1])
    if start != 3617586 or end != last:
        raise RuntimeError('userdata differs from the supported stock layout')
    guid = re.search(r'Partition unique GUID: ([A-Fa-f0-9-]+)', info)[1]
    kind = re.search(r'Partition GUID code: ([A-Fa-f0-9-]+)', info)[1]
    flags = re.search(r'Attribute flags: ([A-Fa-f0-9]+)', info)[1]
    android_end = start + 200 * GIB // SECTOR - 1
    alignment = 8 * 1024 ** 2 // SECTOR
    root_start = (android_end + alignment) // alignment * alignment
    root_end = root_start + 60 * GIB // SECTOR - 1
    if last - root_end < 128 * GIB // SECTOR:
        raise RuntimeError('Not the supported 512 GB disk geometry')
    return ['sgdisk', '--set-alignment=1', '--delete=15',
            f'--new=15:{start}:{android_end}', f'--typecode=15:{kind}',
            f'--partition-guid=15:{guid}', f'--attributes=15:=:0x{flags}',
            '--change-name=15:userdata', f'--new=16:{root_start}:{root_end}',
            '--typecode=16:8300', '--change-name=16:linux_rootfs',
            f'--new=17:{root_end + 1}:{last}', '--typecode=17:8300',
            '--change-name=17:linux_data', disk]


def inspect():
    model = Path('/sys/firmware/devicetree/base/model').read_text().rstrip('\0')
    cmdline = Path('/proc/cmdline').read_text().split()
    # ABL replaces the source DTS model with its stock erhai board label.
    # Check the bootloader project ID as well; a generic Sun/SM8750 is not enough.
    if ('oplusboot.prjname=24926' not in cmdline or
            not (model == 'OnePlus Pad 2 Pro' or ',erhai-' in model)):
        raise RuntimeError('Only the OPD2413 erhai project is supported')
    if 'erhai.switchroot=1' not in cmdline or not any(x.startswith('erhai.rootfs=') for x in cmdline):
        raise RuntimeError('Boot the temporary RAM desktop first; do not partition a running installed system')
    active = []
    for slot in ('a', 'b'):
        flags = int(run('lsblk', '-dno', 'PARTFLAGS', '/dev/disk/by-partlabel/boot_' + slot).strip(), 0)
        if flags & 0x0004000000000000 and not flags & 0x0080000000000000:
            active.append(slot)
    if active != ['a']:
        raise RuntimeError('Only active slot A is supported; do not change slots during preparation')
    if int(run('blockdev', '--getss', DISK)) != SECTOR:
        raise RuntimeError('Expected 4096-byte disk sectors')
    if not 450 * GIB <= int(run('blockdev', '--getsize64', DISK)) <= 512 * GIB:
        raise RuntimeError('Only the 512 GB model layout is supported')
    table = run('sgdisk', '--print', DISK)
    entries = re.findall(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+.*?\s+([0-9A-F]{4})\s+(\S+)\s*$', table, re.M)
    names = {int(n): name for n, _, _, _, name in entries}
    if names.get(15) != 'userdata' or max(names, default=0) != 15:
        raise RuntimeError('Expected stock userdata as the last partition; an existing Linux layout must use install.py')
    # A temporary root must not have mounted a partition from the disk being edited.
    mounted = run('findmnt', '-rn', '-o', 'SOURCE')
    if any(re.match(r'/dev/sda\d+(?:\[|$)', line) for line in mounted.splitlines()):
        raise RuntimeError('A partition on sda is mounted; unmount it before proceeding')
    last = int(re.search(r'last usable sector is (\d+)', table)[1])
    info = run('sgdisk', '--info=15', DISK)
    return table, layout_commands(DISK, info, last)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, default=Path('/run/erhai-gpt-backup.bin'))
    parser.add_argument('--erase-android', action='store_true', help='Apply the plan; Android data must subsequently be erased in Fastboot')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run as root in the temporary RAM desktop')
    os.umask(0o077)
    with Path('/run/erhai-partition.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        table, command = inspect()
        record = args.backup.with_suffix('.json')
        serial = next((x.split('=', 1)[1] for x in Path('/proc/cmdline').read_text().split()
                       if x.startswith(('oplusboot.serialno=', 'androidboot.serialno='))), None)
        if not serial:
            raise RuntimeError('Device serial is missing')
        print(table)
        print('New layout: Android 200 GiB, Linux root 60 GiB, Linux home uses the remainder.')
        if not args.erase_android:
            if args.backup.exists() or record.exists():
                raise RuntimeError('Backup already exists; keep it and use --erase-android only after saving it on the host')
            run('sgdisk', '--backup=' + str(args.backup), DISK)
            record.write_text(json.dumps({'serial': serial, 'table': table, 'command': command}, indent=2) + '\n')
            print(f'Saved {args.backup} and {record}. Copy both to the host before applying.')
            return
        saved = json.loads(record.read_text())
        if saved['serial'] != serial or saved['table'] != table or saved['command'] != command or not args.backup.is_file():
            raise RuntimeError('Saved partition plan does not match this tablet')
        print('Applying the layout. Android data will no longer be usable.', flush=True)
        print(run(*command))
        verification = run('sgdisk', '--verify', DISK)
        print(verification)
        if 'No problems found' not in verification:
            raise RuntimeError('Partition verification failed; keep the backup and do not erase userdata')
        print('Layout written. Reboot to Fastboot, erase userdata and metadata, then boot Android.')
        print('Keep the GPT backup on the host. Do not run the preparation step again.')


if __name__ == '__main__':
    main()
