import math
import os
import subprocess
import sys
import tempfile
import unittest
import wave
import struct
from pathlib import Path
from unittest.mock import patch
from sea.engine import resolve_media, analyze, frame, window

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        env=patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root)})
        env.start(); self.addCleanup(env.stop)
        self.wav=self.root/'tone.wav'
        with wave.open(str(self.wav),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*440*i/16000)) if i>=16000 else 0) for i in range(32000)))
    def test_audio(self):
        report=analyze(resolve_media(str(self.wav)),0,2)
        self.assertIsNone(report['video'])
        self.assertEqual(report['observations']['low_level_bins'],2)
        self.assertEqual(report['timeline'][2]['dominant_frequency_hz'],440)
        self.assertAlmostEqual(report['audio']['peak_dbfs'],-8.73,places=1)
    def test_scope(self):
        with self.assertRaises(ValueError): resolve_media('tone.wav')
        with tempfile.TemporaryDirectory() as other:
            p=Path(other)/'outside.wav';p.write_bytes(b'x')
            with self.assertRaises(ValueError): resolve_media(str(p))
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':''}):
            with self.assertRaises(ValueError): resolve_media(str(self.wav))
    def test_windows(self):
        for s,d in [(0,61),(-1,1),(0,float('nan'))]:
            with self.assertRaises(ValueError):window(s,d)
    def test_audiovisual_demo(self):
        p=self.root/'demo.mp4'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,capture_output=True)
        report=analyze(p,0,6)
        self.assertGreaterEqual(report['observations']['visual_change_bins'],2)
        self.assertGreaterEqual(report['observations']['low_level_bins'],6)
        self.assertTrue(any(r['visual_change_flag'] and r['dominant_frequency_hz']==440 for r in report['timeline']))
        self.assertTrue(frame(p,2.5).startswith(b'\x89PNG'))
