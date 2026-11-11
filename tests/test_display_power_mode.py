# SPDX-License-Identifier: GPL-2.0-only
"""erhai-display-power-mode: overrides only, both directions, and the status reading."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import re
import tempfile
import unittest

PACKAGING = Path(__file__).resolve().parents[1] / 'packaging'
SOURCE = PACKAGING / 'erhai-display-power/tree/usr/sbin/erhai-display-power-mode'
loader = importlib.machinery.SourceFileLoader('display_power_mode', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
mode = importlib.util.module_from_spec(spec)
loader.exec_module(mode)

GREETER, USER = 60578, 1000


class FakeDevice:
    """A tablet-shaped root plus the systemctl/udevadm it would answer."""

    def __init__(self, root, fix=True):
        self.root = root
        self.calls = []
        self.masked = {unit: '' for unit in mode.UNITS}  # '', 'runtime' or 'etc'
        self.active = {'erhai-display-power.socket': True,
                       'erhai-display-power.service': True}
        self.next_pid = 5000
        self.rule_applies = True
        control = root / f'sys/bus/platform/devices/{mode.MDSS}/power/control'
        control.parent.mkdir(parents=True)
        control.write_text('on\n')
        (root / 'proc').mkdir()
        symbols = 'ffffffc080010000 T _text\n'
        if fix:
            symbols += f'ffffffc080a00000 T {mode.FIX_SYMBOL}\n'
        (root / 'proc/kallsyms').write_text(symbols)
        for uid in (GREETER, USER):
            (root / f'run/user/{uid}/systemd').mkdir(parents=True)
            (root / f'run/user/{uid}/systemd/private').write_text('')
        self.spawn_gsd(GREETER, adapter=True)

    def spawn_gsd(self, uid, adapter):
        pid = self.next_pid
        self.next_pid += 1
        proc = self.root / f'proc/{pid}'
        proc.mkdir()
        (proc / 'comm').write_text('gsd-power\n')
        (proc / 'status').write_text(f'Name:\tgsd-power\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n')
        maps = '7f00-7f01 r-xp 0 00:00 1 /usr/libexec/gsd-power\n'
        if adapter:
            maps += f'7f02-7f03 r-xp 0 00:00 2 {mode.ADAPTER}\n'
        (proc / 'maps').write_text(maps)
        return pid

    def kill_gsd(self, uid):
        for proc in (self.root / 'proc').glob('[0-9]*'):
            if f'Uid:\t{uid}\t' in (proc / 'status').read_text():
                for name in ('comm', 'status', 'maps'):
                    (proc / name).unlink()
                proc.rmdir()
        # systemd restarts it with whatever the drop-in directories say now.
        masked = any(System.is_mask(self.root / base / mode.GSD_DROPIN)
                     for base in ('etc', 'run'))
        self.spawn_gsd(uid, adapter=not masked)

    def __call__(self, argv, uid=None):
        self.calls.append((tuple(argv), uid))
        if argv[:2] == ['systemctl', 'is-enabled']:
            where = self.masked[argv[2]]
            return (1, 'masked-runtime' if where == 'runtime' else 'masked') if where \
                else (0, 'enabled' if argv[2].endswith('.socket') else 'static')
        if argv[:2] == ['systemctl', 'is-active']:
            return (0, 'active') if self.active[argv[2]] else (3, 'inactive')
        if argv[:2] == ['systemctl', 'stop']:
            for unit in argv[2:]:
                self.active[unit] = False
        elif argv[:2] == ['systemctl', 'mask']:
            runtime = '--runtime' in argv
            for unit in argv[2:]:
                if unit != '--runtime':
                    self.masked[unit] = 'runtime' if runtime else 'etc'
        elif argv[:2] == ['systemctl', 'unmask']:
            runtime = '--runtime' in argv
            for unit in argv[2:]:
                if unit != '--runtime' and self.masked[unit] == ('runtime' if runtime else 'etc'):
                    self.masked[unit] = ''
        elif argv[:2] == ['systemctl', 'start']:
            if self.masked[argv[2]]:
                return 1, f'Unit {argv[2]} is masked.'
            self.active[argv[2]] = True
        elif argv[:3] == ['systemctl', '--user', 'kill']:
            self.kill_gsd(uid)
        elif argv[:2] == ['udevadm', 'trigger'] and self.rule_applies:
            if not any(System.is_mask(self.root / base / mode.UDEV_RULE)
                       for base in ('etc', 'run')):
                self.control().write_text('on\n')
        return 0, ''

    def control(self):
        return self.root / f'sys/bus/platform/devices/{mode.MDSS}/power/control'


System = mode.System


class ModeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def device(self, fix=True):
        device = FakeDevice(self.root, fix=fix)
        return device, System(self.root, run=device, sleep=lambda _seconds: None)

    def main(self, system, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status = mode.main(list(argv), system)
        return status, output.getvalue()

    @staticmethod
    def field(text, key):
        return re.search(rf'^{key}=(.*)$', text, re.M)[1]

    def test_package_default_reads_compat(self):
        _, system = self.device()
        status, text = self.main(system, 'status')
        self.assertEqual((status, self.field(text, 'mode')), (0, 'compat'), text)
        self.assertEqual(self.field(text, 'gsd_power'), f'5000:{GREETER}:adapter')

    def test_runtime_standard_and_back(self):
        device, system = self.device()
        status, text = self.main(system, 'standard', '--runtime', '--restart-gsd-power')
        self.assertEqual((status, self.field(text, 'mode')), (0, 'standard'), text)
        run = self.root / 'run'
        for relative in (mode.UDEV_RULE, mode.GSD_DROPIN):
            self.assertEqual(os.readlink(run / relative), '/dev/null')
            self.assertFalse((self.root / 'etc' / relative).is_symlink())
        self.assertEqual((run / mode.MARKER).read_text(), 'standard\n')
        self.assertEqual(device.control().read_text(), 'auto\n')
        self.assertEqual(device.masked, {unit: 'runtime' for unit in mode.UNITS})
        self.assertIn('plain', self.field(text, 'gsd_power'))

        status, text = self.main(system, 'compat', '--restart-gsd-power')
        self.assertEqual((status, self.field(text, 'mode')), (0, 'compat'), text)
        self.assertEqual([p for p in run.rglob('*erhai*') if not p.is_dir() or p.is_symlink()], [])
        self.assertEqual(device.control().read_text(), 'on\n')
        self.assertIn('adapter', self.field(text, 'gsd_power'))

    def test_persistent_standard_goes_to_etc(self):
        device, system = self.device()
        status, text = self.main(system, 'standard')
        self.assertEqual(status, 0, text)
        etc = self.root / 'etc'
        self.assertTrue(System.is_mask(etc / mode.UDEV_RULE))
        self.assertTrue(System.is_mask(etc / mode.GSD_DROPIN))
        self.assertTrue((etc / mode.MARKER).is_file())
        self.assertEqual(set(device.masked.values()), {'etc'})
        # Without a restart the running gsd-power still has the adapter.
        self.assertEqual(self.field(text, 'mode'), 'mixed')
        self.assertIn(((('systemctl', '--user', 'daemon-reload'), GREETER)), device.calls)
        self.assertIn(((('systemctl', '--user', 'daemon-reload'), USER)), device.calls)

    def test_compat_clears_both_places(self):
        device, system = self.device()
        self.main(system, 'standard')
        self.main(system, 'standard', '--runtime')
        status, text = self.main(system, 'compat', '--restart-gsd-power')
        self.assertEqual((status, self.field(text, 'mode')), (0, 'compat'), text)
        self.assertEqual(set(device.masked.values()), {''})
        for base in ('etc', 'run'):
            for relative in (mode.UDEV_RULE, mode.GSD_DROPIN, mode.MARKER):
                self.assertFalse(os.path.lexists(self.root / base / relative))

    def test_refused_without_the_kernel_fix(self):
        device, system = self.device(fix=False)
        status, text = self.main(system, 'standard', '--runtime')
        self.assertEqual(status, 1)
        self.assertIn(mode.FIX_SYMBOL, text)
        self.assertEqual(device.calls[-1][0][:2], ('systemctl', 'is-active'))  # status only
        self.assertFalse(os.path.lexists(self.root / 'run' / mode.MARKER))
        self.assertEqual(self.field(text, 'mode'), 'compat')

    def test_foreign_files_are_never_replaced_or_removed(self):
        device, system = self.device()
        foreign = self.root / 'etc' / mode.UDEV_RULE
        foreign.parent.mkdir(parents=True)
        foreign.write_text('# local rule\n')
        status, text = self.main(system, 'standard')
        self.assertEqual(status, 1)
        self.assertIn('not a mask', text)
        self.assertEqual(foreign.read_text(), '# local rule\n')
        status, text = self.main(system, 'compat')
        self.assertEqual(status, 0, text)
        self.assertEqual(foreign.read_text(), '# local rule\n')

    def test_compat_pins_the_mdss_even_if_the_rule_does_not(self):
        device, system = self.device()
        self.main(system, 'standard', '--runtime')
        device.rule_applies = False
        status, text = self.main(system, 'compat')
        self.assertEqual(status, 0, text)
        self.assertIn('writing on directly', text)
        self.assertEqual(device.control().read_text(), 'on\n')

    def test_step_order(self):
        device, system = self.device()
        self.main(system, 'standard', '--runtime')
        names = [call[0] for call in device.calls]
        self.assertLess(names.index(('systemctl', 'stop', *mode.UNITS)),
                        names.index(('systemctl', 'mask', '--runtime', *mode.UNITS)))
        self.assertLess(names.index(('systemctl', 'mask', '--runtime', *mode.UNITS)),
                        names.index(('udevadm', 'control', '--reload')))
        device.calls.clear()
        marker = self.root / 'run' / mode.MARKER
        seen = []
        original = device.__call__

        def spy(argv, uid=None):
            seen.append((tuple(argv), marker.exists()))
            return original(argv, uid)
        system.run = spy
        self.main(system, 'compat')
        start = next(present for argv, present in seen
                     if argv == ('systemctl', 'start', mode.UNITS[0]))
        # Keep the standard-mode marker until the compatibility socket is ready.
        self.assertTrue(start)
        self.assertFalse(marker.exists())

    def test_mixed_is_reported(self):
        device, system = self.device()
        device.control().write_text('auto\n')
        _, text = self.main(system, 'status')
        self.assertEqual(self.field(text, 'mode'), 'mixed')

    def test_masks_name_the_packaged_files(self):
        self.assertTrue((PACKAGING / 'erhai-device-support/tree/usr/lib' / mode.UDEV_RULE)
                        .is_file())
        self.assertTrue((PACKAGING / 'erhai-display-power/tree/usr/lib' / mode.GSD_DROPIN)
                        .is_file())
        for unit in mode.UNITS:
            self.assertTrue((PACKAGING / 'erhai-display-power/tree/usr/lib/systemd/system'
                             / unit).is_file())
        dropin = (PACKAGING / 'erhai-display-power/tree/usr/lib' / mode.GSD_DROPIN).read_text()
        self.assertIn(mode.ADAPTER, dropin)
        postrm = (PACKAGING / 'erhai-display-power/postrm').read_text()
        for relative in (mode.MARKER, mode.UDEV_RULE, mode.GSD_DROPIN):
            self.assertIn(relative, postrm)



if __name__ == '__main__':
    unittest.main()
