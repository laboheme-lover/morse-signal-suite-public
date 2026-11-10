"""Cloud boundary checks and fresh-process entry-point smoke tests."""
import json,sys,tempfile,unittest,subprocess,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud'))
import runtime

class CloudTests(unittest.TestCase):
    def probe(self,duration=5,width=320,height=240,fps='30/1'):
        return subprocess.CompletedProcess([],0,json.dumps({'format':{'duration':str(duration)},'streams':[{'codec_type':'video','width':width,'height':height,'avg_frame_rate':fps}]}).encode(),b'')
    def test_limits_and_invalid_media(self):
        for kwargs in [{'duration':301},{'duration':float('nan')},{'width':4096,'height':2160},{'fps':'120/1'},{'fps':'0/0'}]:
            with patch('runtime.shutil.which',return_value='ffprobe'),patch('runtime.subprocess.run',return_value=self.probe(**kwargs)):
                with self.assertRaises(ValueError):runtime.inspect_media('unused.mp4','video')
    def test_duration_limits_by_kind(self):
        for kind,seconds,accepted in [('video',120,True),('video',300,True),('video',300.01,False),('audio',120,True),('audio',300,True),('audio',300.01,False)]:
            data=json.loads(self.probe(duration=seconds).stdout)
            data['streams'][0]['codec_type']=kind
            probe=subprocess.CompletedProcess([],0,json.dumps(data).encode(),b'')
            with self.subTest(kind=kind,seconds=seconds), patch('runtime.shutil.which',return_value='ffprobe'),patch('runtime.subprocess.run',return_value=probe):
                if accepted:runtime.inspect_media('unused',kind)
                else:
                    with self.assertRaises(ValueError):runtime.inspect_media('unused',kind)
    def test_upload_size_by_kind(self):
        class Oversized:
            def __len__(self):return 300*1024*1024+1
        with self.assertRaisesRegex(ValueError,'300 MB'):
            runtime.store_upload(Oversized(), '.mp4', {}, 'video')
        class AudioOversized:
            def __len__(self):return 50*1024*1024+1
        with self.assertRaisesRegex(ValueError,'50 MB'):
            runtime.store_upload(AudioOversized(), '.wav', {}, 'audio')
        # A real >50 MB payload must pass the video gate and reach media validation.
        with patch('runtime.inspect_media',side_effect=ValueError('probe reached')):
            with self.assertRaisesRegex(ValueError,'probe reached'):
                runtime.store_upload(bytes(51*1024*1024), '.mp4', {}, 'video')
        self.assertEqual(runtime.VIDEO_MAX_BYTES,300*1024*1024)
    def test_session_isolation_and_cleanup(self):
        a={};b={}
        try:
            with patch('runtime.inspect_media',return_value={}),patch('runtime.threading.Timer'):
                x=runtime.store_upload(b'test','.mp4',a,'video');y=runtime.store_upload(b'test','.mp4',b,'video')
                self.assertNotEqual(x,y)
                self.assertEqual(runtime.store_upload(b'test','.mp4',a,'video'),x)
                runtime.store_upload(b'changed','.mp4',a,'video')
                self.assertFalse(Path(x).exists());self.assertTrue(Path(y).exists())
                with self.assertRaises(ValueError):runtime.store_upload(b'', '.mp4',a,'video')
        finally:
            for state in [a,b]:
                for value in state.values():shutil.rmtree(Path(value['path']).parent,ignore_errors=True)
    def test_failed_probe_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'upload';p.mkdir()
            with patch('runtime.tempfile.mkdtemp',return_value=str(p)),patch('runtime.inspect_media',side_effect=ValueError('invalid')):
                with self.assertRaises(ValueError):runtime.store_upload(b'bad','.mp4',{},'video')
            self.assertFalse(p.exists())
    def test_entry_points(self):
        code='''from streamlit.testing.v1 import AppTest
import sys
at=AppTest.from_file(sys.argv[1],default_timeout=120).run()
assert not at.exception,str(at.exception)
assert at.title
if 'optical' in sys.argv[1]:
 assert not at.text_input, 'Public app must not expose server file paths'
 assert len(at.get('file_uploader'))==1
else:
 assert any('クラウド' in str(x.value) for x in at.caption)
'''
        for name in ['audio_app.py','optical_app.py']:
            subprocess.run([sys.executable,'-c',code,str(ROOT/'cloud'/name)],cwd=ROOT,check=True,timeout=150)

if __name__=='__main__':unittest.main()
