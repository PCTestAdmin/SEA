import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from sea import temporal,visual_search

class VisualSearchTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.p=self.root/'demo.avi'
        store=self.root/'index';store.mkdir()
        env=patch.dict(os.environ,{'SEA_INDEX_DIR':str(store)})
        env.start();self.addCleanup(env.stop)
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(self.p)],check=True,timeout=30)

    def test_signatures_distinguish_flat_colors(self):
        frames=np.zeros((2,32,32,3),dtype=np.uint8)
        frames[1]=255
        c,h=visual_search.signatures(frames)
        self.assertEqual(c.shape,(2,48))
        self.assertEqual(h.shape,(2,7))
        self.assertTrue((c[0]==0).all())
        self.assertTrue((c[1]==255).all())

    def test_native_index_reuse_and_search(self):
        temporal.build(self.p,True)
        with self.assertRaises(ValueError):visual_search.build(self.p,2)
        r=visual_search.build(self.p,2,True)
        self.assertEqual(r['indexed_sample_count'],12)
        with patch('sea.visual_search.run',side_effect=AssertionError('should reuse')):
            self.assertTrue(visual_search.build(self.p,2,True)['reused'])
        r=visual_search.search(self.p,reference_frame=0,threshold=.99)
        self.assertEqual([m['frame_index'] for m in r['matches']],[2,4,6,16,18,20,22])
        self.assertEqual(r['matches'][3]['relative_s'],4)
        ref=self.root/'white.png'
        Image.new('RGB',(160,90),'white').save(ref)
        r=visual_search.search(self.p,reference_image=ref,threshold=.99)
        self.assertEqual([m['frame_index'] for m in r['matches']],[8,10,12,14])
        with self.assertRaises(ValueError):visual_search.search(self.p,reference_frame=1)
        with self.assertRaises(ValueError):visual_search.build(self.p,1,True)
        temporal.add_note(self.p,8,15,'white',True)
        visual_search.delete(self.p,True)
        self.assertEqual(temporal.page(self.p)['frame_count'],24)
        self.assertEqual(len(temporal.search_notes(self.p)['notes']),1)
        with self.assertRaises(ValueError):visual_search.search(self.p,reference_frame=0)

    def test_template_page(self):
        ref=self.root/'pattern.png'
        rng=np.random.default_rng(7)
        pattern=rng.integers(0,256,(12,16,3),dtype=np.uint8)
        Image.fromarray(pattern).save(ref)
        frame=np.zeros((252,448,3),dtype=np.uint8)
        frame[30:42,50:66]=pattern
        with patch('sea.visual_search.sample_frames',return_value=np.stack([frame]*4)):
            r=visual_search.template_page(self.p,ref,0,1,.99)
        self.assertEqual(r['status'],'sampled')
        self.assertEqual(r['next_cursor'],1)
        self.assertEqual(len(r['matches']),4)
        self.assertAlmostEqual(r['matches'][0]['matches'][0]['box'][0],50/448)
        with self.assertRaises(ValueError):visual_search.template_page(self.p,ref,0,3)

    def test_source_change_and_cascade(self):
        rev=temporal.build(self.p,True)['source_revision']
        with patch('sea.visual_search.run',return_value=b''):
            with self.assertRaisesRegex(RuntimeError,'sample count'):visual_search.build(self.p,2,True)
        visual_search.build(self.p,2,True)
        temporal.delete(rev,True)
        with temporal.database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM visual_frames').fetchone()[0],0)
        temporal.build(self.p,True)
        visual_search.build(self.p,2,True)
        with self.p.open('ab') as f:f.write(b'x')
        with self.assertRaises(ValueError):visual_search.search(self.p,reference_frame=0)
