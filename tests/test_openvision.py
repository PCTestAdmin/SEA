import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sea.openvision import validate_queries,normalize,model_dir,status,search,overlay

class OpenVisionTests(unittest.TestCase):
    def test_queries(self):
        self.assertEqual(validate_queries([' red cup ','a laptop'],.2,20),['red cup','a laptop'])
        for q in ([],['a','A'],['a'*81],['x\nz'],['a']*9):
            with self.assertRaises(ValueError):validate_queries(q,.2,20)
        with self.assertRaises(ValueError):validate_queries(['cat'],float('nan'),20)

    def test_normalize_and_nms(self):
        r=normalize([[0,0,50,50],[1,1,49,49],[0,0,50,50],[90,90,120,120]],
                    [.9,.8,.7,.6],['cat','cat','blanket','cat'],['cat','blanket'],100,100,.2,2)
        self.assertEqual(r['matching_count'],3)
        self.assertEqual(r['returned_count'],2)
        self.assertTrue(r['truncated'])
        self.assertEqual(r['detections'][1]['label'],'blanket')
        self.assertEqual(r['detections'][0]['box'],[0,0,.5,.5])

    def test_disabled(self):
        with patch.dict(os.environ,{'SEA_OPEN_VISION_DIR':''}):
            self.assertFalse(status()['ready_to_attempt'])
            with self.assertRaises(ValueError):model_dir()

    def test_scipy_readiness(self):
        with patch('sea.openvision.importlib.util.find_spec', side_effect=lambda name: None if name=='scipy' else object()):
            r=status()
            self.assertFalse(r['dependencies_discoverable']['scipy'])
            self.assertFalse(r['ready_to_attempt'])

    def test_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'SEA_OPEN_VISION_DIR':tmp}):
            self.assertFalse(status()['model_files_present'])
            with self.assertRaises(ValueError):model_dir()

    @unittest.skipUnless(os.environ.get('SEA_OPEN_VISION_TEST_IMAGE'),'Optional OWLv2 fixture not configured')
    def test_real_model(self):
        r,rgb=search(Path(os.environ['SEA_OPEN_VISION_TEST_IMAGE']),['a photo of a cat','a photo of a dog'],0,.2,20)
        self.assertTrue(any(x['label']=='a photo of a cat' for x in r['detections']),r)
        self.assertEqual(len(r['weights_sha256']),64)
        self.assertTrue(overlay(r,rgb).startswith(b'\x89PNG'))
