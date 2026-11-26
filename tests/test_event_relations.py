import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sea.analysis import analyze_target
from sea.event_relations import relate
from sea.evidence import digest
from sea.video_perception import visual_changes


def rehash(page):
    page['evidence_id']=digest(page['record'])
    return page


class EventRelationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root=Path(tmp.name).resolve()
        cls.p=cls.root/'demo.avi'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(cls.p)],check=True,timeout=30)
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(cls.root)}):
            cls.a=analyze_target(str(cls.p),segment_seconds=4,page_size=1)
            cls.b=analyze_target(str(cls.p),cursor=1,segment_seconds=4,page_size=1)

    def test_real_pages_audio_and_cli(self):
        r=relate([self.b,self.a])
        self.assertEqual(r,relate([self.a,self.b]))
        self.assertEqual(r['missing_ranges'],[])
        cuts=[e for e in r['events'] if e['kind']=='scene_change_candidate']
        self.assertEqual([e['time_s'] for e in cuts],[2,4])
        self.assertTrue(all(any(x['kind']=='near_audio_transition' for x in e['relations']) for e in cuts))
        self.assertTrue(any(x['kind']=='follows_visual_change' for x in cuts[1]['relations']))
        first=relate([self.a,self.b],limit=1)
        self.assertEqual(first['next_offset'],1)
        self.assertEqual(first['events']+relate([self.a,self.b],offset=1)['events'],r['events'])
        paths=[]
        for i,page in enumerate((self.a,self.b)):
            p=self.root/f'event-page{i}.json';p.write_text(json.dumps(page),encoding='utf-8')
            paths.append(str(p))
        proc=subprocess.run([sys.executable,'-m','sea.setup','relate-video-events',*paths],
                            capture_output=True,text=True,check=True,timeout=30)
        self.assertEqual(json.loads(proc.stdout),r)

    def test_local_overlap_and_missing_boundary(self):
        a=copy.deepcopy(self.a)
        row=a['record']['normalized_result']['results'][0]
        frames=np.zeros((16,8,8,3),dtype=np.uint8)
        frames[1,:2,:2]=255
        frames[2,:2,:2]=0
        frames[3:,:2,2:4]=255
        row['comparisons']=visual_changes(frames,0,4)
        r=relate([rehash(a)])
        local=[e for e in r['events'] if e['kind']=='visual_change']
        self.assertEqual([e['changed_tiles_4x4'] for e in local],[[0],[0],[1]])
        self.assertEqual(local[1]['relations'][0]['tile_jaccard'],1)
        self.assertEqual(local[2]['relations'][0]['tile_jaccard'],0)
        only=relate([self.b])
        self.assertEqual(only['missing_ranges'][0]['start_s'],0)
        self.assertFalse(any(e['time_s']==4 for e in only['events']))

    def test_measured_audio_boundary_gap(self):
        # A small decoder shortfall is already permitted by scan_page.
        # Retain a cross-modal transition, but expose its unobserved interval.
        for gap in (.016,.03,.031,.08):
            with self.subTest(gap=gap):
                a=copy.deepcopy(self.a)
                b=copy.deepcopy(self.b)
                left=a['record']['normalized_result']['results'][0]
                right=b['record']['normalized_result']['results'][0]
                left['audio_bins'][-1].update(end_s=round(4-gap,3),low_level=False)
                left['audio']['analyzed_s']=round(4-gap,3)
                right['audio_bins'][0]['low_level']=True
                r=relate([rehash(a),rehash(b)])
                transitions=[e for e in r['events'] if e['kind']=='audio_became_low' and e['time_s']==4]
                cuts=[e for e in r['events'] if e['kind']=='scene_change_candidate' and e['time_s']==4]
                self.assertEqual(len(cuts),1)
                links=[x for x in cuts[0]['relations'] if x['kind']=='near_audio_transition']
                if gap<=.03:
                    self.assertEqual(len(transitions),1)
                    self.assertEqual(transitions[0]['unobserved_gap_s'],gap)
                    self.assertEqual(transitions[0]['gap_range_s'],[round(4-gap,3),4])
                    self.assertEqual(links[0]['unobserved_audio_gap_s'],gap)
                else:
                    self.assertEqual(transitions,[])
                    self.assertEqual(links,[])

    def test_invalid_and_incomplete(self):
        a=copy.deepcopy(self.a)
        a['record']['normalized_result']['results'][0]['comparisons'][0].pop('changed_tiles_4x4')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            relate([a])
        with self.assertRaisesRegex(ValueError,'change grid'):
            relate([rehash(a)])
        b=copy.deepcopy(self.b)
        b['record']['normalized_result']['results'][0]['audio_status']='partial'
        r=relate([self.a,rehash(b)])
        self.assertEqual(r['skipped_segments'],['V000002'])
        self.assertTrue(all(e['time_s']<4 for e in r['events']))
        with self.assertRaises(ValueError):relate([self.a,self.a])
        with self.assertRaises(ValueError):relate([self.a],limit=101)
