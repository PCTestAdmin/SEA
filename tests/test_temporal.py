import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sea import temporal

class TemporalTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name).resolve()
        self.p=root/'demo.avi'
        self.store=root/'index';self.store.mkdir()
        env=patch.dict(os.environ,{'SEA_INDEX_DIR':str(self.store)})
        env.start();self.addCleanup(env.stop)
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(self.p)],check=True,timeout=30)

    def test_parser_vfr_and_missing(self):
        base,first,rows=temporal.parse_probe(b'frame|key_frame=1|best_effort_timestamp=100\nframe|key_frame=0|best_effort_timestamp=103\nframe|key_frame=0|best_effort_timestamp=N/A\nframe|key_frame=0|best_effort_timestamp=103\nstream|time_base=1/100\n')
        self.assertEqual((base,first),('1/100',100))
        self.assertEqual([r[2] for r in rows],[0,.03,None,.03])
        with patch('sea.temporal.MAX_FRAMES',1):
            with self.assertRaises(ValueError):
                temporal.parse_probe(b'frame|key_frame=1|best_effort_timestamp=0\nframe|key_frame=0|best_effort_timestamp=1\nstream|time_base=1/4\n')

    def test_real_index_and_navigation(self):
        r=temporal.build(self.p,True)
        self.assertEqual(r['frame_count'],24)
        self.assertEqual(r['missing_timestamp_count'],0)
        self.assertFalse(r['reused'])
        with patch('sea.temporal.run',side_effect=AssertionError('must reuse')):
            self.assertTrue(temporal.build(self.p,True)['reused'])
        page=temporal.page(self.p,20,3)
        self.assertEqual([f['frame_index'] for f in page['frames']],[20,21,22])
        self.assertEqual(page['next_cursor'],23)
        self.assertIsNone(temporal.page(self.p,23,3)['next_cursor'])
        hit=temporal.locate(self.p,relative_s=2.01)
        self.assertEqual(hit['frame']['frame_index'],8)
        self.assertAlmostEqual(hit['frame']['relative_s'],2)
        self.assertEqual(temporal.locate(self.p,frame_index=16)['frame']['relative_s'],4)
        with self.assertRaises(ValueError):temporal.locate(self.p)

    def test_observations_and_deletion(self):
        rev=temporal.build(self.p,True)['source_revision']
        with self.assertRaises(ValueError):temporal.add_note(self.p,8,9,'White frame')
        r=temporal.add_note(self.p,8,15,'White frame',True)
        temporal.add_note(self.p,16,23,'Black frame',True)
        self.assertEqual(temporal.search_notes(self.p,'WHITE')['notes'][0]['id'],r['note_id'])
        self.assertEqual(temporal.search_notes(self.p,'%',limit=1)['notes'],[])
        page=temporal.search_notes(self.p,limit=1)
        self.assertEqual(len(temporal.search_notes(self.p,after_id=page['next_after_id'])['notes']),1)
        with self.assertRaises(ValueError):temporal.delete(rev)
        temporal.delete(rev,True)
        with self.assertRaises(ValueError):temporal.page(self.p)
        self.assertTrue(self.p.exists())

    def test_stale_and_opt_in(self):
        with self.assertRaises(ValueError):temporal.build(self.p)
        self.assertEqual(list(self.store.iterdir()),[])
        r=temporal.build(self.p,True)
        with self.p.open('ab') as f:f.write(b'x')
        with self.assertRaises(ValueError):temporal.page(self.p)
        temporal.delete(r['source_revision'],True)
        with patch.dict(os.environ,{'SEA_INDEX_DIR':''}):
            with self.assertRaises(ValueError):temporal.build(self.p,True)
