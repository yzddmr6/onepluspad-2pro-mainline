#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Package a mainline first-boot candidate: kernel Image + erhai DTB + RAM initramfs.

The device boot contract is header v2 with the three components delivered by
ABL: kernel, ramdisk and --dtb. Output identity records the kernel commit,
config fragment, every input hash and the ABL overlay sink layout read back
from the DTB (tools/lib/abl_layout.py). A DTB with the legacy root-level sink
is only taken with --legacy-sink: that layout is for fallback and comparison.

The setup image for first-time preparation is a RAM desktop built with
--debug-package: the erhai-debug deb rides in a second archive appended to
the ramdisk, and the initramfs installs it into the RAM overlay of that one
session. The published root filesystem and installed systems stay without it.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

from lib.abl_layout import LayoutError, add_arguments as add_layout_arguments, \
    check_choice, sink_layout
from lib.boot_profiles import CMDLINE, PROFILE_EXTRA

REPO = Path(__file__).resolve().parent.parent
# Workspace layout: when this repo is checked out at <workspace>/public/<name>,
# shared inputs and build outputs live in the workspace root; standalone
# checkouts keep everything inside the repo. ERHAI_WORKSPACE overrides both.
if (REPO.parent.parent / 'AGENTS.md').is_file() and (REPO.parent.parent / 'kernel/linux').is_dir():
    WS = Path(os.environ.get('ERHAI_WORKSPACE', REPO.parent.parent)).resolve()
else:
    WS = Path(os.environ.get('ERHAI_WORKSPACE', str(REPO))).resolve()
KERNEL_GIT = WS / 'kernel/linux'
DEFAULT_OUT = WS / 'out/kernel-firstboot'
# AOSP mkbootimg, vendored at cache/tools/mkbootimg.py (see README inputs).
MKBOOT = Path(os.environ.get('MKBOOTIMG', str(WS / 'cache/tools/mkbootimg.py')))
# Where initramfs/init-ncm looks for the package a setup session installs.
CARRIED_DEBUG = 'usr/lib/erhai/debug/erhai-debug.deb'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def newc(entries):
    """A newc cpio archive of (path, mode, data) entries, owned by root at time 0."""
    archive = bytearray()
    for ino, (name, mode, data) in enumerate([*entries, ('TRAILER!!!', 0, b'')], 1):
        fields = (ino, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0, len(data),
                  0, 0, 0, 0, len(name) + 1, 0)
        archive += b'070701' + ''.join(f'{field:08X}' for field in fields).encode()
        archive += name.encode() + b'\0'
        archive += bytes(-len(archive) % 4) + data
        archive += bytes(-len(archive) % 4)
    return bytes(archive)


