import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sea.video_understanding import plan_page, timeline, analyze_page, contact_sheet, status

class VideoUnderstandingTests(unittest.TestCase):
    def test_full_plan_no_gaps(self):
        rows=[];cursor=0
        while cursor is not None:
            p=plan_page(25.25,8,cursor,2)
            rows.extend(p['segments']);cursor=p['next_cursor']
        self.assertEqual([(r['start_s'],r['end_s']) for r in rows],[(0,8),(8,16),(16,24),(24,25.25)])
        self.assertEqual(len({r['id'] for r in rows}),4)
        with self.assertRaises(ValueError):plan_page(float('nan'))
        with self.assertRaises(ValueError):plan_page(10,8,3)

    def test_optional_status(self):
        with patch.dict(os.environ,{'SEA_VIDEO_MODEL_DIR':'','SEA_SPEECH_MODEL_DIR':''}):
            self.assertFalse(status()['video']['configured'])
            self.assertFalse(status()['speech']['ready_to_attempt'])

    def test_real_decoding_and_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'demo.avi'
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,timeout=30)
            plan=timeline(p,4,0,1)
            self.assertEqual(plan['total_segments'],2)
            self.assertEqual(plan['next_cursor'],1)
            self.assertTrue(contact_sheet(p,1,4,2,plan['source_revision']).startswith(b'\x89PNG'))
            with self.assertRaises(ValueError):contact_sheet(p,0,4,2,'wrong-revision')

    def test_paged_model_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.mp4';p.write_bytes(b'x')
            frames=np.zeros((8,20,20,3),dtype=np.uint8)
            calls=[]
            def predict(f,fps,a,b):
                calls.append((a,b))
                return {'description':'mock evidence'}
            with patch('sea.video_understanding.probe',return_value={'video':True,'audio':True,'duration_s':9}), \
                 patch('sea.video_understanding.sample_frames',side_effect=[frames,RuntimeError('bad frame'),frames]), \
                 patch('sea.video_understanding.visual_model',return_value=predict) as load, \
                 patch('sea.video_understanding.speech_model',return_value=lambda a,t:{'segments':[{'start_s':t,'end_s':t+.1,'text':'test'}]}), \
                 patch('sea.video_understanding.audio_samples',return_value=np.zeros(1600,dtype=np.float32)):
                r=analyze_page(p,4,0,3)
                self.assertIsNone(r['next_cursor'])
                self.assertEqual([x['visual_status'] for x in r['results']],['described','failed','described'])
                self.assertEqual([x['speech_status'] for x in r['results']],['transcribed']*3)
                self.assertEqual(calls,[(0,4),(8,9)])
                load.assert_called_once()
                json.dumps(r,allow_nan=False)

    @unittest.skipUnless(os.environ.get('SEA_VIDEO_REAL_TEST')=='1','Optional full video model not configured')
    def test_real_video_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'demo.avi'
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,timeout=30)
            r=analyze_page(p,4,0,2,2,False)
            self.assertIsNone(r['next_cursor'])
            self.assertTrue(all(x['visual_status']=='described' and x['visual']['description'] for x in r['results']),r)
