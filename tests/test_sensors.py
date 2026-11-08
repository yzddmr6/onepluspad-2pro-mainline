# SPDX-License-Identifier: GPL-2.0-only
"""erhai-sensors: sample gate, registry import, delivery switch, sleep pause and recipe consistency."""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
TREE = REPO / 'packaging/erhai-sensors/tree'
INPUTS = REPO / 'packaging/sensors'
GATE = TREE / 'usr/libexec/erhai-sensors/ssc-sample-gate'
IMPORT = TREE / 'usr/sbin/erhai-sensors-import-registry'
DELIVERY = TREE / 'usr/sbin/erhai-sensors-ssc-delivery'
SLEEP = TREE / 'usr/libexec/erhai-sensors/sleep-streams'
SLEEP_UNIT = TREE / 'usr/lib/systemd/system/erhai-sensors-sleep.service'


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class GateTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.registry = self.dir / 'registry'
        self.registry.mkdir()
        (self.registry / 'bmi3x0_0_platform.accel.config').write_text('{}')
        self.state = self.dir / 'run'

    def tearDown(self):
        subprocess.run(['rm', '-rf', str(self.dir)], check=True)

    def fake(self, body):
        path = self.dir / 'ssccli'
        path.write_text('#!/bin/sh\n' + body)
        path.chmod(0o755)
        return path

    def gate(self, ssccli, bound=5):
        env = dict(os.environ, ERHAI_SENSORS_REGISTRY=str(self.registry),
                   ERHAI_SENSORS_SSCCLI=str(ssccli), ERHAI_SENSORS_STATE=str(self.state),
                   ERHAI_SENSORS_BOUND=str(bound), LC_ALL='C')
        result = subprocess.run([str(GATE)], env=env, capture_output=True, text=True)
        return result, (self.state / 'accel-gate.result').read_text()

    @staticmethod
    def samples(*vectors):
        return ''.join(f"echo 'Accelerometer sensor measurement: X={x:f} Y={y:f} Z={z:f} m/s²'\n"
                       for x, y, z in vectors)

    def test_gravity_passes(self):
        cli = self.fake(self.samples((0.1, -9.78, 0.4), (0.2, -9.80, 0.3), (0.1, -9.81, 0.2)))
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('result=pass', record)
        self.assertIn('samples=3 gravity=3', record)

    def test_light_unavailability_does_not_block_accelerometer(self):
        cli = self.fake('[ "$1" = --sensor=accelerometer ] || exit 42\n' +
                        self.samples((0, 0, 9.81)) * 3)
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('result=pass', record)
        self.assertFalse((self.state / 'light-gate.result').exists())

    def test_wrong_scale_fails(self):
        cli = self.fake(self.samples((0.0, -1.0, 0.0), (0.0, -1.0, 0.0), (0.0, -1.0, 0.0)))
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 1)
        self.assertIn('do not measure gravity', record)

    def test_too_few_samples_fail(self):
        cli = self.fake(self.samples((0.0, -9.81, 0.0)))
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 1)
        self.assertIn('result=fail', record)

    def test_init_failure_fails(self):
        cli = self.fake("echo 'Unable to initialize accelerometer sensor: UNKNOWN'\nexit 254\n")
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 1)
        self.assertIn('ssccli exit 254', record)

    def test_hang_is_bounded(self):
        cli = self.fake('exec sleep 60\n')
        start = time.monotonic()
        result, record = self.gate(cli, bound=1)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('no accelerometer sample', record)

    def test_missing_registry_fails_before_sampling(self):
        marker = self.dir / 'ran'
        cli = self.fake(f'touch {marker}\n' + self.samples((0, -9.81, 0)) * 3)
        for path in self.registry.iterdir():
            path.unlink()
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 1)
        self.assertIn('is empty', record)
        self.registry.rmdir()
        result, record = self.gate(cli)
        self.assertEqual(result.returncode, 1)
        self.assertIn('no imported sensor registry', record)
        self.assertFalse(marker.exists())


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.tool = load(IMPORT, 'erhai_sensors_import')
        self.dir = Path(tempfile.mkdtemp())
        self.source = self.dir / 'sensors'
        (self.source / 'registry/registry').mkdir(parents=True)
        for name in ('bmi3x0_0_platform.accel.config', 'sns_reg_config_ver'):
            (self.source / 'registry/registry' / name).write_text(name)
        (self.source / 'registry/sns_reg_version').write_bytes(b'version=2\0')
        self.soc = self.dir / 'soc0'
        self.soc.mkdir()
        (self.soc / 'hw_platform').write_text('MTP\n')
        (self.soc / 'soc_id').write_text('618\n')
        (self.soc / 'serial_number').write_text('12345\n')
        self.root = self.dir / 'root'

    def tearDown(self):
        subprocess.run(['rm', '-rf', str(self.dir)], check=True)

    def run_tool(self, *extra):
        return self.tool.main(['--root', str(self.root), *extra, str(self.source)])

    def test_import_copies_registry_and_known_socinfo(self):
        self.assertEqual(self.run_tool('--socinfo', str(self.soc)), 0)
        state = self.root / 'var/lib/erhai/sensors'
        self.assertEqual(sorted(p.name for p in (state / 'persist/registry').iterdir()),
                         ['bmi3x0_0_platform.accel.config', 'sns_reg_config_ver'])
        self.assertEqual((state / 'persist/sns_reg_version').read_bytes(), b'version=2\0')
        self.assertEqual(sorted(p.name for p in (state / 'socinfo').iterdir()),
                         ['hw_platform', 'soc_id'])
        record = json.loads((state / 'import.json').read_text())
        self.assertEqual(record['socinfo']['soc_id'], '618')
        self.assertEqual(len(record['registry']), 2)
        self.assertEqual([p.name for p in state.iterdir() if p.name.startswith('.import')], [])

    def test_reimport_replaces_previous_set(self):
        self.assertEqual(self.run_tool('--socinfo', str(self.soc)), 0)
        (self.source / 'registry/registry/sns_reg_config_ver').unlink()
        self.assertEqual(self.run_tool(), 0)
        state = self.root / 'var/lib/erhai/sensors'
        self.assertEqual([p.name for p in (state / 'persist/registry').iterdir()],
                         ['bmi3x0_0_platform.accel.config'])
        self.assertFalse((state / 'socinfo').exists())

    def test_rejects_symlink_entries(self):
        (self.source / 'registry/registry/link').symlink_to('/etc/passwd')
        self.assertEqual(self.run_tool(), 1)
        self.assertFalse((self.root / 'var/lib/erhai/sensors/persist').exists())

    def test_rejects_unexpected_names_and_layout(self):
        (self.source / 'registry/registry/.hidden').write_text('x')
        self.assertEqual(self.run_tool(), 1)
        (self.source / 'registry/registry/.hidden').unlink()
        empty = self.dir / 'empty'
        (empty / 'registry/registry').mkdir(parents=True)
        self.assertEqual(self.tool.main(['--root', str(self.root), str(empty)]), 1)
        self.assertEqual(self.tool.main(['--root', str(self.root), str(self.dir / 'soc0')]), 1)

    def test_rejects_binary_socinfo(self):
        (self.soc / 'revision').write_bytes(b'\xff\xfe')
        self.assertEqual(self.run_tool('--socinfo', str(self.soc)), 1)


