# SPDX-License-Identifier: MIT
"""The previous batch must not be asked to retain packages it never managed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'packaging/mesa/shared/tools'
spec = importlib.util.spec_from_file_location(
    'release_repository', TOOLS / 'release-repository.py')
release_repository = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_repository)


def row(package, version, source):
    return dict(package=package, version=version, architecture='arm64',
                source=source,
                file='pool/' + package + '_' + version + '_arm64.deb',
                sha256='0' * 64, bytes=1, install=True)


def batch(identifier, rows):
    return dict(schema=1, id=identifier, product='erhai', packages=rows)


DEVICE = row('erhai-device', '0.8.1+b1f68d8c8', 'erhai-device')
# v0.9.0 added these ordinary Ubuntu libraries to its release batch. Qt and
# fcitx5 already had four of them installed at exactly these versions.
ADDED = [
    row('libxcb-render-util0', '0.3.10-1build1', 'libxcb'),
    row('libxcb-ewmh2', '0.4.2-1build1', 'xcb-util-wm'),
    row('libxcb-icccm4', '0.4.2-1build1', 'xcb-util-wm'),
    row('libxcb-xinput0', '1.17.0-2ubuntu1', 'libxcb'),
]


class PreviousBatchCohort(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Path(self.directory.name) / 'releases'
        self.store.mkdir()
        self.previous = Path(self.directory.name) / 'erhai-0.8.1'
        self.old = batch('erhai-0.8.1', [DEVICE])

    def tearDown(self):
        self.directory.cleanup()

    def resolve(self, new_rows, before):
        return release_repository.previous_for_installed(
            self.previous, self.old, batch('erhai-0.9.0', new_rows),
            before, self.store)

    def test_new_dependencies_at_new_version_do_not_block_upgrade(self):
        """Regression for erhai v0.8.1 -> v0.9.0.

        The upgrade leaves these packages untouched and a rollback has nothing
        to restore, so no exact .deb is needed in the previous batch.
        """
        before = {'erhai-device': DEVICE['version']}
        before.update({r['package']: r['version'] for r in ADDED})
        got_previous, got_old = self.resolve([DEVICE, *ADDED], before)
        self.assertIs(got_previous, self.previous)
        self.assertIs(got_old, self.old)
        self.assertFalse((self.store / 'erhai-0.8.1-before-erhai-0.9.0').exists())

    def test_new_dependency_at_other_version_is_still_rejected(self):
        before = {'erhai-device': DEVICE['version'], 'libxcb-ewmh2': '0.4.1-1'}
        with self.assertRaisesRegex(ValueError, 'previous batch is missing'):
            self.resolve([DEVICE, ADDED[1]], before)

    def test_drifted_release_package_is_still_rejected(self):
        before = {'erhai-device': '0.8.0+other'}
        with self.assertRaisesRegex(ValueError, 'previous batch is missing'):
            self.resolve([DEVICE], before)

    def test_unchanged_cohort_is_returned_untouched(self):
        before = {'erhai-device': DEVICE['version']}
        got_previous, got_old = self.resolve([DEVICE], before)
        self.assertIs(got_previous, self.previous)
        self.assertIs(got_old, self.old)


if __name__ == '__main__':
    unittest.main()
