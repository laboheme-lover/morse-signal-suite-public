from pathlib import Path
import tempfile,unittest
import soundfile as sf
import numpy as np
from intake import validate,digest

class IntakeTests(unittest.TestCase):
    def test_empty_is_not_complete(self):
        self.assertEqual(validate({'recordings':[]},Path('.'),set(),set())['status'],'NEEDS_REVIEW')
    def test_missing_and_declared_exposure(self):
        for row in ({},{'id':'a','audio':'x.wav','reference':'x.txt','group_id':'s','declared_unseen':False}):
            self.assertEqual(validate({'recordings':[row]},Path('.'),set(),set())['status'],'NEEDS_REVIEW')
    def test_new_and_duplicate_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sf.write(root/'x.wav',np.sin(np.arange(1600)*2*np.pi*600/16000)*0.1,16000);(root/'x.txt').write_text('アイウ',encoding='utf-8')
            row={'id':'a','audio':'x.wav','reference':'x.txt','group_id':'s','declared_unseen':True}
            self.assertEqual(validate({'recordings':[row]},root,set(),set())['status'],'PASS')
            for known_audio,known_ref in (({digest(root/'x.wav')},set()),(set(),{'アイウ'})):
                self.assertEqual(validate({'recordings':[row]},root,known_audio,known_ref)['status'],'NEEDS_REVIEW')
            self.assertEqual(validate({'recordings':[row,row]},root,set(),set())['status'],'NEEDS_REVIEW')
            (root/'x.wav').write_bytes(b'not an audio file')
            self.assertEqual(validate({'recordings':[row]},root,set(),set())['status'],'NEEDS_REVIEW')

if __name__=='__main__':unittest.main()