def carried_package(deb):
    """The ramdisk addition holding a setup session's diagnostics package.

    The kernel unpacks concatenated archives in order, so appending this one
    to the shared initramfs leaves the installed init_boot ramdisk unchanged.
    """
    parts = CARRIED_DEBUG.split('/')
    directories = [('/'.join(parts[:i]), stat.S_IFDIR | 0o755, b'')
                   for i in range(1, len(parts))]
    archive = newc(directories + [(CARRIED_DEBUG, stat.S_IFREG | 0o644, deb.read_bytes())])
    return gzip.compress(archive, compresslevel=9, mtime=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--kernel-out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--initramfs', type=Path,
                        default=WS / 'out/initramfs-dev/initramfs-ncm.cpio.gz')
    parser.add_argument('--dtb', type=Path)
    parser.add_argument('--cmdline-extra', default='',
                        help='Appended to the standard cmdline (e.g. erhai.watchdog=1800 '
                             'to hold a demo session longer than 600s)')
    parser.add_argument('--profile', choices=tuple(PROFILE_EXTRA),
                        help='Append a cmdline policy: "desktop" runs a RAM desktop '
                             'session, "persistent" boots the installed UFS root')
    parser.add_argument('--rootfs', type=Path,
                        help='RAM desktop squashfs to hash; requires --profile desktop')
    parser.add_argument('--rootfs-url',
                        help='HTTP URL serving that squashfs to the tablet')
    parser.add_argument('--debug-package', type=Path,
                        help='erhai-debug deb for a setup session: the initramfs installs '
                             'it into the RAM overlay only; adds erhai.debug=1')
    add_layout_arguments(parser)
    args = parser.parse_args()
    rootfs = None
    debug_package = None
    if args.debug_package:
        if args.profile != 'desktop':
            parser.error('--debug-package requires --profile desktop')
        if not args.debug_package.is_file():
            parser.error(f'Missing input: {args.debug_package}')
        fields = subprocess.run(['dpkg-deb', '--field', str(args.debug_package),
                                 'Package', 'Version'],
                                capture_output=True, text=True)
        control = dict(line.split(': ', 1) for line in fields.stdout.splitlines()
                       if ': ' in line)
        if fields.returncode or control.get('Package') != 'erhai-debug':
            parser.error(f'{args.debug_package} is not an erhai-debug package')
        debug_package = {'version': control.get('Version'), 'path': '/' + CARRIED_DEBUG}
    if args.profile == 'desktop':
        if not args.rootfs or not args.rootfs_url:
            parser.error('--profile desktop requires --rootfs and --rootfs-url')
        if not args.rootfs_url.startswith(('http://', 'https://')) or any(
                c.isspace() or c in '\x00"' for c in args.rootfs_url):
            parser.error('--rootfs-url must be one HTTP(S) URL without whitespace or quotes')
        if not args.rootfs.is_file():
            parser.error(f'Missing input: {args.rootfs}')
        if any(token.startswith(('erhai.rootfs=', 'erhai.rootfs.sha256=', 'erhai.root='))
               for token in args.cmdline_extra.split()):
            parser.error('RAM desktop root inputs must use --rootfs and --rootfs-url')
        with args.rootfs.open('rb') as stream:
            rootfs = {'url': args.rootfs_url,
                      'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
    elif args.rootfs or args.rootfs_url:
        parser.error('--rootfs and --rootfs-url require --profile desktop')
    cmdline = CMDLINE
    if args.profile:
        cmdline += ' ' + PROFILE_EXTRA[args.profile]
    if rootfs:
        cmdline += f' erhai.rootfs={rootfs["url"]} erhai.rootfs.sha256={rootfs["sha256"]}'
    if debug_package and 'erhai.debug=1' not in args.cmdline_extra.split():
        cmdline += ' erhai.debug=1'
    if args.cmdline_extra.strip():
        cmdline += ' ' + args.cmdline_extra.strip()
    kout = args.kernel_out.resolve()
    image = kout / 'arch/arm64/boot/Image'
    dtb = args.dtb or kout / 'arch/arm64/boot/dts/qcom/sm8750-erhai.dtb'
    initramfs = args.initramfs.resolve()
    for path in (image, dtb, initramfs):
        if not path.is_file():
            parser.error(f'Missing input: {path}')
    try:
        layout = check_choice(sink_layout(dtb.read_bytes()), args.sink_layout,
                              allow_none=True)
    except LayoutError as error:
        parser.error(f'{dtb}: {error}')

    head = subprocess.run(['git', '-C', str(KERNEL_GIT), 'rev-parse', 'HEAD'],
                          capture_output=True, check=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(KERNEL_GIT), 'status', '--porcelain'],
                           capture_output=True, check=True, text=True).stdout.strip()
    if dirty:
        parser.error(f'Kernel tree is dirty; commit first so the candidate identifies real code:\n{dirty}')

    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = {'Image': image, 'sm8750-erhai.dtb': dtb, 'initramfs.cpio.gz': initramfs}
    if debug_package:
        inputs['erhai-debug.deb'] = args.debug_package.resolve()
    hashes = {name: sha(path) for name, path in inputs.items()}
    ramdisk = initramfs
    if debug_package:
        ramdisk = out / 'ramdisk.cpio.gz'
        ramdisk.write_bytes(initramfs.read_bytes() + carried_package(args.debug_package))
    boot = out / 'boot-mainline.img'
    subprocess.run(['python3', str(MKBOOT), '--header_version', '2', '--pagesize', '4096',
                    '--base', '0', '--kernel_offset', '0x00008000',
                    '--ramdisk_offset', '0x01000000', '--tags_offset', '0x00000100',
                    '--dtb_offset', '0x01f00000',
                    '--kernel', str(image), '--ramdisk', str(ramdisk),
                    '--dtb', str(dtb), '--os_version', '15.0.0',
                    '--os_patch_level', '2026-07', '--cmdline', cmdline,
                    '--output', str(boot)], check=True)
    if debug_package:
        ramdisk.unlink()
    assert boot.stat().st_size <= 100663296, 'exceeds boot partition capacity'
    manifest = {'status': 'OFFLINE_CANDIDATE_NOT_DEVICE_TESTED',
                'kernel_commit': head, 'kernel_out': str(kout),
                'cmdline': cmdline, 'inputs_sha256': hashes,
                'abl_sink_layout': layout,
                'boot_sha256': sha(boot), 'boot_size': boot.stat().st_size,
                'scope': 'fastboot boot only (header v2, ABL delivers kernel/ramdisk/dtb); '
                         'RAM userspace with NCM/HTTP evidence, telnet end, watchdog self-recovery.'}
    if rootfs:
        manifest['ram_rootfs'] = rootfs
    if debug_package:
        manifest['debug_package'] = debug_package
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: manifest[k] for k in ['status', 'kernel_commit', 'abl_sink_layout',
                                                   'boot_sha256', 'boot_size']}, indent=2))


if __name__ == '__main__':
    main()
