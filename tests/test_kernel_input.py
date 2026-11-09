#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""The real build entry must refuse an unrelated kernel before invoking make."""
import os
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix='erhai-kernel-input-') as temporary:
    directory = Path(temporary)
    source = directory / 'source'
    source.mkdir()
    def git(*args):
        return subprocess.run(['git', '-C', str(source), *args], check=True, capture_output=True)
    git('-c', 'init.templateDir=', 'init', '-q')
    fragment = source / 'arch/arm64/configs/erhai-firstboot.config'
    fragment.parent.mkdir(parents=True)
    fragment.write_text('# unrelated fixture\n')
    for name in ['sm8750-netfilter.config', 'sm8750-peripherals.config', 'sm8750-waydroid.config', 'sm8750-snap.config', 'sm8750-virt.config']:
        (fragment.parent / name).write_text('# unrelated feature\n')
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-qm', 'Unrelated input fixture')
    result = subprocess.run([str(REPO / 'tools/build-kernel.sh')], capture_output=True, text=True,
                            env={**os.environ, 'KERNEL_SOURCE': str(source),
                                 'OUT_DIR': str(directory / 'out'), 'ALLOW_UNPINNED_KERNEL': '0'})
    assert result.returncode != 0 and 'Kernel HEAD differs from kernel/source.json' in result.stderr
    assert not (directory / 'out/.config').exists()
    print('PASS: unrelated kernel refused before configuration or build')
