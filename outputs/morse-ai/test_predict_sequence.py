import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from generate_morse_audio import generate_morse_audio
from predict_sequence import SequencePredictor,interpret_segments,save_sequence
from morse_table import MORSE_TABLE,REVERSE_TABLE


def sample(text,frequency=700):
    return np.concatenate([generate_morse_audio(c,.1,frequency,.7,padding=.15) for c in text])


class SequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1);cls.predictor=SequencePredictor()

    def test_end_to_end(self):
        r=self.predictor.predict_audio(sample('イロハ'),include_details=True)
        self.assertEqual(r['text'],'イロハ');self.assertEqual(r['segment_count'],3)
        for a,b in zip(r['segments'],r['segments'][1:]):self.assertLess(a['end_seconds'],b['start_seconds'])
        for s in r['segments']:
            self.assertEqual(len(s['top_k']),3);self.assertEqual(s['mel'].shape[0],64)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'sequence';save_sequence(r,out)
            self.assertTrue((out/'details/00000.wav').is_file())
            self.assertTrue((out/'sequence.json').is_file())
            with self.assertRaises(FileExistsError):save_sequence(r,out)

    def test_mixed_mode_uses_cnn_prediction(self):
        patterns=[MORSE_TABLE[c] for c in '（ヤチツ）イ']
        rows=[dict(index=i,pattern=p,prediction=REVERSE_TABLE[p],top_k=[]) for i,p in enumerate(patterns)]
        self.assertEqual(interpret_segments(rows),[])
        self.assertEqual(''.join(r['text_prediction'] for r in rows),'WFPイ')
        rows[1]['prediction']='ヘ';interpret_segments(rows)
        self.assertEqual(rows[1]['text_prediction'],'E')
        self.assertEqual(rows[1]['rule_prediction'],'W')

    def test_unclosed_and_prosigns(self):
        rows=[dict(index=0,pattern=MORSE_TABLE['（'],prediction='（',top_k=[])]
        self.assertTrue(interpret_segments(rows))
        rows=[dict(index=0,pattern='-..---',prediction='イ',top_k=[])]
        interpret_segments(rows);self.assertEqual(rows[0]['text_prediction'],'')
        self.assertEqual(rows[0]['prediction'],'イ');self.assertEqual(rows[0]['kind'],'prosign')

    def test_frequency_and_invalid_options(self):
        r=self.predictor.predict_audio(sample('イロハ',3272),frequency_hz=3272,target_frequency_hz=700)
        self.assertEqual(r['text'],'イロハ');self.assertEqual(r['carrier_processing']['target_hz'],700)
        for kwargs in [{'top_k':0},{'low_confidence':2},{'character_gap_seconds':-1}]:
            with self.assertRaises(ValueError):self.predictor.predict_audio(sample('イロハ'),**kwargs)
        with self.assertRaises(ValueError):self.predictor.predict_audio(np.zeros(16000))
