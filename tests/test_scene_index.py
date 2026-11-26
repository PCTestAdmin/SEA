import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sea.analysis import analyze_target
from sea.evidence import digest
from sea.scene_index import summarize


def rehash(p):
    p['evidence_id']=digest(p['record'])
    return p


class SceneIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root=Path(tmp.name).resolve()
        p=cls.root/'demo.avi'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,timeout=30)
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(cls.root)}):
            cls.a=analyze_target(str(p),segment_seconds=4,page_size=1)
            cls.b=analyze_target(str(p),segment_seconds=4,cursor=1,page_size=1)

    def test_real_video_scenes_and_paging(self):
        r=summarize([self.b,self.a])
        self.assertEqual(r,summarize([self.a,self.b]))
        scenes=r['scenes']
        self.assertEqual([(s['start_s'],s['end_s']) for s in scenes],[(0,2),(2,4),(4,6)])
        self.assertEqual([s['start_reason'] for s in scenes],['video_start','scene_change_candidate','scene_change_candidate'])
        self.assertEqual([s['sample_count'] for s in scenes],[8,8,8])
        self.assertEqual([s['audio']['unknown_s'] for s in scenes],[0,0,0])
        self.assertGreater(scenes[0]['audio']['low_level_observed_s'],1.5)
        self.assertLess(scenes[1]['audio']['low_level_observed_s'],.5)
        self.assertGreater(scenes[2]['audio']['low_level_observed_s'],1.5)
        self.assertTrue(all(s['representative_samples'] and s['evidence_segments'] for s in scenes))
        first=summarize([self.a,self.b],limit=1)
        self.assertEqual(first['next_offset'],1)
        self.assertEqual(first['scenes']+summarize([self.a,self.b],offset=1)['scenes'],scenes)
        paths=[]
        for i,p in enumerate((self.a,self.b)):
            file=self.root/f'scene-page{i}.json'
            file.write_text(json.dumps(p),encoding='utf-8')
            paths.append(str(file))
        proc=subprocess.run([sys.executable,'-m','sea.setup','summarize-video-scenes',*paths],
                            capture_output=True,text=True,check=True,timeout=30)
        self.assertEqual(json.loads(proc.stdout),r)

    def test_missing_and_independent_modalities(self):
        r=summarize([self.b])
        self.assertEqual(r['scenes'][0]['start_reason'],'missing_evidence')
        self.assertEqual(r['scenes'][0]['audio']['unknown_s'],4)
        self.assertEqual(r['scenes'][1]['start_reason'],'after_gap_or_unobserved_boundary')
        a=copy.deepcopy(self.a)
        a['record']['normalized_result']['results'][0]['visual_status']='failed'
        r=summarize([rehash(a),self.b])
        self.assertEqual(r['scenes'][0]['visual_status'],'unavailable')
        self.assertEqual(r['scenes'][0]['audio']['observed_s'],4)
        self.assertEqual(r['scenes'][1]['start_reason'],'after_gap_or_unobserved_boundary')
        a=copy.deepcopy(self.a)
        a['record']['normalized_result']['results'][0]['audio_status']='failed'
        r=summarize([rehash(a),self.b])
        self.assertEqual(len(r['scenes']),3)
        self.assertEqual(r['scenes'][1]['audio']['unknown_s'],2)
        self.assertEqual(r['scenes'][1]['visual_status'],'sampled')

    def test_no_cut_at_segment_boundary_and_unknown_audio(self):
        b=copy.deepcopy(self.b)
        row=b['record']['normalized_result']['results'][0]
        row['comparisons'][0]['scene_change_candidate']=False
        row['audio_status']='not_present'
        r=summarize([self.a,rehash(b)])
        self.assertEqual([(s['start_s'],s['end_s']) for s in r['scenes']],[(0,2),(2,6)])
        self.assertEqual(r['scenes'][1]['audio']['no_stream_s'],2)
        self.assertEqual(r['scenes'][1]['sample_count'],16)
        self.assertEqual(len(r['scenes'][1]['evidence_segments']),2)

    def test_invalid_evidence(self):
        a=copy.deepcopy(self.a)
        a['record']['normalized_result']['results'][0]['audio_bins'][0]['end_s']=1.5
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            summarize([a])
        with self.assertRaisesRegex(ValueError,'audio bin'):
            summarize([rehash(a)])
        with self.assertRaises(ValueError):
            summarize([self.a,self.a])
        with self.assertRaises(ValueError):
            summarize([self.a],limit=51)
