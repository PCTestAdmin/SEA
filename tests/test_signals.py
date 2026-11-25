from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os
import json
from sea.engine import resolve_media
from sea.signals import analyze_signals

class SignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'signals.csv'

    def test_summary(self):
        self.p.write_text('time_s,a,b,c\n0,1,2,7\n1,2,4,7\n3,5,10,7\n',encoding='utf-8')
        r=analyze_signals(self.p,'time_s',['a','b','c'],{'a':2})
        self.assertEqual(r['rows'],3)
        self.assertEqual(r['median_sample_interval_s'],1.5)
        self.assertEqual(r['channels'][0]['threshold_hit_count'],1)
        self.assertEqual(r['channels'][0]['threshold_events'][0]['to_s'],3)
        self.assertEqual(r['same_row_correlations'][0]['pearson_r'],1)
        self.assertIsNone(r['same_row_correlations'][1]['pearson_r'])
        json.dumps(r,allow_nan=False)

    def test_reject_invalid(self):
        for content in ('t,a\n0,NaN\n1,2\n','t,a\n1,1\n1,2\n',
                        't,a,a\n0,1,2\n1,2,3\n','t,a\n0,1\n1,\n','t,a\n0,1\n'):
            self.p.write_text(content,encoding='utf-8')
            with self.assertRaises(ValueError):analyze_signals(self.p,'t',['a'])

    def test_limits(self):
        self.p.write_text('t,a\n0,1\n1,2\n',encoding='utf-8')
        with self.assertRaises(ValueError):analyze_signals(self.p,'t',['a'],{'a':0})
        with self.assertRaises(ValueError):analyze_signals(self.p,'t',['a','a'])
        self.p.write_bytes(b'x'*(2*1024*1024+1))
        with self.assertRaises(ValueError):analyze_signals(self.p,'t',['a'])

    def test_scope(self):
        self.p.write_text('t,a\n0,1\n1,2\n',encoding='utf-8')
        with patch.dict(os.environ,{'SEA_MEDIA_ROOTS':self.tmp.name}):
            with self.assertRaises(ValueError):resolve_media(str(self.p))
            self.assertEqual(resolve_media(str(self.p),allow_csv=True),self.p.resolve())
