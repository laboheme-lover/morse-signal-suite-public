import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import soundfile as sf
from batch_preflight import inspect,estimate,GIB

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
        sf.write(self.p/'a.wav',np.zeros(16000),16000);(self.p/'a.txt').write_text('イ',encoding='utf-8')
        self.row=dict(id='one',audio='a.wav',reference='a.txt',body={'mode':'full'})
        self.source=self.p/'input.json';self.write([self.row]);self.resources=dict(available_memory_bytes=16*GIB,free_disk_bytes=100*GIB)
    def tearDown(self):self.tmp.cleanup()
    def write(self,rows):self.source.write_text(json.dumps({'recordings':rows}),encoding='utf-8')
    def check(self,**kwargs):return inspect(self.source,self.p/'out',resources=self.resources,**kwargs)
    def test_ready_and_monotonic_budget(self):
        self.assertEqual(self.check()['status'],'READY');self.assertFalse((self.p/'out').exists())
        self.assertGreater(estimate([1800])['memory_bytes'],estimate([120])['memory_bytes'])
    def test_insufficient_memory_and_disk(self):
        self.resources=dict(available_memory_bytes=0,free_disk_bytes=0);r=self.check()
        self.assertEqual(r['status'],'BLOCKED');self.assertTrue(any('メモリ' in e for e in r['errors']));self.assertTrue(any('容量' in e for e in r['errors']))
    def test_missing_and_duplicate(self):
        self.write([self.row,self.row]);self.assertEqual(self.check()['status'],'BLOCKED')
        (self.p/'a.wav').unlink();self.assertEqual(self.check()['status'],'BLOCKED')
    def test_duration_bounds(self):
        for seconds,expected in [(1800,'READY'),(1800.001,'BLOCKED'),(.499,'BLOCKED')]:
            with patch('batch_preflight.sf.info',return_value=SimpleNamespace(frames=seconds*16000,samplerate=16000)):
                self.assertEqual(self.check()['status'],expected)
    def test_invalid_reference_and_body(self):
        (self.p/'a.txt').write_text('（イ',encoding='utf-8');self.assertEqual(self.check()['status'],'BLOCKED')
        (self.p/'a.txt').write_text('イ',encoding='utf-8');self.row['body']=dict(mode='window',start_seconds=0,end_seconds=2);self.write([self.row])
        self.assertEqual(self.check()['status'],'BLOCKED')
    def test_invalid_body_structure(self):
        for body in (None,[],1,'full'):
            self.row['body']=body;self.write([self.row]);self.assertEqual(self.check()['status'],'BLOCKED')
    def test_unwritable_destination(self):
        with patch('batch_preflight.tempfile.TemporaryFile',side_effect=PermissionError('書込不可')):
            self.assertEqual(self.check()['status'],'BLOCKED')
    def test_corrupt_json(self):
        self.source.write_text('{',encoding='utf-8');self.assertEqual(self.check()['status'],'BLOCKED')
    def test_resume_excludes_completed_load(self):
        out=self.p/'out';(out/'one').mkdir(parents=True);(out/'one/result.json').write_text('{}')
        row=dict(self.row,audio=str(self.p/'a.wav'),reference_path=str(self.p/'a.txt'))
        (out/'manifest.json').write_text(json.dumps({'recordings':[row]}))
        r=inspect(out/'manifest.json',out,resume=True,resources=self.resources)
        self.assertEqual(r['status'],'READY');self.assertTrue(r['recordings'][0]['completed'])
        self.assertEqual(r['estimated_start_requirements'],estimate([]))

if __name__=='__main__':unittest.main()
