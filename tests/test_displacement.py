import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from sea.displacement import grid,normalize,status,measure,draw_vectors,native

class DisplacementTests(unittest.TestCase):
    def test_grid(self):
        x,y=grid(512,512,12)
        self.assertEqual(x.shape,y.shape)
        self.assertGreaterEqual(x.shape[0],8)
        self.assertEqual(int(x[0,1]-x[0,0]),32)
        for args in ((100,100,12),(512,512,25),(512,512,5)):
            with self.assertRaises(ValueError):grid(*args)

    def test_native_small_grid_configuration(self):
        class FakeProvider:
            def runAutorift(self):
                # Check adapter configuration, not numerical provider correctness.
                if self.sparseSearchSampleRate != 1:
                    raise AssertionError('Small grid would be undersampled.')
                self.Dx=np.zeros(self.xGrid.shape,dtype=np.float32)
                self.Dy=np.zeros_like(self.Dx)
                self.ChipSizeX=np.full_like(self.Dx,32)
                self.InterpMask=np.zeros(self.xGrid.shape,dtype=bool)
        a=np.zeros((512,512),dtype=np.uint8)
        with patch('sea.displacement.status',return_value={'ready_to_attempt':True}), \
             patch.dict(sys.modules,{'autoRIFT':SimpleNamespace(autoRIFT=FakeProvider)}):
            report=native(a,a,12)
        self.assertEqual(report['grid_shape'],[14,14])
        self.assertEqual(report['matched_count'],196)

    def test_masks(self):
        x=np.array([[40,72,104,136]])
        y=np.full_like(x,40)
        dx=np.array([[2.,3.,np.nan,20.]])
        dy=np.array([[1.,1.,0.,0.]])
        r=normalize(x,y,dx,dy,np.array([[32,32,0,32]]),np.array([[False,True,False,False]]),12)
        self.assertEqual([p['status'] for p in r['points']],['matched','interpolated','missing','missing'])
        self.assertEqual(r['median_matched_dx_px'],2.)
        self.assertIsNone(r['points'][2]['dx_autorift_px'])
        self.assertTrue(draw_vectors(r,np.zeros((160,160,3),dtype=np.uint8)).startswith(b'\x89PNG'))

    def test_unavailable(self):
        with patch('sea.displacement.status',return_value={'ready_to_attempt':False}):
            with self.assertRaises(ValueError):measure(Path('a.png'),Path('b.png'))

    def test_timeout(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.png'
            Image.fromarray(np.random.default_rng(4).integers(0,256,(512,512),dtype=np.uint8)).save(p)
            with patch('sea.displacement.status',return_value={'ready_to_attempt':True}), \
                 patch('sea.displacement.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',90)):
                with self.assertRaisesRegex(RuntimeError,'timed out'):measure(p,p)

    @unittest.skipUnless(os.environ.get('SEA_TEST_AUTORIFT')=='1','Optional native autoRIFT test disabled')
    def test_real_provider(self):
        self.assertTrue(status()['ready_to_attempt'],status())
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.png';b=Path(tmp)/'b.png'
            img=np.random.default_rng(42).integers(16,240,(512,512),dtype=np.uint8)
            shifted=np.roll(img,(3,5),axis=(0,1))
            Image.fromarray(img).save(a);Image.fromarray(shifted).save(b)
            r,rgb=measure(a,b,12)
            self.assertEqual(r['coarse_search_stride'],1)
            self.assertGreater(r['matched_count'],10,{k:v for k,v in r.items() if k!='points'})
            # Check displacement magnitude independently of native source-order sign convention.
            self.assertAlmostEqual(abs(r['median_matched_dx_px']),5,delta=.5)
            self.assertAlmostEqual(abs(r['median_matched_dy_px']),3,delta=.5)
            self.assertTrue(draw_vectors(r,rgb).startswith(b'\x89PNG'))
