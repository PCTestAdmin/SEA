import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sea.detector import normalize_predictions, annotate, checkpoint, status, detect

class DetectorTests(unittest.TestCase):
    def test_normalization_and_limit(self):
        p={'boxes':[[10,20,50,60],[-5,0,200,100],[0,0,0,0],[1,1,2,2]],
           'labels':[1,2,1,1],'scores':[.7,.9,.95,.1]}
        r=normalize_predictions(p,['__background__','cat','dog'],100,100,.5,1)
        self.assertEqual(r['matching_count'],2)
        self.assertTrue(r['truncated'])
        self.assertEqual(r['detections'][0]['box'],[0,0,1,1])
        self.assertEqual(r['label_counts'],{'dog':1})
        self.assertEqual(r['detections'][0]['id'],'D001')
    def test_invalid_options(self):
        with self.assertRaises(ValueError):
            normalize_predictions({'boxes':[],'labels':[],'scores':[]},[],100,100,float('nan'),1)
    def test_disabled(self):
        with patch.dict(os.environ,{'SEA_VISION_WEIGHTS':''}):
            self.assertFalse(status()['ready_to_attempt'])
            with self.assertRaises(ValueError):checkpoint()
    def test_wrong_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.pth';p.write_bytes(b'not the official weights')
            with patch.dict(os.environ,{'SEA_VISION_WEIGHTS':str(p)}):
                self.assertFalse(status()['weights_prefix_verified'])
                with self.assertRaises(ValueError):checkpoint()
    def test_annotation(self):
        data=annotate(np.zeros((100,100,3),dtype=np.uint8),
                      [{'id':'D001','label':'cat','score':.9,'box':[.1,.2,.5,.6]}])
        self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
    @unittest.skipUnless(os.environ.get('SEA_VISION_TEST_IMAGE'),'Optional pretrained inference fixture not configured')
    def test_pretrained(self):
        p=Path(os.environ['SEA_VISION_TEST_IMAGE'])
        report,rgb=detect(p,0,.35,30)
        self.assertTrue(any(r['label']=='cat' for r in report['detections']),report)
        self.assertEqual(len(report['weights_sha256']),64)
        self.assertTrue(annotate(rgb,report['detections']).startswith(b'\x89PNG'))
