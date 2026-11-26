import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
from PIL import Image
from sea.analysis import analyze_target,inspect_view,audit_video_coverage
from sea.evidence import digest
from sea.workflows import guidance,render

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        env=patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root)})
        env.start();self.addCleanup(env.stop)
        self.wav=self.root/'audio.wav'
        with wave.open(str(self.wav),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes(b'\0'*32000)

    def test_evidence_and_projection(self):
        r=analyze_target(str(self.wav),duration_s=1)
        self.assertEqual(r['record']['target_kind'],'audio')
        s=inspect_view(r)
        self.assertEqual(s['row_count'],2)
        p=inspect_view(r,'page',0,1)
        self.assertEqual(p['next_offset'],1)
        self.assertEqual(p['parent_evidence_id'],r['evidence_id'])
        bad=copy.deepcopy(r)
        bad['record']['coverage']='changed'
        with self.assertRaisesRegex(ValueError,'digest mismatch'):inspect_view(bad)
        with self.assertRaises(ValueError):analyze_target(str(self.wav),expected_revision='wrong')

    def test_video_and_image(self):
        p=self.root/'video.avi'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,timeout=30)
        a=analyze_target(str(p),segment_seconds=4,page_size=1)
        self.assertEqual(a['record']['next_cursor'],1)
        b=analyze_target(str(p),cursor=1,segment_seconds=4,page_size=1,expected_revision=a['record']['source_revision'])
        self.assertIsNone(b['record']['next_cursor'])
        self.assertEqual(inspect_view(b)['row_count'],1)
        image=self.root/'image.png';Image.new('RGB',(64,64),'red').save(image)
        self.assertEqual(analyze_target(str(image))['record']['target_kind'],'image')

    def test_cli_same_contract(self):
        expected=analyze_target(str(self.wav),duration_s=1)
        self.assertEqual(expected,analyze_target(str(self.wav),start_s=-0.0,duration_s=1.0))
        self.assertEqual(expected,analyze_target(str(self.wav),start_s=0.0,duration_s=1.0))
        p=subprocess.run([sys.executable,'-m','sea.setup','analyze',str(self.wav),'--duration', '1'],
                         capture_output=True,text=True,check=True,timeout=60)
        self.assertEqual(json.loads(p.stdout),expected)
        file=self.root/'report.json';file.write_text(p.stdout,encoding='utf-8')
        p=subprocess.run([sys.executable,'-m','sea.setup','inspect-evidence',str(file),'--view','page','--limit','1'],
                         capture_output=True,text=True,check=True,timeout=30)
        self.assertEqual(json.loads(p.stdout)['parent_evidence_id'],expected['evidence_id'])

    def test_video_coverage(self):
        p=self.root/'video.avi'
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(p)],check=True,timeout=30)
        a=analyze_target(str(p),segment_seconds=4,page_size=1)
        b=analyze_target(str(p),cursor=1,segment_seconds=4,page_size=1)
        partial=audit_video_coverage([b])
        self.assertEqual(partial['missing_segments'],1)
        self.assertEqual(partial['missing_ranges'][0]['start_s'],0)
        full=audit_video_coverage([b,a])
        self.assertTrue(full['all_segment_rows_submitted'])
        self.assertEqual(full['missing_ranges'],[])
        self.assertEqual(full,audit_video_coverage([a,b]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            audit_video_coverage([a,a])
        wrong=analyze_target(str(p),segment_seconds=8,page_size=1)
        with self.assertRaisesRegex(ValueError,'different'):
            audit_video_coverage([a,wrong])
        broken=copy.deepcopy(b)
        broken['record']['normalized_result']['results'][0]['visual_status']='failed'
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            audit_video_coverage([a,broken])
        broken['evidence_id']=digest(broken['record'])
        report=audit_video_coverage([a,broken])
        self.assertTrue(report['all_segment_rows_submitted'])
        self.assertFalse(report['all_sampled_measurements_reported_complete'])
        self.assertEqual(report['incomplete_segments'][-1]['visual_status'],'failed')
        with self.assertRaises(ValueError):
            audit_video_coverage([])
        with self.assertRaises(ValueError):
            audit_video_coverage([a]*17)
        with self.assertRaises(ValueError):
            audit_video_coverage([analyze_target(str(self.wav),duration_s=1)])
        paths=[]
        for i,page in enumerate((a,b)):
            file=self.root/f'page{i}.json'
            file.write_text(json.dumps(page),encoding='utf-8')
            paths.append(str(file))
        proc=subprocess.run([sys.executable,'-m','sea.setup','audit-video-coverage',*paths],
                            capture_output=True,text=True,check=True,timeout=30)
        self.assertEqual(json.loads(proc.stdout),full)

    def test_shared_guidance(self):
        self.assertIn('understand-full-video',guidance()['workflows'])
        self.assertEqual(guidance('understand-full-video')['rendered'],render('understand-full-video'))
        self.assertIn('next_cursor',render('understand-full-video'))
        with self.assertRaises(ValueError):render('unknown')
