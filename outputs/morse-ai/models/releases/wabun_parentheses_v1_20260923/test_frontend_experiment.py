import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent/'phase8_quality'))
from experimental_frontend import segment_candidate,repair_mode
from warning_localization import audit,summarize
from generate_morse_audio import generate_morse_audio
from morse_table import MORSE_TABLE,REVERSE_TABLE
from policy import render_body

def rows_for(chars):
    return [dict(index=i,pattern=MORSE_TABLE[c],prediction=c,confidence=.99,top_k=[],rule_prediction=c,start_seconds=i,end_seconds=i+.5) for i,c in enumerate(chars)]

class ExperimentTests(unittest.TestCase):
    def test_localization_deletion_is_not_rescued(self):
        text,rows,_=render_body(rows_for('イハ'))
        rows[1]['confidence']=.2
        a=audit('イロハ',text,rows);s=summarize(a)
        self.assertEqual(s['deletions_without_output'],1);self.assertEqual(s['FN'],1);self.assertEqual(s['FP'],1)

    def test_localization_wrong_position_does_not_count(self):
        text,rows,_=render_body(rows_for('イハ'))
        rows[0]['confidence']=.2
        s=summarize(audit('イロ',text,rows))
        self.assertEqual((s['TP'],s['FN'],s['FP']),(0,1,1))

    def test_clean_patterns_and_invalid_audio(self):
        for dot in (.06,.12):
            audio=np.concatenate([generate_morse_audio(c,dot,500,.7,padding=dot*1.5) for c in 'イロハ'])
            rows,_=segment_candidate(audio)
            self.assertEqual([r['pattern'] for r in rows],[MORSE_TABLE[c] for c in 'イロハ'])
        for audio in (np.zeros(16000),np.full(16000,np.nan),np.zeros((16000,2))):
            with self.assertRaises(ValueError):segment_candidate(audio)

    def test_mode_repair_is_audited_and_confidence_gated(self):
        rows=rows_for('（イ）');corrupt=MORSE_TABLE['（']+'.'
        self.assertNotIn(corrupt,REVERSE_TABLE)
        rows[0]['pattern']=corrupt
        text,result,warnings=repair_mode(rows)
        self.assertEqual(text,'A');self.assertEqual(result[0]['observed_pattern'],corrupt)
        self.assertTrue(result[0]['review_reason']);self.assertTrue(warnings)
        self.assertEqual(rows[0]['pattern'],corrupt)
        rows[0]['confidence']=.97
        _,result,_=repair_mode(rows);self.assertNotIn('observed_pattern',result[0])

    def test_mode_repair_rejects_legal_other_code(self):
        rows=rows_for('（イ）');rows[0]['pattern']=MORSE_TABLE['ロ']
        _,result,_=repair_mode(rows)
        self.assertNotIn('observed_pattern',result[0])

if __name__=='__main__':unittest.main()