class RecipeTest(unittest.TestCase):
    def test_pinned_patches_and_rom_config(self):
        lock = json.loads((INPUTS / 'sources.json').read_text())
        for source in lock['sources']:
            for patch in source['patches']:
                self.assertEqual(sha256(INPUTS / patch['file']), patch['sha256'], patch['file'])
        rom = json.loads((INPUTS / 'rom-config.json').read_text())
        installs = set()
        for entry in rom['files']:
            path = INPUTS / entry['file']
            self.assertEqual((path.stat().st_size, sha256(path)), (entry['size'], entry['sha256']))
            installs.add(entry['install'])
        self.assertIn('sensors/sns_reg.conf', installs)
        self.assertIn('sensors/config/json.lst', installs)
        self.assertIn('sensors/odm-config/json_list', installs)

    def test_units_point_at_packaged_paths(self):
        builder = load(REPO / 'tools/build-sensors.py', 'build_sensors')
        units = TREE / 'usr/lib/systemd/system'
        rpcd = (units / 'erhai-sensors-rpcd.service').read_text()
        self.assertIn(f'/{builder.PREFIX}/bin/hexagonrpcd ', rpcd)
        self.assertIn(f'-R /{builder.RPCD_ROOT}', rpcd)
        self.assertIn('-d adsp -s', rpcd)
        self.assertIn('Restart=no', rpcd)
        self.assertIn(f'ConditionDirectoryNotEmpty={builder.STATE}/persist/registry', rpcd)
        gate = (units / 'erhai-sensors-gate.service').read_text()
        self.assertIn('ExecStart=/usr/libexec/erhai-sensors/ssc-sample-gate', gate)
        self.assertIn('AF_QIPCRTR', gate)
        dropin = (units / 'iio-sensor-proxy.service.d/80-erhai-ssc.conf').read_text()
        self.assertIn(f'ExecStart=/{builder.PREFIX}/libexec/iio-sensor-proxy', dropin)
        self.assertIn('libexec/iio-sensor-proxy', builder.PAYLOAD)
        self.assertIn('bin/ssccli', builder.PAYLOAD)
        self.assertIn(f'/{builder.PREFIX}/bin/ssccli', GATE.read_text())

    def test_udev_rule_limits_proxy_to_gated_sensors(self):
        rule = (TREE / 'usr/lib/udev/rules.d/81-erhai-sensors.rules').read_text()
        self.assertIn('ENV{IIO_SENSOR_PROXY_TYPE}="ssc-accel ssc-light ssc-compass ssc-gyro"', rule)
        self.assertIn('ENV{ACCEL_MOUNT_MATRIX}="0, 1, 0; -1, 0, 0; 0, 0, 1"', rule)
        self.assertIn('SYMLINK+="erhai-sensors-fastrpc"', rule)
        # Sensor interrupt lines belong to the DSP; nothing here claims a GPIO.
        self.assertNotIn('gpio', rule.lower())


