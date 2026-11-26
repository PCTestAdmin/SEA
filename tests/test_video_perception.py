import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave
import numpy as np
from sea.video_perception import native_page,native_sheet,crop_frame,frame_pair,scan_page,audio_clip,visual_changes

class PerceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.p=Path(cls.tmp.name)/'demo.avi'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(cls.p)],check=True,timeout=30)

    def test_native_indices_and_eof(self):
        report,frames=native_page(self.p,7,3)
        self.assertEqual(report['frame_indices'],[7,8,9])
        self.assertEqual(report['next_frame_index'],10)
        self.assertLess(frames[0].mean(),10)
        self.assertGreater(frames[1].mean(),240)
        self.assertTrue(native_sheet(report,frames).startswith(b'\x89PNG'))
        tail,frames=native_page(self.p,22,4,expected_revision=report['source_revision'])
        self.assertEqual(tail['frame_indices'],[22,23])
        self.assertTrue(tail['end_of_stream'])
        self.assertIsNone(tail['next_frame_index'])
        with self.assertRaises(ValueError):native_page(self.p,0,1,expected_revision='wrong')

    def test_crop_and_diff(self):
        r,image=crop_frame(self.p,8,[0,0,.5,.5])
        self.assertEqual(r['crop_bounds_sample_px'],[0,0,80,45])
        self.assertTrue(image.startswith(b'\x89PNG'))
        r,image=frame_pair(self.p,7,8)
        self.assertAlmostEqual(r['changed_pixel_fraction'],1)
        self.assertTrue(image.startswith(b'\x89PNG'))

    def test_contiguous_scan(self):
        a=scan_page(self.p,4,0,1,4)
        b=scan_page(self.p,4,a['next_cursor'],1,4,a['source_revision'])
        self.assertIsNone(b['next_cursor'])
        self.assertEqual(a['results'][0]['visual_status'],'sampled')
        self.assertEqual(b['results'][0]['preceding_boundary_status'],'observed')
        self.assertTrue(b['results'][0]['comparisons'][0]['boundary_comparison'])
        self.assertIn(2.,a['results'][0]['scene_change_candidates'])
        self.assertIn(4.,b['results'][0]['scene_change_candidates'])
        self.assertEqual(a['results'][0]['audio_status'],'measured')
        json.dumps(b,allow_nan=False)

    def test_audio_content(self):
        r,data=audio_clip(self.p,2,1)
        with wave.open(io.BytesIO(data),'rb') as f:
            self.assertEqual(f.getframerate(),16000)
            self.assertEqual(f.getnchannels(),1)
            self.assertEqual(f.getnframes(),16000)
            self.assertGreater(np.abs(np.frombuffer(f.readframes(16000),dtype='<i2')).max(),1000)
        self.assertEqual(r['decoded_duration_s'],1)

    def test_change_heuristic(self):
        a=np.zeros((2,8,8,3),dtype=np.uint8);a[1]=255
        self.assertTrue(visual_changes(a,0,4)[0]['scene_change_candidate'])
        with self.assertRaises(ValueError):native_page(self.p,100000,1)
        with self.assertRaises(ValueError):audio_clip(self.p,0,13)
