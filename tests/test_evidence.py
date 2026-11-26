import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sqlite3
import wave
from sea import evidence

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.store=self.root/'evidence';self.store.mkdir()
        self.wav=self.root/'source.wav'
        with wave.open(str(self.wav),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes(b'\0'*32000)
        env=patch.dict(os.environ,{'SEA_EVIDENCE_DIR':str(self.store),'SEA_MEDIA_ROOTS':str(self.root)})
        env.start();self.addCleanup(env.stop)

    def capture(self):
        return evidence.capture(str(self.wav),'sense_audio',0,1,True)

    def test_capture_verify_delete(self):
        r=self.capture()
        self.assertEqual(len(r['id']),64)
        self.assertEqual(evidence.recall(r['id']),r)
        self.assertNotIn('file',r['envelope']['report'])
        self.assertTrue(evidence.verify(r['id'],str(self.wav))['source_matches'])
        with self.wav.open('ab') as f:f.write(b'x')
        self.assertFalse(evidence.verify(r['id'],str(self.wav))['source_matches'])
        self.assertEqual(evidence.list_records()['total'],1)
        with self.assertRaises(ValueError):evidence.delete(r['id'])
        evidence.delete(r['id'],True)
        self.assertEqual(evidence.list_records()['total'],0)

    def test_opt_in(self):
        with self.assertRaises(ValueError):evidence.capture(str(self.wav),'sense_audio')
        self.assertEqual(evidence.list_records()['total'],0)
        self.assertEqual(list(self.store.iterdir()),[])
        with patch.dict(os.environ,{'SEA_EVIDENCE_DIR':''}):
            with self.assertRaises(ValueError):self.capture()

    def test_tamper(self):
        r=self.capture()
        with sqlite3.connect(self.store/'sea-evidence.sqlite3') as db:
            db.execute('UPDATE evidence SET payload=?',(b'{}',))
        with self.assertRaisesRegex(ValueError,'digest mismatch'):evidence.recall(r['id'])

    def test_limits(self):
        with self.assertRaises(ValueError):evidence.capture(str(self.wav),'arbitrary',confirm=True)
        with patch('sea.evidence.MAX_SOURCE',1):
            with self.assertRaises(ValueError):self.capture()
        with self.assertRaises(ValueError):evidence.recall('../invalid')
        with patch('sea.evidence.MAX_RECORDS',1):
            self.capture()
            with self.assertRaises(ValueError):self.capture()

    def test_no_unrelated_database_overwrite(self):
        with sqlite3.connect(self.store/'sea-evidence.sqlite3') as db:
            db.execute('CREATE TABLE unrelated (id INTEGER)')
        with self.assertRaises(ValueError):self.capture()