class DeliveryTest(unittest.TestCase):
    """erhai-sensors-ssc-delivery: the per-boot stream delivery switch."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.env_dir = self.dir / 'run/erhai-sensors-ssc'
        self.calls = self.dir / 'calls'
        systemctl = self.dir / 'systemctl'
        systemctl.write_text(f'#!/bin/sh\necho "$*" >> {self.calls}\n'
                             'case $1 in show) echo ActiveState=active; echo MainPID=42 ;; esac\n')
        systemctl.chmod(0o755)
        self.environ = dict(os.environ, ERHAI_SENSORS_SSC_ENV_DIR=str(self.env_dir),
                            ERHAI_SENSORS_SYSTEMCTL=str(systemctl), LC_ALL='C')

    def tearDown(self):
        subprocess.run(['rm', '-rf', str(self.dir)], check=True)

    def run_tool(self, *args):
        return subprocess.run([str(DELIVERY), *args], env=self.environ, capture_output=True,
                              text=True)

    def restarts(self):
        if not self.calls.exists():
            return []
        return [line for line in self.calls.read_text().splitlines() if 'restart' in line]

    def settings(self):
        return [line for line in (self.env_dir / 'env').read_text().splitlines()
                if not line.startswith('#')]

    def test_nowakeup_writes_the_environment_and_restarts_only_the_proxy(self):
        result = self.run_tool('nowakeup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.settings(), ['SSC_SUSPEND_MODE=nowakeup'])
        self.assertEqual(self.restarts(), ['try-restart iio-sensor-proxy.service'])
        self.assertIn('selection: SSC_SUSPEND_MODE=nowakeup', result.stdout)

    def test_batching_and_default(self):
        self.assertEqual(self.run_tool('--no-restart', 'wakeup', '2000000', '4000000').returncode, 0)
        self.assertEqual(self.settings(), ['SSC_SUSPEND_MODE=wakeup', 'SSC_BATCH_PERIOD_US=2000000',
                                           'SSC_FLUSH_PERIOD_US=4000000'])
        self.assertEqual(self.restarts(), [])
        result = self.run_tool('default')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.env_dir / 'env').exists())
        self.assertIn('selection: default', result.stdout)
        self.assertEqual(self.restarts(), ['try-restart iio-sensor-proxy.service'])

    def test_invalid_arguments_change_nothing(self):
        for args in (['sleep'], ['nowakeup', '0'], ['nowakeup', '2s'], ['nowakeup', '0200'],
                     ['nowakeup', '4294967296'], ['nowakeup', '1', '2', '3'], ['status', 'x'], []):
            with self.subTest(args=args):
                result = self.run_tool(*args)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.env_dir / 'env').exists())
                self.assertEqual(self.restarts(), [])
        self.assertEqual(self.run_tool('--no-restart', 'nowakeup', '4294967295').returncode, 0)

    def test_names_match_the_proxy_unit_and_libssc(self):
        text = DELIVERY.read_text()
        dropin = (TREE / 'usr/lib/systemd/system/iio-sensor-proxy.service.d/80-erhai-ssc.conf').read_text()
        self.assertIn('ENV_DIR=${ERHAI_SENSORS_SSC_ENV_DIR:-/run/erhai-sensors-ssc}', text)
        self.assertIn('EnvironmentFile=-/run/erhai-sensors-ssc/env', dropin)
        lock = json.loads((INPUTS / 'sources.json').read_text())
        libssc = next(s for s in lock['sources'] if s['name'] == 'libssc')
        patch = (INPUTS / libssc['patches'][0]['file']).read_text()
        for name in ('SSC_SUSPEND_MODE', 'SSC_BATCH_PERIOD_US', 'SSC_FLUSH_PERIOD_US'):
            self.assertIn(f'"{name}"', patch)
            self.assertIn(name + '=', text)
        # Only stream requests carry the chosen delivery.
        self.assertIn('config_msg.suspend_mode = streaming ? delivery->suspend_mode : '
                      'SSC_SUSPEND_MODE_WAKEUP;', patch)
        self.assertIn('+#define SSC_SUSPEND_MODE_NO_WAKEUP\t1', patch)

    def test_default_delivery_follows_the_sensor_type(self):
        """0002: motion streams non-wakeup, everything else wake-up, env still overrides."""
        lock = json.loads((INPUTS / 'sources.json').read_text())
        libssc = next(s for s in lock['sources'] if s['name'] == 'libssc')
        names = [Path(p['file']).name for p in libssc['patches']]
        self.assertEqual(names[:2], [
            '0001-libssc-select-the-delivery-and-batching-of-streams-at-run-time.patch',
            '0002-libssc-choose-the-stream-delivery-by-sensor-type.patch'])
        patch = (INPUTS / libssc['patches'][1]['file']).read_text()
        table = patch.split('+static const gchar * const no_wakeup_data_types[] = {', 1)[1]
        table = table.split('+};', 1)[0]
        types = [l.strip('+\t ",') for l in table.splitlines() if l.strip('+\t ')]
        self.assertEqual(types, ['accel', 'gyro', 'mag', 'rotv'])
        # The sensor passes its data type with the stream request.
        self.assertIn('+\tssc_client_send_for_sensor (priv->client,\n+\t\t\t\t    priv->data_type,', patch)
        # Unset means per type; wakeup and nowakeup still override.
        self.assertIn('+\tconfig->suspend_mode = SSC_SUSPEND_MODE_BY_SENSOR_TYPE;', patch)
        self.assertIn('+\t\telse if (g_str_equal (mode, "wakeup"))', patch)
        # The delivery type is the only per-type choice: batching comes from
        # SSC_BATCH_PERIOD_US alone.
        self.assertIn('+\t*delivery = *overrides;\n+\tif (delivery->suspend_mode == '
                      'SSC_SUSPEND_MODE_BY_SENSOR_TYPE)\n', patch)
        self.assertIn('Assisted-by: LLM', patch)
        self.assertIn('by sensor type: accelerometer non-wakeup, no batching', DELIVERY.read_text())



class SleepStreamsTest(unittest.TestCase):
    """sleep-streams: stop the proxy before sleep, start it again after."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.state = self.dir / 'run/erhai-sensors-sleep'
        self.calls = self.dir / 'calls'
        self.unit_state = self.dir / 'unit-state'
        self.unit_state.write_text('active')
        systemctl = self.dir / 'systemctl'
        # A proxy that is active (or whatever unit-state says) with PID 42;
        # "stop" hangs while stop-hangs exists.
        systemctl.write_text(f"""#!/bin/sh
echo "$*" >> {self.calls}
case "$1 $2" in
'show iio-sensor-proxy.service')
    case "$4" in
    ActiveState) cat {self.unit_state} ;;
    MainPID) echo 42 ;;
    esac ;;
'stop iio-sensor-proxy.service')
    [ -e {self.dir}/stop-hangs ] && sleep 5
    echo inactive > {self.unit_state} ;;
'--no-block start') echo active > {self.unit_state} ;;
esac
""")
        systemctl.chmod(0o755)
        self.environ = dict(os.environ, ERHAI_SENSORS_SYSTEMCTL=str(systemctl),
                            ERHAI_SENSORS_SLEEP_STATE=str(self.state),
                            ERHAI_SENSORS_SLEEP_BOUND='1', LC_ALL='C')

    def tearDown(self):
        subprocess.run(['rm', '-rf', str(self.dir)], check=True)

    def run_tool(self, *args):
        return subprocess.run([str(SLEEP), *args], env=self.environ, capture_output=True,
                              text=True, timeout=20)

    def actions(self):
        if not self.calls.exists():
            return []
        return [line for line in self.calls.read_text().splitlines()
                if not line.startswith('show ')]

    def test_pause_stops_a_running_proxy_and_resume_starts_it_again(self):
        result = self.run_tool('pause')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.actions(), ['stop iio-sensor-proxy.service'])
        self.assertEqual((self.state / 'proxy-stopped').read_text().strip(), '42')
        self.assertIn('stopped iio-sensor-proxy.service (PID 42)', result.stdout)
        result = self.run_tool('resume')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.actions(), ['stop iio-sensor-proxy.service',
                                          '--no-block start iio-sensor-proxy.service'])
        self.assertFalse((self.state / 'proxy-stopped').exists())
        self.assertIn('starting iio-sensor-proxy.service again (was PID 42)', result.stdout)

    def test_a_proxy_that_is_not_running_is_left_alone(self):
        for state in ('inactive', 'failed', ''):
            with self.subTest(state=state):
                self.unit_state.write_text(state)
                self.assertEqual(self.run_tool('pause').returncode, 0)
                self.assertEqual(self.run_tool('resume').returncode, 0)
                self.assertEqual(self.actions(), [])
        # A stale mark from an earlier pause does not start it either.
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / 'proxy-stopped').write_text('7\n')
        self.unit_state.write_text('failed')
        self.run_tool('pause')
        self.run_tool('resume')
        self.assertEqual(self.actions(), [])

    def test_a_starting_proxy_is_paused_too(self):
        self.unit_state.write_text('activating')
        self.run_tool('pause')
        self.run_tool('resume')
        self.assertEqual(self.actions(), ['stop iio-sensor-proxy.service',
                                          '--no-block start iio-sensor-proxy.service'])

    def test_a_stop_that_hangs_is_bounded_and_resume_still_starts(self):
        (self.dir / 'stop-hangs').write_text('')
        started = time.monotonic()
        result = self.run_tool('pause')
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(result.returncode, 0)
        self.assertIn('did not finish within 1 s', result.stderr)
        self.run_tool('resume')
        self.assertEqual(self.actions()[-1], '--no-block start iio-sensor-proxy.service')

    def test_usage(self):
        for args in ([], ['stop'], ['pause', 'x']):
            with self.subTest(args=args):
                result = self.run_tool(*args)
                if args[:1] == ['pause']:
                    self.assertEqual(result.returncode, 0)
                else:
                    self.assertEqual(result.returncode, 2)

    def test_unit_orders_before_sleep_and_is_enabled_by_the_package(self):
        unit = SLEEP_UNIT.read_text()
        for line in ('Before=sleep.target', 'StopWhenUnneeded=yes', 'Type=oneshot',
                     'RemainAfterExit=yes', 'WantedBy=sleep.target',
                     'ExecStart=/usr/libexec/erhai-sensors/sleep-streams pause',
                     'ExecStop=/usr/libexec/erhai-sensors/sleep-streams resume',
                     'RuntimeDirectory=erhai-sensors-sleep'):
            self.assertIn(line + '\n', unit)
        self.assertIn('${RUNTIME_DIRECTORY:-/run/erhai-sensors-sleep}', SLEEP.read_text())
        # The unit's own bound is longer than the script's.
        self.assertIn('BOUND=${ERHAI_SENSORS_SLEEP_BOUND:-15}', SLEEP.read_text())
        self.assertIn('TimeoutStartSec=30s', unit)
        package = REPO / 'packaging/erhai-sensors'
        postinst = (package / 'postinst').read_text()
        self.assertIn('deb-systemd-helper --quiet was-enabled erhai-sensors-sleep.service', postinst)
        self.assertIn('deb-systemd-helper enable erhai-sensors-sleep.service', postinst)
        postrm = (package / 'postrm').read_text()
        self.assertIn('deb-systemd-helper mask erhai-sensors-sleep.service', postrm)
        self.assertIn('deb-systemd-helper purge erhai-sensors-sleep.service', postrm)
        # The file server and the sample gate are not part of the pause.
        script = SLEEP.read_text()
        self.assertNotIn('erhai-sensors-rpcd', script.split('set -u', 1)[1])
        self.assertNotIn('erhai-sensors-gate', script.split('set -u', 1)[1])
        for name in ('postinst', 'postrm', 'prerm'):
            subprocess.run(['dash', '-n', str(package / name)], check=True)
        subprocess.run(['dash', '-n', str(SLEEP)], check=True)


