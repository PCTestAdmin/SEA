import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave
import numpy as np
from sea.engine import WIDTH,HEIGHT
from sea.vision import analyze_frames, analyze_video, correlate, investigate

class VisionTests(unittest.TestCase):
    def test_global_and_stable(self):
        x=np.zeros((12,HEIGHT,WIDTH),dtype=np.uint8)
        x[6:]=255
        r=analyze_frames(x,0,3)
        points=[e for e in r['events'] if 'time_s' in e]
        self.assertEqual(len(points),1)
        self.assertEqual(points[0]['kind'],'large_global_change')
        self.assertEqual(points[0]['time_s'],1.5)
        self.assertEqual(points[0]['change_region'],[0,0,1,1])
        self.assertEqual(sum(e['kind']=='low_change_interval' for e in r['events']),2)
        json.dumps(r,allow_nan=False)

    def test_local_activity(self):
        x=np.zeros((2,HEIGHT,WIDTH),dtype=np.uint8)
        x[1,10:40,20:60]=255
        r=analyze_frames(x,4,1)
        e=r['events'][0]
        self.assertEqual(e['kind'],'pixel_activity')
        self.assertEqual(e['time_s'],4.25)
        self.assertEqual(e['change_region'],[.125,.1111,.375,.4444])

    def test_static_not_freeze(self):
        r=analyze_frames(np.zeros((8,HEIGHT,WIDTH),dtype=np.uint8),0,2)
        self.assertEqual([e['kind'] for e in r['events']],['low_change_interval'])

    def test_correlation(self):
        a=[{'id':'A1','time_s':2},{'id':'A2','time_s':9}]
        v=[{'id':'V1','time_s':2.25},{'id':'V2','time_s':4}]
        r=correlate(a,v,.5)
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['video_minus_audio_s'],.25)
        self.assertEqual(r[0]['relationship'],'temporal_proximity_only')
        with self.assertRaises(ValueError): correlate(a,v,3)

    def test_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'demo.mp4'
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,capture_output=True)
            r=investigate(p,0,6)
            self.assertEqual(r['available_modalities'],{'audio':True,'video':True})
            self.assertGreaterEqual(len(r['correlations']),2)
            self.assertTrue(any(abs(e['video_time_s']-2)<.51 for e in r['correlations']))
            self.assertTrue(any(abs(e['video_time_s']-4)<.51 for e in r['correlations']))
            self.assertTrue(r['recommended_followups'])
            json.dumps(r,allow_nan=False)
            with self.assertRaises(ValueError): analyze_video(p,0,121)
            with self.assertRaises(ValueError): investigate(p,0,31)

    def test_audio_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'silence.wav'
            with wave.open(str(p),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'))
                f.writeframes(b'\0'*32000)
            r=investigate(p,0,1)
            self.assertEqual(r['available_modalities'],{'audio':True,'video':False})
            self.assertEqual(r['correlations'],[])
            self.assertEqual(r['recommended_followups'],[])
