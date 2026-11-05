# SPDX-License-Identifier: GPL-2.0-only
"""Execute UCM in ACP order without a sound card.

Replace only cset I/O with an execution trace and hardware PCMs with ALSA
null PCMs. The real alsa-lib parser, conditions, variable expansion and UCM
state machine run unchanged. This checks sequence ownership, not hardware.
"""
import ctypes as C
import ctypes.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
UCM = REPO / 'packaging/erhai-audio/tree/usr/share/alsa/ucm2'
MIC_ROUTE = 'MultiMedia3 Mixer TX_CODEC_DMA_TX_3'
SPEAKER_ROUTE = 'Secondary TDM0 Audio Mixer MultiMedia1'


class AcpProbeOrder(unittest.TestCase):
    def test_verb_routes_before_pcm_probe(self):
        lib = C.CDLL(ctypes.util.find_library('asound'))
        lib.snd_use_case_mgr_open.argtypes = [C.POINTER(C.c_void_p), C.c_char_p]
        lib.snd_use_case_set.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p]
        lib.snd_use_case_get_list.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(C.POINTER(C.c_char_p))]
        lib.snd_use_case_free_list.argtypes = [C.POINTER(C.c_char_p), C.c_int]
        lib.snd_use_case_mgr_close.argtypes = [C.c_void_p]
        lib.snd_pcm_open.argtypes = [C.POINTER(C.c_void_p), C.c_char_p, C.c_int, C.c_int]
        lib.snd_pcm_close.argtypes = [C.c_void_p]
        for disabled in (False, True):
            with self.subTest(disabled=disabled), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                tree = root / 'ucm2'
                shutil.copytree('/usr/share/alsa/ucm2', tree, symlinks=True)
                board = tree / 'Qualcomm/sm8750/OnePlus-Pad-2-Pro'
                shutil.copytree(UCM / 'Qualcomm/sm8750/OnePlus-Pad-2-Pro', board, dirs_exist_ok=True)
                (tree / 'conf.virt.d').mkdir(exist_ok=True)
                shutil.copy(UCM / 'conf.d/sm8750/OnePlus-Pad-2-Pro.conf', tree / 'conf.virt.d')
                flag = root / 'speaker-disabled'
                if disabled:
                    flag.touch()
                trace = root / 'controls.jsonl'
                helper = root / 'record-control'
                helper.write_text(f'#!{sys.executable}\nimport json,sys\n'
                                  f'with open({str(trace)!r}, "a") as f: '
                                  'f.write(json.dumps(sys.argv[1:]) + "\\n")\n')
                helper.chmod(0o755)
                controls = []

                def instrument(match):
                    controls.append(match[1])
                    return f'exec "{helper} {len(controls)-1} {match[2]}"'

                for conf in board.glob('*.conf'):
                    text = conf.read_text().replace('${CardId}', '0')
                    text = text.replace('/var/lib/erhai/audio/speaker-disabled', str(flag))
                    text = re.sub(r'cset "name=\'([^\']+)\' ([^"]+)"', instrument, text)
                    text = text.replace('"hw:0,0"', '"null"').replace('"hw:0,2"', '"null"')
                    conf.write_text(text)
                alsa = root / 'alsa.conf'
                alsa.write_text('pcm.null { type null }\n')

                def writes():
                    return [(controls[int(i)], value) for i, value in
                            map(json.loads, trace.read_text().splitlines())]

                with patch.dict(os.environ, ALSA_CONFIG_UCM2=str(tree), ALSA_CONFIG_PATH=str(alsa)):
                    manager = C.c_void_p()
                    self.assertEqual(lib.snd_use_case_mgr_open(C.byref(manager), b'OnePlus-Pad-2-Pro'), 0)
                    try:
                        devices = C.POINTER(C.c_char_p)()
                        count = lib.snd_use_case_get_list(manager, b'_devices/HiFi', C.byref(devices))
                        self.assertGreater(count, 0)
                        names = [devices[i].decode() for i in range(0, count, 2)]
                        lib.snd_use_case_free_list(devices, count)
                        self.assertEqual(set(names), {'Mic'} if disabled else {'Mic', 'Speaker'})
                        self.assertEqual(lib.snd_use_case_set(manager, b'_verb', b'HiFi'), 0)
                        self.assertEqual(writes(), [(MIC_ROUTE, '1'), (SPEAKER_ROUTE, '0,0' if disabled else '1,1')])
                        # Like ACP, open playback then capture with only the verb set.
                        for stream in ([1] if disabled else [0, 1]):
                            pcm = C.c_void_p()
                            self.assertEqual(lib.snd_pcm_open(C.byref(pcm), b'null', stream, 0), 0)
                            lib.snd_pcm_close(pcm)
                        print(f'opt_out={disabled}: only _verb; devices={names}; before PCM opens={writes()}', flush=True)
                        if not disabled:
                            self.assertEqual(lib.snd_use_case_set(manager, b'_enadev', b'Speaker'), 0)
                            self.assertEqual(len(writes()), 9)  # two routes, six amps, DSP gain
                            self.assertTrue(all('Volume' in name or 'Playback Volu' in name for name, _ in writes()[2:]))
                        self.assertEqual(lib.snd_use_case_set(manager, b'_verb', b'Inactive'), 0)
                        self.assertEqual(writes()[-2:], [(SPEAKER_ROUTE, '0,0'), (MIC_ROUTE, '0')])
                    finally:
                        lib.snd_use_case_mgr_close(manager)


if __name__ == '__main__':
    unittest.main()
