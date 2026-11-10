"""Regression tests for transient Windows JSON publication locks."""
import json, os, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
from recognition_job import save

class SaveTests(unittest.TestCase):
    def test_transient_lock(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'result.json'
            original=Path.replace
            count=[0]
            def replace(src,dst):
                count[0]+=1
                if count[0]<3:raise PermissionError('busy reader')
                return original(src,dst)
            with patch.object(Path,'replace',replace),patch('time.sleep'):
                self.assertTrue(save(p,{'text':'イ'}))
            self.assertEqual(json.loads(p.read_text(encoding='utf-8')),{'text':'イ'})
            self.assertFalse(p.with_suffix('.tmp').exists())

    def test_persistent_lock_progress_only_is_optional(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'progress.json';p.write_text('{"fraction":0.1}')
            with patch.object(Path,'replace',side_effect=PermissionError('locked')),patch('time.sleep'):
                self.assertFalse(save(p,{'fraction':.2}))
                for name in ['result.json','error.json']:
                    with self.assertRaises(PermissionError):save(Path(d)/name,{})
            self.assertEqual(json.loads(p.read_text())['fraction'],.1)

    @unittest.skipUnless(os.name=='nt','Windows replacement semantics')
    def test_real_windows_reader_lock(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'progress.json';p.write_text('{}')
            handle=p.open('rb')
            release=threading.Timer(.3,handle.close);release.start()
            try:
                self.assertTrue(save(p,{'fraction':.5}))
            finally:
                release.join();handle.close()
            self.assertEqual(json.loads(p.read_text())['fraction'],.5)

if __name__=='__main__':unittest.main()
