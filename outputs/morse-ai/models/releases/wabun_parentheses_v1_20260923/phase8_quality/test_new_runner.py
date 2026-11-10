import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from evaluate_new import prepare,select_body,aggregate
from evaluate_recording import edit_alignment

class RunnerTests(unittest.TestCase):
    def test_protocol_requires_unambiguous_framing(self):
        def rows(patterns):return [dict(pattern=p,start_seconds=i,end_seconds=i+.5) for i,p in enumerate(patterns)]
        self.assertEqual(len(select_body(rows(['-..---','.-','...-.']),{'mode':'protocol'})),1)
        self.assertEqual(len(select_body(rows(['....','.-.','....','.-.','-...-','.-','.-.-.']),{'mode':'protocol'})),1)
        for patterns in (['.-'],['-..---','-..---','.-','...-.'],['-..---','...-.']):
            with self.assertRaises(ValueError):select_body(rows(patterns),{'mode':'protocol'})
    def test_window_never_cuts_character(self):
        rows=[dict(start_seconds=1,end_seconds=2),dict(start_seconds=3,end_seconds=4)]
        self.assertEqual(select_body(rows,{'mode':'window','start_seconds':.5,'end_seconds':2.5}),rows[:1])
        with self.assertRaises(ValueError):select_body(rows,{'mode':'window','start_seconds':1.5,'end_seconds':4.5})
        with self.assertRaises(ValueError):select_body(rows,{'mode':'window','start_seconds':5,'end_seconds':6})
    def test_intake_modes_and_safe_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sf.write(root/'x.wav',np.zeros(16000),16000);(root/'x.txt').write_text('アイ',encoding='utf-8')
            m={'recordings':[dict(id='x',audio='x.wav',reference='x.txt',group_id='g',declared_unseen=False,body={'mode':'full'})]}
            original=copy.deepcopy(m)
            audit=prepare(m,root,rehearsal=True)
            self.assertFalse(audit['recordings'][0]['declared_unseen']);self.assertEqual(m,original)
            with self.assertRaises(ValueError):prepare(m,root)
            m['recordings'][0]['id']='../escape'
            with self.assertRaises(ValueError):prepare(m,root,rehearsal=True)
            m['recordings'][0]['id']='x';m['recordings'][0]['body']={}
            with self.assertRaises(ValueError):prepare(m,root,rehearsal=True)
    def test_failure_stays_in_denominator(self):
        ok,_=edit_alignment('アイ','アイ');bad,_=edit_alignment('ウエオ','')
        rows=[dict(ok,model='M1',status='OK',exact=1,review_segments=0),dict(bad,model='M1',status='FAILED',exact=0,review_segments=0)]
        result=aggregate(rows)[0]
        self.assertEqual((result['reference_units'],result['edit_distance'],result['failures']),(5,3,1))
        self.assertEqual(result['cer'],.6)

if __name__=='__main__':unittest.main()
