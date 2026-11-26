import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from sea.motion import analyze_frames,frequency,waveform,analyze_motion

def pattern(dx=0,dy=0):
    y,x=np.mgrid[:80,:96].astype(float)
    return np.clip(128+40*np.sin((x-dx)*.26)+36*np.cos((y-dy)*.31)+20*np.sin((x-dx+y-dy)*.19),0,255).astype(np.uint8)

def fixture(fps=24):
    return np.stack([pattern(.4*np.sin(2*np.pi*3*i/fps),0) for i in range(fps*4)])

class MotionTests(unittest.TestCase):
    def test_subpixel_frequency(self):
        r=analyze_frames(fixture(),[.1,.1,.9,.9],24)
        self.assertEqual(r['valid_count'],96)
        self.assertAlmostEqual(r['frequency_x']['peak_hz'],3,places=2)
        self.assertAlmostEqual(r['frequency_x']['amplitude_px_estimate'],.4,delta=.08)
        self.assertIsNone(r['frequency_y'])
        json.dumps(r,allow_nan=False)
        self.assertTrue(waveform(r).startswith(b'\x89PNG'))

    def test_reference_subtraction(self):
        frames=fixture()
        r=analyze_frames(frames,[0,0,.45,1],24,reference_box=[.55,0,1,1])
        self.assertIsNone(r['frequency_x'])
        self.assertLess(max(abs(s['dx_px']) for s in r['samples']),.04)

    def test_texture_and_invalid_samples(self):
        with self.assertRaises(ValueError):
            analyze_frames(np.zeros((4,80,96),dtype=np.uint8),[0,0,1,1],24)
        frames=fixture()
        frames[30]=np.random.default_rng(42).integers(0,256,(80,96),dtype=np.uint8)
        r=analyze_frames(frames,[0,0,1,1],24)
        self.assertFalse(r['samples'][30]['valid'])
        self.assertIsNone(r['frequency_x'])

    def test_frequency_limits(self):
        self.assertIsNone(frequency(np.zeros(96),24))
        self.assertIsNone(frequency(np.ones(12),24))
        with self.assertRaises(ValueError):
            analyze_frames(fixture(),[0,0,.8,1],24,reference_box=[.2,0,1,1])

    def test_decoded_video(self):
        # Finite grayscale-to-BGR uncompressed AVI with known synthetic shift.
        from examples.make_motion_demo import write_avi
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'motion.avi'
            write_avi(p,fixture(),24)
            r=analyze_motion(p,[.1,.1,.9,.9],0,4,24)
            self.assertEqual(r['frame_count'],96)
            self.assertAlmostEqual(r['frequency_x']['peak_hz'],3,places=2)
