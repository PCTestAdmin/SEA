import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sea.compact_video import compact_row,encode,overview
from sea.video_perception import scan_page
from sea.scan_cache import CACHE, ScanCache


class CompactVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root=Path(tmp.name).resolve()
        cls.p=cls.root/'demo.avi'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(cls.p)],check=True,timeout=30)

    def setUp(self):
        CACHE.clear()
        self.addCleanup(CACHE.clear)

    def test_real_clip_size_and_equivalence(self):
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root)}):
            report=overview(str(self.p),segment_seconds=4)
            raw=scan_page(self.p,4,0,2,4)
            self.assertEqual(report['rows'],[compact_row(r,4) for r in raw['results']])
            self.assertEqual(report['raw_rows_json_bytes'],len(encode(raw['results'])))
            # Gate actual serialized payload size, not a claimed LLM token count.
            self.assertLess(len(encode(report)),.40*len(encode(raw['results'])))
            self.assertIsNone(report['next_cursor'])
            self.assertEqual([r['cuts'] for r in report['rows']],[[8],[0]])
            self.assertEqual([r['samples'] for r in report['rows']],[16,8])
            self.assertEqual(report['rows'][0]['low_ms'],[[0,2000]])
            self.assertEqual(report['rows'][1]['low_ms'],[[0,2000]])
            first=overview(str(self.p),segment_seconds=4,max_segments=1)
            second=overview(str(self.p),cursor=first['next_cursor'],segment_seconds=4,
                            expected_revision=first['source_revision'])
            self.assertEqual(first['rows']+second['rows'],report['rows'])
            self.assertIsNone(second['next_cursor'])
            with self.assertRaises(ValueError):
                overview(str(self.p),expected_revision='stale')
            with self.assertRaises(ValueError):
                overview(str(self.p),output_budget_bytes=100)

    def test_dense_budget_and_no_skipped_rows(self):
        # Simulate a high-change 72-second video with exact synthetic measurements.
        def page(p,segment_seconds,cursor,page_size,sample_fps,rev):
            rows=[]
            for i in range(cursor,min(6,cursor+page_size)):
                a=i*12
                first=0 if i else 1
                rows.append({'index':i,'start_s':a,'end_s':a+12,
                    'visual_status':'sampled','audio_status':'measured',
                    'preceding_boundary_status':'observed' if i else 'start_of_video',
                    'sample_count':48,'expected_sample_count':48,
                    'sample_times_s':[a+j/4 for j in range(48)],
                    'comparisons':[{'time_s':a+j/4,'boundary_comparison':j==0,
                         'changed_pixel_fraction':1.,'scene_change_candidate':True}
                        for j in range(first,48)],
                    'audio_bins':[{'start_s':a+j*.5,'end_s':a+(j+1)*.5,
                        'low_level':j%2==0,'dominant_frequency_hz':None if j%2==0 else 440.}
                        for j in range(24)]})
            return {'results':rows}
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root)}), \
             patch('sea.compact_video.source',return_value=('r',{'duration_s':72.})), \
             patch('sea.compact_video.source_revision',return_value='r'), \
             patch('sea.compact_video.scan_page',side_effect=page):
            cursor=0
            seen=[]
            while cursor is not None:
                r=overview(str(self.p),cursor=cursor,max_segments=6,output_budget_bytes=2048)
                self.assertLessEqual(len(encode(r)),2048)
                self.assertTrue(r['rows'])
                seen.extend(r['rows'])
                cursor=r['next_cursor']
            self.assertEqual([r['i'] for r in seen],list(range(6)))
            self.assertEqual([len(r['cuts']) for r in seen],[47,48,48,48,48,48])
            self.assertEqual([len(r['low_ms']) for r in seen],[12]*6)

    def test_unknown_and_absent_audio(self):
        base={'index':0,'start_s':0,'end_s':4,'visual_status':'failed',
              'preceding_boundary_status':'start_of_video','audio_status':'partial',
              'audio_bins':[{'start_s':0,'end_s':.5,'low_level':False,'dominant_frequency_hz':440.}]}
        r=compact_row(base,4)
        self.assertEqual(r['observed_ms'],[[0,500]])
        self.assertEqual(r['low_ms'],[])
        self.assertNotIn('cuts',r)
        r=compact_row({**base,'audio_status':'not_present'},4)
        self.assertEqual(r['a'],'not_present')
        self.assertNotIn('observed_ms',r)

    def test_cache_reuses_segments_and_respects_revision(self):
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root),'SEA_SCAN_CACHE':'on'}):
            with patch('sea.compact_video.scan_page',wraps=scan_page) as scans:
                first=overview(str(self.p),segment_seconds=4,max_segments=2)
                self.assertEqual(scans.call_count,1)
                again=overview(str(self.p),segment_seconds=4,max_segments=2,output_budget_bytes=4000)
                self.assertEqual(first,again)
                self.assertEqual(scans.call_count,1)
                second=overview(str(self.p),cursor=1,segment_seconds=4,max_segments=1)
                self.assertEqual(second['rows'],first['rows'][1:])
                self.assertEqual(scans.call_count,1)
                overview(str(self.p),segment_seconds=4,sample_fps=2)
                self.assertEqual(scans.call_count,2)
                with patch.dict(os.environ,{'SEA_SCAN_CACHE':'off'}):
                    overview(str(self.p),segment_seconds=4)
                self.assertEqual(scans.call_count,3)
                # Change mtime without changing valid media bytes.
                st=self.p.stat()
                os.utime(self.p,ns=(st.st_atime_ns,st.st_mtime_ns+2000000000))
                try:
                    with self.assertRaises(ValueError):
                        overview(str(self.p),segment_seconds=4,expected_revision=first['source_revision'])
                    new=overview(str(self.p),segment_seconds=4)
                    self.assertNotEqual(first['source_revision'],new['source_revision'])
                    self.assertEqual(scans.call_count,4)
                finally:
                    os.utime(self.p,ns=(st.st_atime_ns,st.st_mtime_ns))

    def test_cache_limits_ttl_and_copy(self):
        now=[0.]
        c=ScanCache(max_entries=2,max_bytes=64,ttl=5,clock=lambda:now[0])
        c.put('a',[1])
        c.put('b',[2])
        value=c.get('a')
        value.append(9)
        self.assertEqual(c.get('a'),[1])
        c.put('c',[3])
        self.assertIsNone(c.get('b'))
        self.assertEqual(c.get('a'),[1])
        c.put('large',['x'*100])
        self.assertIsNone(c.get('large'))
        self.assertLessEqual(c.size,64)
        now[0]=5.
        self.assertIsNone(c.get('a'))
        self.assertEqual(c.size,0)

    def test_cli(self):
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root)}):
            p=subprocess.run([sys.executable,'-m','sea.setup','compact-video',str(self.p),
                              '--segment-seconds','4'],capture_output=True,text=True,check=True,timeout=30)
            self.assertEqual(json.loads(p.stdout),overview(str(self.p),segment_seconds=4))
