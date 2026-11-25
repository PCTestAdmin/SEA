import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave
import numpy as np
from sea.acoustics import analyze_audio, analyze_samples, compare_audio, spectrogram, RATE

class AcousticTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
    def tone(self, name, hz=440, amp=.4, duration=2, gated=False):
        t = np.arange(int(duration*RATE))/RATE
        x = amp*np.sin(2*np.pi*hz*t)
        if gated:
            x[(t<.5)|(t>=1.5)] = 0
        p = self.root/name
        with wave.open(str(p),'wb') as f:
            f.setparams((1,2,RATE,0,'NONE','not compressed'))
            f.writeframes((x*32767).astype('<i2').tobytes())
        return p
    def test_tone_and_events(self):
        report=analyze_audio(self.tone('a.wav',gated=True),0,2)
        self.assertAlmostEqual(report['frequency_peaks'][0]['frequency_hz'],440,delta=8)
        active=[r for r in report['events'] if r['kind']=='above_threshold_interval']
        self.assertEqual(active,[{'kind':'above_threshold_interval','start_s':.5,'end_s':1.5}])
        self.assertTrue(any(r['kind']=='level_rise' and r['time_s']==.5 for r in report['events']))
        self.assertTrue(any(r['kind']=='level_drop' and r['time_s']==1.5 for r in report['events']))
        json.dumps(report,allow_nan=False)
    def test_silence(self):
        r=analyze_samples(np.zeros(RATE),0)
        self.assertIsNone(r['rms_dbfs'])
        self.assertIsNone(r['spectral_centroid_hz'])
        self.assertEqual(r['events'],[])
        self.assertEqual(r['frequency_peaks'],[])
    def test_compare(self):
        a=self.tone('a.wav',amp=.4)
        b=self.tone('b.wav',amp=.2)
        r=compare_audio(a,b,0,0,2)
        self.assertAlmostEqual(r['delta_b_minus_a']['rms_db'],-6.02,places=1)
    def test_unequal_duration(self):
        a=self.tone('a.wav')
        b=self.tone('b.wav',duration=1)
        with self.assertRaises(ValueError):
            compare_audio(a,b,0,0,2)
    def test_spectrogram(self):
        image=spectrogram(self.tone('a.wav'),0,2,2000)
        self.assertEqual(image[:8],b'\x89PNG\r\n\x1a\n')
        width,height=struct.unpack('>II',image[16:24])
        self.assertGreater(width,100)
        self.assertEqual(height,129)
        self.assertLess(len(image),2*1024*1024)
    def test_limits(self):
        p=self.tone('a.wav')
        with self.assertRaises(ValueError):analyze_audio(p,0,31)
        with self.assertRaises(ValueError):spectrogram(p,0,1,9000)
