# SPDX-License-Identifier: GPL-2.0-only
"""Refusal boundaries before any device transition or partition write."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('erhai_install', TOOLS / 'install.py')
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallBoundaries(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.work = Path(self.directory.name)
        self.args = SimpleNamespace(work=self.work, serial='TEST_DEVICE', erase_linux=True)
        self.installer = install.Installer(self.args)
        self.installer.run = Mock(side_effect=AssertionError('device command reached'))
        firmware = json.loads((install.REPO / 'packaging/installation.json').read_text())['tested_firmware_fingerprints'][0]
        self.plan = {'serial': self.args.serial, 'slot': '_a', 'firmware': firmware,
                     'partitions': {
                         'userdata': {'device': '/dev/block/sda15', 'bytes': 4096, 'start_512': 8},
                         'linux_rootfs': {'device': '/dev/block/sda16', 'bytes': 4096, 'start_512': 16},
                         'linux_data': {'device': '/dev/block/sda17', 'bytes': 4096, 'start_512': 24}}}
        self.installer.load_backup = Mock(return_value=self.plan)
        self.installer.inspect = Mock(return_value=self.plan)

    def tearDown(self):
        self.installer.log.close()
        self.directory.cleanup()

    def test_explicit_erase_is_required_before_inspection(self):
        self.args.erase_linux = False
        with self.assertRaisesRegex(RuntimeError, '--erase-linux'):
            self.installer.install()
        self.installer.inspect.assert_not_called()
        self.installer.run.assert_not_called()

    def test_changed_layout_is_rejected_before_transition(self):
        self.installer.inspect.return_value = {**self.plan, 'slot': '_b'}
        with self.assertRaisesRegex(RuntimeError, 'layout or firmware changed'):
            self.installer.install()
        self.installer.run.assert_not_called()

    def test_changed_partition_geometry_is_rejected(self):
        # A real repartition must still stop the install before any transition.
        changed = {**self.plan, 'partitions': {
            **self.plan['partitions'],
            'linux_rootfs': {**self.plan['partitions']['linux_rootfs'], 'bytes': 8192}}}
        self.installer.inspect.return_value = changed
        with self.assertRaisesRegex(RuntimeError, 'layout or firmware changed'):
            self.installer.install()
        self.installer.run.assert_not_called()

    def test_partition_node_rename_is_not_a_layout_change(self):
        """UFS LUN probe order moves /dev/block/sdX between boots.

        The same boot_a has been observed as sdd12 before a reboot and sde12
        after it, with identical size and start sector. That must not read as
        a changed layout, or every install after a reboot would abort.
        """
        renamed = {name: {**part, 'device': part['device'].replace('/sda', '/sde')}
                   for name, part in self.plan['partitions'].items()}
        self.installer.inspect.return_value = {**self.plan, 'partitions': renamed}
        # Past the layout gate the run stops on the missing prepared images.
        with self.assertRaises(FileNotFoundError):
            self.installer.install()

    def test_unchanged_but_unsupported_firmware_is_rejected(self):
        self.plan['firmware'] = 'untested OTA'
        with self.assertRaisesRegex(RuntimeError, 'outside the tested'):
            self.installer.install()
        self.installer.run.assert_not_called()

    def test_distinct_partition_nodes_cannot_overlap_android(self):
        self.plan['partitions']['linux_rootfs']['start_512'] = 12
        with self.assertRaisesRegex(RuntimeError, 'disjoint and follow Android'):
            self.installer.install()
        self.installer.run.assert_not_called()

    def test_same_device_in_two_work_directories_is_locked(self):
        first = ['install.py', '--serial', 'LOCK_TEST', '--work', str(self.work / 'one'), '--phase', 'install']
        second = ['install.py', '--serial', 'LOCK_TEST', '--work', str(self.work / 'two'), '--phase', 'install']
        def attempt_second():
            with patch.object(sys, 'argv', second), self.assertRaises(BlockingIOError):
                install.main()
        with patch.dict('os.environ', {'XDG_RUNTIME_DIR': str(self.work / 'runtime')}), \
                patch.object(install.Installer, 'install', side_effect=attempt_second) as action, \
                patch.object(sys, 'argv', first):
            install.main()
            self.assertEqual(action.call_count, 1)

    def test_prepared_image_for_another_device_is_rejected(self):
        (self.work / 'prepared.json').write_text(json.dumps({'serial': 'OTHER_DEVICE'}))
        with self.assertRaisesRegex(RuntimeError, 'another tablet'):
            self.installer.install()
        self.installer.run.assert_not_called()

    def test_android_userdata_cannot_be_a_flash_target(self):
        (self.work / 'prepared.json').write_text(json.dumps({
            'serial': self.args.serial, 'images': {'userdata': {}}}))
        with self.assertRaisesRegex(RuntimeError, 'Unexpected flash target'):
            self.installer.install()
        self.installer.run.assert_not_called()

    def test_incomplete_linux_set_is_rejected(self):
        (self.work / 'prepared.json').write_text(json.dumps({
            'serial': self.args.serial, 'images': {}}))
        with self.assertRaisesRegex(RuntimeError, 'Both Linux images'):
            self.installer.install()
        self.installer.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
