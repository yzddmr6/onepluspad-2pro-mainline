# SPDX-License-Identifier: GPL-2.0-only
"""erhai-audio: the topology guard against unopenable PCMs, dangling routes
and module configurations the kernel or the DSP would misapply."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
# build-debs.py imports its helpers from tools/lib, as it does when run.
sys.path.insert(0, str(REPO / 'tools'))
INPUTS = REPO / 'packaging/audio'


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


build = load(REPO / 'tools/build-debs.py', 'build_debs')
SOURCE = json.loads((INPUTS / 'source.json').read_text())
WIDGETS = SOURCE['kernel_dai_widgets']


def recipe_conf():
    """The board recipe expanded with m4 against the pinned upstream archive."""
    archive = build.WS / 'cache' / SOURCE['archive']
    if not shutil.which('m4') or not archive.is_file():
        raise unittest.SkipTest('m4 or the pinned audioreach-topology archive is missing')
    with tempfile.TemporaryDirectory() as directory:
        with tarfile.open(archive) as tar:
            tar.extractall(directory, filter='data')
        upstream = Path(directory) / SOURCE['directory']
        return subprocess.run(['m4', '-I', str(INPUTS), '-I', str(upstream),
                               str(INPUTS / (SOURCE['model'] + '.m4'))],
                              capture_output=True, text=True, check=True).stdout


def compile_conf(conf):
    """The binary alsatplg makes of a topology conf."""
    if not shutil.which('alsatplg'):
        raise unittest.SkipTest('alsatplg is missing')
    with tempfile.TemporaryDirectory() as directory:
        source, target = Path(directory) / 't.conf', Path(directory) / 't.bin'
        source.write_text(conf)
        subprocess.run(['alsatplg', '-c', str(source), '-o', str(target)],
                       capture_output=True, check=True)
        return target.read_bytes()


def mix(rows, frame):
    """What the MFC puts on each output for one input frame (Q14 rows)."""
    return [sum(c * x for c, x in zip(row, frame)) / build.Q14_UNITY for row in rows]


class TopologyGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conf = recipe_conf()

    def rejects(self, text, widgets=WIDGETS):
        with self.assertRaises(SystemExit) as caught:
            build.check_topology(text, widgets)
        return str(caught.exception)

    def test_board_recipe_passes(self):
        build.check_topology(self.conf, WIDGETS)

    def test_front_end_format_the_platform_cannot_serve(self):
        # The 0.1.36 speaker graph: S32_LE only, so aplay failed with EINVAL
        # at open and the kernel said nothing about it.
        start = self.conf.index('SectionPCMCapabilities."MultiMedia1 Playback"')
        old = self.conf[:start] + self.conf[start:].replace('"S16_LE"', '"S32_LE"', 1)
        self.assertIn("offers ['S32_LE']", self.rejects(old))

    def test_routes_must_end_at_real_widgets_and_controls(self):
        renamed = self.conf.replace('"Secondary TDM0 Playback, , device40.tdm_rx1"',
                                    '"Secondary TDM Playback, , device40.tdm_rx1"')
        self.assertIn("'Secondary TDM Playback'", self.rejects(renamed))
        control = self.conf.replace('Secondary TDM0 Audio Mixer, MultiMedia1, stream0.logger1',
                                    'Secondary TDM0 Audio Mixer, MultiMedia2, stream0.logger1')
        self.assertIn("no mixer control 'MultiMedia2'", self.rejects(control))

    def test_front_end_must_reach_a_back_end(self):
        cut = self.conf.replace('"device40.mfc1, , device40.logger1"', '')
        self.assertIn("'MultiMedia1 Playback' reaches no back-end", self.rejects(cut))
        cut = self.conf.replace('"device120.logger1, , device120.codec_dma_tx1"', '')
        self.assertIn("'MultiMedia3 Capture' reaches no back-end", self.rejects(cut))

    def test_front_end_wider_than_the_media_format_commands(self):
        # The 0.1.40 speaker graph: eight channels opened, then prepare failed
        # with "Invalid channels (8)" before any command reached the DSP.
        start = self.conf.index('SectionPCMCapabilities."MultiMedia1 Playback"')
        head, tail = self.conf[:start], self.conf[start:]
        wide = head + tail.replace('channels_min "4"', 'channels_min "8"', 1).replace(
            'channels_max "4"', 'channels_max "8"', 1)
        self.assertIn('channel range outside q6apm-dai 2..4', self.rejects(wide))

    def test_every_declared_back_end_is_used(self):
        self.assertIn('Quinary TDM0 Playback',
                      self.rejects(self.conf, WIDGETS + ['Quinary TDM0 Playback']))


class SpeakerMixing(unittest.TestCase):
    """The stereo front end spread over the eight TDM slots inside the DSP."""

    @classmethod
    def setUpClass(cls):
        cls.conf = recipe_conf()
        cls.blob = compile_conf(cls.conf)

    def rejects(self, conf):
        with self.assertRaises(SystemExit) as caught:
            build.check_module_configs(compile_conf(conf))
        return str(caught.exception)

    def test_stereo_front_end_and_eight_slot_back_end(self):
        start = self.conf.index('SectionPCMCapabilities."MultiMedia1 Playback"')
        caps = self.conf[start:self.conf.index('}', start)]
        self.assertIn('channels_min "4"', caps)
        self.assertIn('channels_max "4"', caps)
        tdm = self.conf[self.conf.index('SectionVendorTuples."device40.tdm_rx1_tuples"'):]
        self.assertIn('AR_TKN_U16_MODULE_NSLOTS_PER_FRAME "8"', tdm)
        self.assertIn('AR_TKN_U32_MODULE_SLOT_MASK "0xff"', tdm)

    def test_left_on_even_slots_right_on_odd(self):
        configs = build.check_module_configs(self.blob)
        self.assertEqual(list(configs), ['device40.mfc1'])
        tables = configs['device40.mfc1'][build.AR_PARAM_ID_CHMIXER_COEFF]
        self.assertEqual(len(tables), 1)
        out_map, in_map, rows = tables[0]
        self.assertEqual(tuple(in_map), build.KERNEL_CHANNEL_MAPS[4])
        self.assertEqual(tuple(out_map), build.KERNEL_CHANNEL_MAPS[8])
        self.assertEqual(mix(rows, (1, 0, 0, 0)), [1, 0, 0, 0, 0, 0, .5, 0])
        self.assertEqual(mix(rows, (0, 1, 0, 0)), [0, 0, 0, 1, 0, .5, 0, 0])
        self.assertEqual(mix(rows, (0, 0, 1, 0)), [0, 0, 1, 0, 0, 0, .5, 0])
        self.assertEqual(mix(rows, (0, 0, 0, 1)), [0, 1, 0, 0, 0, .5, 0, 0])

    def test_blob_sits_behind_the_module_tokens(self):
        # audioreach_get_{sg,cont,module}_array() stop at the first array
        # holding their token; the blob must come after all of them.
        private = dict(build.topology_widgets(self.blob))['device40.mfc1']
        tokens, config = build.module_config('device40.mfc1', private)
        self.assertEqual(tokens[build.AR_TKN_U32_MODULE_INSTANCE_ID], 0x6101)
        self.assertEqual(private[-(16 + len(config)):][4:8], (0x01001006).to_bytes(4, 'little'))
        self.assertEqual(len(config) % 8, 0)

    def test_only_the_speaker_mfc_changes(self):
        # The stream MFC and the capture graph carry no configuration.
        for name, private in build.topology_widgets(self.blob):
            if name != 'device40.mfc1':
                self.assertIsNone(build.module_config(name, private)[1], name)

    def test_module_instances_are_unique_across_simultaneous_streams(self):
        owners = {}
        for name, private in build.topology_widgets(self.blob):
            tokens, _ = build.module_config(name, private)
            instance = tokens.get(build.AR_TKN_U32_MODULE_INSTANCE_ID)
            if instance is not None:
                self.assertNotIn(instance, owners, (name, owners.get(instance)))
                owners[instance] = name

    def test_ucm_pcm_numbers_match_the_compiled_graph_directions(self):
        pcms = {int(re.search(r'^\s*id\s+"(\d+)"', body, re.M)[1]): name.rsplit(' ', 1)[-1]
                for name, body in build.topology_sections(self.conf, 'PCM')}
        folder = REPO / 'packaging/erhai-audio/tree/usr/share/alsa/ucm2/Qualcomm/sm8750/OnePlus-Pad-2-Pro'
        for path in folder.glob('*.conf'):
            for direction, pcm in re.findall(r'(Playback|Capture)PCM "hw:\$\{CardId\},(\d+)"',
                                              path.read_text()):
                self.assertEqual(pcms.get(int(pcm)), direction, str(path))

    def test_maps_the_kernel_does_not_send(self):
        # Stock ACDB output map (FL FR FC LS RS CS LB RB) differs from the
        # kernel default; the MFC would ignore such a table.
        stock = self.conf.replace('0x00020001, 0x00030006, 0x00050004, 0x00090008',
                                  '0x00020001, 0x00040003, 0x00070005, 0x00090008')
        self.assertIn('not the ones the kernel sends', self.rejects(stock))

    def test_blob_addressed_to_another_module(self):
        other = self.conf.replace('0x00006101, 0x0800101f', '0x00006102, 0x0800101f')
        self.assertIn('addresses instance 0x6102', self.rejects(other))

    def test_blob_size_must_match(self):
        short = self.conf.replace('words "0x00000080, 0x01001006', 'words "0x00000084, 0x01001006')
        self.assertIn('vendor array', self.rejects(short))

    def test_coefficient_above_unity(self):
        loud = self.conf.replace('0x00004000, 0x00000000,', '0x00004001, 0x00000000,', 1)
        self.assertNotEqual(loud, self.conf)
        self.assertIn('above Q14 unity', self.rejects(loud))


if __name__ == '__main__':
    unittest.main()