def scalars(sc):
    """Split FastRPC scalars into (method, inbufs, outbufs, handles)."""
    return (sc >> 24) & 0x1f, (sc >> 16) & 0xff, (sc >> 8) & 0xff, sc & 0xff


class ReverseRpcTest(unittest.TestCase):
    """The ADSP sensor domain's apps_std method 36 and refused requests."""

    # Logged by hexagonrpcd on the tablet: "Unsupported method: 36 (1f050100)".
    LOGGED_SC = 0x1f050100

    def hexagonrpc_patches(self):
        lock = json.loads((INPUTS / 'sources.json').read_text())
        source = next(s for s in lock['sources'] if s['name'] == 'hexagonrpc')
        return [INPUTS / p['file'] for p in source['patches']]

    def test_logged_scalars_are_extended_fopen_with_env_fd(self):
        # Method field 31 means "real ID in the first input word"; the
        # reference skel's fopen_with_env_fd takes the primary input plus
        # four strings and returns one primary output { fd, len }.
        self.assertEqual(scalars(self.LOGGED_SC), (31, 5, 1, 0))
        patch = self.hexagonrpc_patches()[3].read_text()
        self.assertIn('.msg_id = 36,', patch)
        self.assertIn('#define APPS_STD_FOPEN_WITH_ENV_FD_SC REMOTE_SCALARS_MAKE(31, 5, 1)', patch)
        self.assertEqual(patch.count('{ HRPC_ARG_BLOB_SEQ, sizeof(char) },\n'), 4)
        self.assertEqual(patch.count('{ HRPC_ARG_OUT_BLOB, sizeof(uint32_t) },\n'), 2)
        self.assertIn('.strict_sc = true,', patch)

    def test_series_order_and_refusal_patch(self):
        names = [p.name for p in self.hexagonrpc_patches()]
        self.assertEqual([n[:4] for n in names], ['0001', '0002', '0003', '0004', '0005', '0006'])
        refusal = self.hexagonrpc_patches()[4].read_text()
        # A refusal is answered with no output buffers and the loop goes on;
        # the reason stays in the journal for the bring-up check.
        self.assertIn('outbufs_len = 0;', refusal)
        self.assertIn('Refused request on handle', refusal)
        self.assertIn('+\t\t\tret = 0;\n', refusal)

    def test_hexagonrpc_host_suite(self):
        """Build the patched hexagonrpc on the host and run its tests."""
        builder = load(REPO / 'tools/build-sensors.py', 'build_sensors')
        lock = json.loads((INPUTS / 'sources.json').read_text())
        source = next(s for s in lock['sources'] if s['name'] == 'hexagonrpc')
        archive = builder.WS / 'cache/sensors' / source['archive']
        missing = [t for t in ('meson', 'ninja', 'cc', 'patch') if shutil.which(t) is None]
        if missing or not archive.is_file():
            self.skipTest(f'needs {missing or archive}')
        self.assertEqual(sha256(archive), source['sha256'])
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['tar', '-xzf', str(archive), '-C', tmp], check=True)
            tree = Path(tmp) / source['directory']
            for patch in self.hexagonrpc_patches():
                subprocess.run(['patch', '-d', str(tree), '-p1', '--batch', '--fuzz=0',
                                '-i', str(patch)], check=True, stdout=subprocess.DEVNULL)
            build = Path(tmp) / 'build'
            subprocess.run(['meson', 'setup', str(build), str(tree)], check=True,
                           stdout=subprocess.DEVNULL)
            result = subprocess.run(['meson', 'test', '-C', str(build), '--print-errorlogs'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout[-4000:])
            for name in ('apps-std-fd', 'listener-refusal', 'sns-registry', 'odm-sensor-config'):
                self.assertRegex(result.stdout, rf'{name}\s+OK')


if __name__ == '__main__':
    unittest.main()
