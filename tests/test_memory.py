import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import numpy as np
from sea.memory import remember_audio,remember_signals,list_memory,recall,compare_memory,forget,save

class MemoryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.mem=self.root/'memory';self.mem.mkdir()
        env=patch.dict(os.environ,{'SEA_MEMORY_DIR':str(self.mem)})
        env.start();self.addCleanup(env.stop)

    def tone(self,name,amp):
        p=self.root/name
        x=amp*np.sin(2*np.pi*440*np.arange(16000)/16000)
        with wave.open(str(p),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes((x*32767).astype('<i2').tobytes())
        return p

    def test_disabled_and_empty(self):
        with patch.dict(os.environ,{'SEA_MEMORY_DIR':''}):
            with self.assertRaises(ValueError):list_memory()
        self.assertEqual(list_memory()['total'],0)
        self.assertEqual(list(self.mem.iterdir()),[])

    def test_audio_history(self):
        a=remember_audio(self.tone('first.wav',.4),'baseline',0,1)
        b=remember_audio(self.tone('second.wav',.2),'new',0,1)
        self.assertEqual(list_memory()['total'],2)
        stored=recall(a['id'])
        self.assertEqual(stored['label'],'baseline')
        self.assertNotIn('first.wav',json.dumps(stored))
        r=compare_memory(a['id'],b['id'])
        self.assertAlmostEqual(r['delta_b_minus_a']['rms_dbfs'],-6.02,places=1)
        with self.assertRaises(ValueError):forget(a['id'])
        self.assertEqual(forget(a['id'],True)['status'],'deleted')
        self.assertEqual(list_memory()['total'],1)
        with self.assertRaises(ValueError):recall(a['id'])

    def test_signal_history(self):
        p=self.root/'log.csv'
        p.write_text('t,x\n0,1\n1,3\n',encoding='utf-8')
        a=remember_signals(p,'before','t',['x'])
        p.write_text('t,x\n0,2\n1,4\n',encoding='utf-8')
        b=remember_signals(p,'after','t',['x'])
        self.assertEqual(compare_memory(a['id'],b['id'])['delta_b_minus_a'][0]['mean'],1)
        c=remember_audio(self.tone('tone.wav',.2),'tone',0,1)
        with self.assertRaises(ValueError):compare_memory(a['id'],c['id'])

    def test_record_limits(self):
        with patch('sea.memory.MAX_RECORDS',1):
            save('first','signals',{})
            with self.assertRaises(ValueError):save('second','signals',{})
        with self.assertRaises(ValueError):recall('../outside')
        with self.assertRaises(ValueError):save('','audio',{})
        with self.assertRaises(ValueError):list_memory(101)

    def test_existing_database(self):
        import sqlite3
        p=self.mem/'sea-memory.sqlite3'
        db=sqlite3.connect(str(p))
        db.execute('CREATE TABLE other (value TEXT)')
        db.close()
        with self.assertRaises(ValueError):save('first','signals',{})
        db=sqlite3.connect(str(p))
        try:
            self.assertEqual(db.execute('SELECT name FROM sqlite_master').fetchall(),[('other',)])
        finally:
            db.close()
