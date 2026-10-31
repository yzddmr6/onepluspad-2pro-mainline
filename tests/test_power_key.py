# SPDX-License-Identifier: GPL-2.0-only
"""Authentication boundaries of the tablet's power-key policy."""
import configparser
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / (
    'packaging/erhai-device-support/tree/usr/sbin/erhai-power-key')
loader = importlib.machinery.SourceFileLoader('power_key', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
key = importlib.util.module_from_spec(spec)
loader.exec_module(key)


class PowerKeyTest(unittest.TestCase):
    standard = False

    def run_action(self, mode, session_class='user', locked='no', failure=None,
                   resumed=False, action=None, active='(true,)'):
        calls = []
        info = {'User': '1000', 'Class': session_class, 'LockedHint': locked}

        def screen(_info, method, *args):
            calls.append((method, *args))
            if failure and method == 'Lock':
                raise RuntimeError(failure)
            return active

        def power(_info, value=None):
            if value is not None:
                calls.append(('power', value))
            return mode

        def unused(_info, value=None):
            raise AssertionError('the other display backend was used')

        wake = Mock()
        used, other = ('mutter_mode', 'power_mode') if self.standard else (
            'power_mode', 'mutter_mode')
        with patch.object(key, 'active_session', return_value=info), \
                patch.object(key, 'standard_path', return_value=self.standard), \
                patch.object(key, 'screensaver', side_effect=screen), \
                patch.object(key, used, side_effect=power), \
                patch.object(key, other, side_effect=unused), \
                patch.object(key, 'SUSPEND_MARKERS', () if action is None else (
                    Mock(read_text=Mock(return_value=action)),)), \
                patch.object(key, 'command', side_effect=lambda argv: calls.append(tuple(argv))), \
                patch.object(key.time, 'monotonic', side_effect=(0, 4)):
            if failure or active != '(true,)':
                with self.assertRaises(RuntimeError):
                    key.toggle(wake, resumed=resumed)
            else:
                key.toggle(wake, resumed=resumed)
        return calls, wake

    def test_default_locks_and_blanks_before_suspend(self):
        calls, wake = self.run_action(0)
        self.assertEqual(calls, [('Lock',), ('GetActive',), ('power', 3),
                                 ('systemctl', '--no-block', 'suspend')])
        wake.wake.assert_not_called()

    def test_lock_failure_does_not_hide_an_unlocked_desktop(self):
        calls, _ = self.run_action(0, failure='lock denied')
        self.assertEqual(calls, [('Lock',)])

    def test_inactive_lock_does_not_blank_or_suspend(self):
        calls, _ = self.run_action(0, active='(false,)')
        self.assertEqual(calls, [('Lock',), ('GetActive',)])

    def test_greeter_keeps_its_login_policy(self):
        calls, _ = self.run_action(0, session_class='greeter')
        self.assertEqual(calls, [('power', 3), ('systemctl', '--no-block', 'suspend')])

    def test_greeter_wake_does_not_hide_the_login_dialog(self):
        calls, wake = self.run_action(3, session_class='greeter')
        self.assertEqual(calls, [('power', 0)])
        wake.wake.assert_called_once_with()

    def test_repeated_blank_of_locked_session(self):
        calls, _ = self.run_action(0, locked='yes')
        self.assertNotIn(('Lock',), calls)
        self.assertIn(('power', 3), calls)
        self.assertEqual(calls[-1], ('systemctl', '--no-block', 'suspend'))

    def test_blank_opt_out_still_locks(self):
        calls, wake = self.run_action(0, action='blank')
        self.assertEqual(calls, [('Lock',), ('GetActive',), ('power', 3)])
        wake.wake.assert_not_called()

    def test_resume_press_only_restores_display(self):
        for session_class in ('user', 'greeter'):
            with self.subTest(session_class=session_class):
                calls, wake = self.run_action(0, session_class=session_class, resumed=True)
                self.assertEqual(calls, [('power', 0)])
                wake.wake.assert_called_once_with()

    def test_wake_never_deactivates_the_lock_screen(self):
        for mode in (1, 2, 3):
            with self.subTest(mode=mode):
                calls, wake = self.run_action(mode, locked='yes')
                self.assertEqual(calls, [('power', 0)])
                wake.wake.assert_called_once_with()

    def test_unknown_display_state_does_not_change_power(self):
        calls, wake = self.run_action(-1, failure='unknown')
        self.assertEqual(calls, [])
        wake.wake.assert_not_called()


class StandardPathTest(PowerKeyTest):
    """The same boundaries when the key drives Mutter's PowerSaveMode."""
    standard = True


class SuspendPolicyTest(unittest.TestCase):
    def test_default_opt_out_and_marker_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, etc = Path(tmp) / 'run-marker', Path(tmp) / 'etc-marker'
            for runtime, persistent, expected in (
                    (None, None, True), (None, 'suspend\n', True),
                    (None, 'blank\n', False), ('blank', 'suspend', False),
                    ('suspend', 'blank', True), ('invalid', 'blank', False),
                    ('blank', None, False), ('', '', True), (None, 'invalid', True)):
                with self.subTest(runtime=runtime, persistent=persistent):
                    for marker, value in ((run, runtime), (etc, persistent)):
                        if value is None:
                            marker.unlink(missing_ok=True)
                        else:
                            marker.write_text(value)
                    with patch.object(key, 'SUSPEND_MARKERS', (run, etc)):
                        self.assertEqual(key.suspend_requested(), expected)

    def test_desktop_inherits_idle_policy_and_keeps_lock_and_key_ownership(self):
        tree = SOURCE.parents[2]
        settings = configparser.ConfigParser()
        settings.read(tree / 'usr/share/glib-2.0/schemas/90_erhai-power.gschema.override')
        self.assertEqual({section: dict(settings[section]) for section in settings.sections()}, {
            'org.gnome.settings-daemon.plugins.power': {'power-button-action': "'nothing'"},
            'org.gnome.desktop.screensaver': {'lock-enabled': 'true'},
        })
        logind = configparser.ConfigParser()
        logind.read(tree / 'etc/systemd/logind.conf.d/90-erhai-power.conf')
        self.assertEqual(logind['Login']['HandlePowerKey'], 'ignore')
        self.assertEqual(logind['Login']['HandleLidSwitch'], 'suspend')


class MutterBackendTest(unittest.TestCase):
    info = {'User': '1000', 'Class': 'greeter'}

    def test_reads_and_sets_power_save_mode(self):
        calls = []

        def session(_info, dest, path, method, *args):
            calls.append((dest, path, method, *args))
            return '(<3>,)'
        with patch.object(key, 'call_session', side_effect=session):
            self.assertEqual(key.mutter_mode(self.info), 3)
            self.assertEqual(key.mutter_mode(self.info, 0), 0)
        interface = 'org.gnome.Mutter.DisplayConfig'
        self.assertEqual(calls, [
            (interface, '/org/gnome/Mutter/DisplayConfig',
             'org.freedesktop.DBus.Properties.Get', interface, 'PowerSaveMode'),
            (interface, '/org/gnome/Mutter/DisplayConfig',
             'org.freedesktop.DBus.Properties.Set', interface, 'PowerSaveMode', '<0>')])

    def test_unreadable_reply_is_refused(self):
        for reply in ('', '(<"on">,)', '(3,)'):
            with self.subTest(reply=reply), \
                    patch.object(key, 'call_session', return_value=reply), \
                    self.assertRaises(RuntimeError):
                key.mutter_mode(self.info)

    def test_marker_selects_the_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, etc = Path(tmp) / 'run-marker', Path(tmp) / 'etc-marker'
            with patch.object(key, 'MODE_MARKERS', (run, etc)):
                self.assertFalse(key.standard_path())
                etc.write_text('compat\n')
                self.assertFalse(key.standard_path())
                etc.write_text('standard\n')
                self.assertTrue(key.standard_path())
                etc.unlink()
                run.write_text('standard\n')
                self.assertTrue(key.standard_path())


class SuspendCycleTest(unittest.TestCase):
    def test_recent_resume_is_consumed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, stamp = Path(tmp) / 'cycle', Path(tmp) / 'resumed'
            flag.touch()
            stamp.touch()
            with patch.object(key, 'RESUME_FLAG', flag), \
                    patch.object(key, 'RESUMED_STAMP', stamp):
                self.assertTrue(key.suspended_since_last_press())
                self.assertFalse(key.suspended_since_last_press())
            self.assertFalse(stamp.exists())

    def test_no_resume_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, stamp = Path(tmp) / 'cycle', Path(tmp) / 'resumed'
            with patch.object(key, 'RESUME_FLAG', flag), \
                    patch.object(key, 'RESUMED_STAMP', stamp):
                self.assertFalse(key.suspended_since_last_press())

    def test_resume_flag_without_post_stamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, stamp = Path(tmp) / 'cycle', Path(tmp) / 'resumed'
            flag.touch()
            with patch.object(key, 'RESUME_FLAG', flag), \
                    patch.object(key, 'RESUMED_STAMP', stamp):
                self.assertTrue(key.suspended_since_last_press())
            self.assertFalse(flag.exists())

    def test_stale_resume_flag_is_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, stamp = Path(tmp) / 'cycle', Path(tmp) / 'resumed'
            flag.touch()
            stamp.touch()
            old = time.time() - 60
            os.utime(stamp, (old, old))
            with patch.object(key, 'RESUME_FLAG', flag), \
                    patch.object(key, 'RESUMED_STAMP', stamp):
                self.assertFalse(key.suspended_since_last_press())
            self.assertFalse(flag.exists())
            self.assertFalse(stamp.exists())


if __name__ == '__main__':
    unittest.main()
