import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sea.survey import plan_windows,candidate_events,investigate_recording

class SurveyTests(unittest.TestCase):
    def test_plan(self):
        self.assertEqual(plan_windows(0,6,5),[(0,6)])
        self.assertEqual(plan_windows(0,12,5),[(0,6),(6,6)])
        w=plan_windows(0,300,5)
        self.assertEqual(len(w),5)
        self.assertEqual(w[0],(27,6))
        self.assertEqual(w[-1],(267,6))
        with self.assertRaises(ValueError):plan_windows(0,1801,5)
        with self.assertRaises(ValueError):plan_windows(0,30,6)

    def test_candidates(self):
        rows=[{'start_s':0,'end_s':.5,'audio_observed':True,'audio_rms_dbfs':None},
              {'start_s':.5,'end_s':1,'audio_observed':True,'audio_rms_dbfs':-12,
               'visual_change_flag':True,'max_frame_change':.9}]
        c=candidate_events({'timeline':rows},'W01')
        self.assertEqual(len(c),1)
        self.assertEqual(len(c[0]['evidence']),2)

    def test_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'demo.mp4'
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,capture_output=True)
            r=investigate_recording(p,0,6,5,2)
            self.assertEqual(r['scan_windows'][0]['status'],'scanned')
            self.assertGreaterEqual(r['candidate_count'],2)
            self.assertTrue(any(e['status']=='refined' for e in r['refinements']))
            self.assertEqual(r['unscanned_requested_ranges_s'],[])
            json.dumps(r,allow_nan=False)

    def test_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.wav';p.write_bytes(b'x')
            with patch('sea.survey.probe',return_value={'audio':True,'video':False,'duration_s':60}), \
                 patch('sea.survey.analyze',return_value={'timeline':[{'start_s':12,'end_s':12.5,'audio_observed':True}]}):
                r=investigate_recording(p,0,60,2,0)
                self.assertEqual(len(r['scan_windows']),2)
                self.assertEqual(len(r['unscanned_requested_ranges_s']),3)
                self.assertEqual(r['refinements'],[])

    def test_failed_window_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.wav';p.write_bytes(b'x')
            with patch('sea.survey.probe',return_value={'audio':True,'video':False,'duration_s':6}), \
                 patch('sea.survey.analyze',side_effect=RuntimeError('decode failed')):
                r=investigate_recording(p,0,6)
                self.assertEqual(r['scan_windows'][0]['status'],'failed')
                self.assertEqual(r['unscanned_requested_ranges_s'],[[0,6]])
