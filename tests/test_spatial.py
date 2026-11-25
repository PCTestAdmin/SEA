from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os
import numpy as np
from sea.acoustics import png
from sea.spatial import spatial_grid, region_pixels, sense_spatial, crop_region
from sea.engine import resolve_media

class SpatialTests(unittest.TestCase):
    def test_grid(self):
        img=np.zeros((12,12,3),dtype=np.uint8)
        img[:6,:6]=[255,0,0]
        r=spatial_grid(img,2)
        self.assertEqual(r['regions'][0]['mean_rgb_8bit'],[255,0,0])
        self.assertEqual(r['regions'][0]['box'],[0,0,.5,.5])
        self.assertEqual(r['regions'][3]['mean_luma'],0)
        self.assertEqual(r['regions'][0]['edge_fraction'],0)

    def test_crop(self):
        image=np.zeros((20,40,3),dtype=np.uint8)
        crop,box=region_pixels(image,[.25,.25,.75,.75])
        self.assertEqual(crop.shape,(10,20,3))
        self.assertEqual(box,[10,5,30,15])
        for bad in ([0,0,0,1],[0,0,2,1],[0,0,float('nan'),1]):
            with self.assertRaises(ValueError):region_pixels(image,bad)

    def test_local_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'image.png'
            a=np.zeros((32,64,3),dtype=np.uint8)
            a[:,:32]=255
            p.write_bytes(png(a))
            with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':tmp}):
                with self.assertRaises(ValueError):resolve_media(str(p))
                allowed=resolve_media(str(p),allow_image=True)
                r=sense_spatial(allowed,0,2)
                self.assertEqual(r['sample_size_px'],[64,32])
                self.assertGreater(r['regions'][0]['mean_luma'],.95)
                self.assertLess(r['regions'][1]['mean_luma'],.05)
                self.assertTrue(crop_region(allowed,0,[0,0,.5,.5]).startswith(b'\x89PNG'))
                with self.assertRaises(ValueError):sense_spatial(allowed,1,2)
