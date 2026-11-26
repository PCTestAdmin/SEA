import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sea.tracking import associate,sample_times,track,contact_sheet

def detection(i,box,label='cat'):
    return {'id':f'D{i:03d}','label':label,'box':box,'score':.9}

def sample(i,rows,status='observed'):
    return {'id':f'S{i:02d}','requested_time_s':float(i),'status':status,'detections':rows}

class TrackingTests(unittest.TestCase):
    def test_stable_track_and_motion(self):
        r=associate([sample(1,[detection(1,[.1,.1,.4,.4])]),
                     sample(2,[detection(1,[.2,.1,.5,.4])])])
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['observation_count'],2)
        self.assertEqual(r[0]['net_center_shift'],[.1,0])
        self.assertEqual(r[0]['sampled_center_path_length'],.1)

    def test_missing_and_label_change_break_tracks(self):
        a=detection(1,[.1,.1,.4,.4])
        b=detection(1,[.1,.1,.4,.4],'dog')
        r=associate([sample(1,[a]),sample(2,[], 'decode_failed'),sample(3,[a]),sample(4,[b])])
        self.assertEqual([t['observation_count'] for t in r],[1,1,1])

    def test_ambiguity_breaks_tracks(self):
        a=detection(1,[.1,.1,.6,.6])
        b=detection(2,[.2,.1,.7,.6])
        r=associate([sample(1,[a,b]),sample(2,[a])])
        self.assertEqual(len(r),3)
        self.assertEqual(r[-1]['observations'][0]['association'],'ambiguous_overlap')

    def test_sample_limits(self):
        self.assertEqual(sample_times(0,6,3),[0,2,4])
        for s,d,n in [(0,61,4),(0,10,13),(86400,1,2),(0,float('nan'),2)]:
            with self.assertRaises(ValueError):sample_times(s,d,n)
        with self.assertRaises(ValueError):associate([],float('nan'))

    def test_pipeline_and_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'video.avi';p.write_bytes(b'x')
            rgb=np.zeros((90,160,3),dtype=np.uint8)
            pred={'detections':[detection(1,[.1,.1,.5,.5])],'truncated':False}
            with patch('sea.tracking.probe',return_value={'video':True,'duration_s':6}), \
                 patch('sea.tracking.load_detector',return_value=(lambda *_:pred,{'model':'mock'},['cat'])), \
                 patch('sea.tracking.load_image',side_effect=[rgb,RuntimeError('decode'),rgb]):
                r,frames=track(p,0,6,3,keep_frames=True)
                self.assertEqual(r['observed_sample_count'],2)
                self.assertEqual(r['track_count'],2)
                self.assertEqual(r['samples'][1]['status'],'decode_failed')
                self.assertEqual(len(frames),2)
                self.assertTrue(contact_sheet(r,frames).startswith(b'\x89PNG'))
                json.dumps(r,allow_nan=False)

    @unittest.skipUnless(os.environ.get('SEA_VISION_TEST_IMAGE'),'Optional pretrained tracking fixture not configured')
    def test_real_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cats.avi'
            # Repeated source picture verifies real decoding and model association, not motion accuracy.
            subprocess.run(['ffmpeg','-v','error','-nostdin','-loop','1','-i',
                            os.environ['SEA_VISION_TEST_IMAGE'],'-t','2','-r','2',
                            '-vf','scale=640:480','-c:v','mpeg4','-threads','1',str(p)],
                           check=True,timeout=30,stdin=subprocess.DEVNULL)
            r,frames=track(p,0,1.5,2,.25,labels=['cat'],keep_frames=True)
            self.assertEqual(r['observed_sample_count'],2)
            self.assertTrue(any(t['label']=='cat' and t['observation_count']==2 for t in r['tracks']),r)
            self.assertTrue(contact_sheet(r,frames).startswith(b'\x89PNG'))
