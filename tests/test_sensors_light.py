# SPDX-License-Identifier: GPL-2.0-only
"""Reproduce nested Claim/Release against the upstream SSC light driver."""
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / 'packaging/sensors'


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# Resolve the pinned source cache the way the tools do (ERHAI_WORKSPACE or the
# checkout root), not by walking up from the tests directory.
BUILDER = load(REPO / 'tools/build-sensors.py', 'build_sensors')


PRELUDE = r'''
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int gboolean;
typedef struct { const char *message; } GError;
typedef struct {
    void *sensor;
    unsigned long measurement_id;
    gboolean polling_requested, polling_changing;
} DrvData;
typedef struct { void *priv; } SensorDevice;
#define TRUE 1
#define FALSE 0
#define g_autoptr(type) type *
#define G_CALLBACK(fn) NULL
#define g_signal_connect(sensor, name, callback, data) 1UL
#define g_clear_signal_handler(id, sensor) (*(id) = 0)
#define g_warning(...) ((void)0)
static void ssc_light_set_polling(SensorDevice *, gboolean);
static SensorDevice *current;
static int busy, overlap, mode, hook, opens, closes;
static GError failure = { "injected" };
static int ssc_sensor_light_open_sync(void *s, void *c, GError **error) {
    (void)s; (void)c;
    opens++; busy++;
    if (!hook++) {
        ssc_light_set_polling(current, FALSE);
        if (mode == 2) ssc_light_set_polling(current, TRUE);
    }
    busy--;
    if (mode == 3) { *error = &failure; return FALSE; }
    return TRUE;
}
static int ssc_sensor_light_close_sync(void *s, void *c, GError **error) {
    (void)s; (void)c; (void)error;
    closes++;
    if (busy) overlap++;
    return TRUE;
}
'''
EPILOGUE = r'''
int main(int argc, char **argv) {
    (void)argc;
    DrvData data = { .sensor = &data };
    SensorDevice device = { .priv = &data };
    current = &device;
    mode = atoi(argv[1]);
    ssc_light_set_polling(&device, TRUE);
    if (overlap || data.polling_changing) return 3;
    if (mode == 1 && (opens != 1 || closes != 1 || data.measurement_id)) return 4;
    if (mode == 2 && (opens != 1 || closes || !data.measurement_id)) return 5;
    if (mode == 3 && (opens != 1 || closes || data.measurement_id)) return 6;
    return 0;
}
'''


class LightTransitions(unittest.TestCase):
    def test_nested_release_and_latest_claim(self):
        pin = next(s for s in json.loads((INPUTS / 'sources.json').read_text())['sources']
                   if s['name'] == 'iio-sensor-proxy')
        archive = BUILDER.WS / 'cache/sensors' / pin['archive']
        if not archive.is_file() or not shutil.which('cc'):
            self.skipTest('requires pinned source cache and host C compiler')
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), pin['sha256'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with tarfile.open(archive) as tar:
                text = tar.extractfile(pin['directory'] + '/src/drv-ssc-light.c').read().decode()
            (root / 'src').mkdir()
            source = root / 'src/drv-ssc-light.c'
            source.write_text(text)
            patch = next(p for p in pin['patches'] if 'ssc-light-polling' in p['file'])
            path = INPUTS / patch['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), patch['sha256'])
            subprocess.run(['patch', '-p1', '--fuzz=0', '--batch', '-i', str(path)], cwd=root,
                           check=True, capture_output=True)
            for name, content in (('upstream', text), ('candidate', source.read_text())):
                start = content.index('static void\nssc_light_set_polling')
                end = content.index('\n}\n', start) + 3
                unit = root / f'{name}.c'
                unit.write_text(PRELUDE + content[start:end] + EPILOGUE)
                binary = root / name
                subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(unit), '-o', str(binary)],
                               check=True, capture_output=True)
                if name == 'upstream':
                    self.assertNotEqual(subprocess.run([str(binary), '1']).returncode, 0,
                                        'the unpatched driver must reproduce the nested close')
                else:
                    for scenario in ('1', '2', '3'):
                        self.assertEqual(subprocess.run([str(binary), scenario]).returncode, 0)


if __name__ == '__main__':
    unittest.main()
