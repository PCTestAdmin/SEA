import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sea import benchmark as b
from sea.analysis import analyze_target
from sea.event_relations import relate


ROOT=Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root=Path(tmp.name).resolve()
        avi=cls.root/'demo.avi'
        mp4=cls.root/'demo.mp4'
        subprocess.run([sys.executable,str(ROOT/'examples'/'make_demo.py'),str(avi)],check=True,timeout=30)
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(avi),'-c:v','mpeg4',
                        '-pix_fmt','yuv420p','-c:a','aac',str(mp4)],check=True,timeout=30)
        cls.spec=b.load(ROOT/'benchmarks'/'smoke_spec.json')
        cls.suite,cls.key=b.prepare(cls.spec,cls.root)
        cls.protocol={'pair_id':'unit-test','model':'fake-test-model','host':'test-host','settings':'fixed',
                      'shared_input':'same MP4','budget':'fixed'}
        cls.baseline=b.template(cls.suite,'baseline',cls.protocol)
        cls.assisted=b.template(cls.suite,'sea',cls.protocol)
        cls.baseline['answers']={'q01':1,'q02':2,'q03':None}
        cls.assisted['answers']={'q01':0,'q02':0,'q03':2}
        cls.baseline['clip_runs']['demo01']={'status':'completed','tool_calls':0,'elapsed_s':5}
        cls.assisted['clip_runs']['demo01']={'status':'completed','tool_calls':3,'elapsed_s':7}

    def test_paired_scores_and_abstentions(self):
        r=b.score(self.suite,self.key,self.baseline,self.assisted)
        self.assertEqual(r['overall']['baseline_correct'],1)
        self.assertEqual(r['overall']['sea_correct'],2)
        self.assertEqual(r['overall']['improved'],2)
        self.assertEqual(r['overall']['regressed'],1)
        self.assertEqual(r['overall']['baseline_abstentions'],1)
        self.assertEqual(r['overall']['delta_percentage_points'],33.3333)
        self.assertEqual(r['by_source_kind']['synthetic'],r['overall'])
        self.assertEqual(r['run_summary']['sea']['sea_tool_calls'],3)

    def test_blind_packet_and_content_hash(self):
        packet=b.packet(self.suite,'demo01',self.root)
        self.assertNotIn('answers',packet)
        self.assertNotIn('answer',packet['questions'][0])
        self.assertNotIn('source',packet)
        changed=copy.deepcopy(self.suite)
        changed['clips'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'changed'):
            b.packet(changed,'demo01',self.root)
        with self.assertRaises(ValueError):b.media_file(self.root,'../demo.mp4')

    def test_invalid_runs(self):
        for mutate in (lambda r:r['protocol'].update(model='other'),
                       lambda r:r['answers'].pop('q01'),
                       lambda r:r['answers'].update(q01=True),
                       lambda r:r['clip_runs']['demo01'].update(status='pending'),
                       lambda r:r['clip_runs']['demo01'].update(status='error')):
            run=copy.deepcopy(self.assisted);mutate(run)
            with self.assertRaises(ValueError):b.score(self.suite,self.key,self.baseline,run)
        run=copy.deepcopy(self.baseline);run['clip_runs']['demo01']['tool_calls']=1
        with self.assertRaises(ValueError):b.score(self.suite,self.key,run,self.assisted)
        key=copy.deepcopy(self.key);key['suite_id']='wrong'
        with self.assertRaises(ValueError):b.score(self.suite,key,self.baseline,self.assisted)

    def test_failed_clip_counts_as_incorrect(self):
        run=copy.deepcopy(self.assisted)
        run['answers']={q:None for q in run['answers']}
        run['clip_runs']['demo01']={'status':'error','tool_calls':0,'elapsed_s':1}
        r=b.score(self.suite,self.key,self.baseline,run)
        self.assertEqual(r['overall']['sea_correct'],0)
        self.assertEqual(r['overall']['sea_abstentions'],3)
        self.assertEqual(r['run_summary']['sea']['failed_clips'],1)
        self.assertEqual(r['assisted_clips_without_sea_calls'],['demo01'])

    def test_real_mp4_decode_smoke(self):
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':str(self.root)}):
            page=analyze_target(str(self.root/'demo.mp4'),segment_seconds=4,page_size=2)
        r=relate([page])
        self.assertEqual(r['missing_ranges'],[])
        self.assertTrue(any(e['kind']=='scene_change_candidate' for e in r['events']))

    def test_cli(self):
        out=self.root/'frozen'
        def run(*args):
            p=subprocess.run([sys.executable,'-m','sea.benchmark',*map(str,args)],
                             capture_output=True,text=True,check=True,timeout=30)
            return json.loads(p.stdout)
        result=run('prepare',ROOT/'benchmarks'/'smoke_spec.json',self.root,out)
        self.assertEqual(result['suite_id'],b.digest(self.suite))
        for name,obj in [('baseline',self.baseline),('assisted',self.assisted),('protocol',self.protocol)]:
            (out/(name+'.json')).write_text(json.dumps(obj),encoding='utf-8')
        self.assertEqual(run('packet',out/'suite.json','demo01',self.root),b.packet(self.suite,'demo01',self.root))
        self.assertEqual(run('run-template',out/'suite.json','sea',out/'protocol.json'),b.template(self.suite,'sea',self.protocol))
        self.assertEqual(run('score',out/'suite.json',out/'key.json',out/'baseline.json',out/'assisted.json'),
                         b.score(self.suite,self.key,self.baseline,self.assisted))
