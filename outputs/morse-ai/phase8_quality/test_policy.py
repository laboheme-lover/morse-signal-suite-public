import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from policy import normalize_reference,render_body,interpret

class PolicyTests(unittest.TestCase):
    def test_decimal_context(self):
        self.assertEqual(normalize_reference('０．６ド、1.5ド。'),'0テン6ト゛1テン5ト゛')
        self.assertEqual(normalize_reference('（415.7ppm）'),'415.7PPM')
        self.assertEqual(normalize_reference('60cm？'),'60CM?')
    def test_reference_rejects_broken_controls(self):
        for text in ('(A','A)','((A))'):
            with self.assertRaises(ValueError):normalize_reference(text)
    def test_unknown_not_replaced_with_high_confidence_guess(self):
        row=dict(index=90,pattern='..--..',prediction='ヱ',confidence=.985,top_k=[],rule_prediction='?')
        text,rows,_=render_body([row])
        self.assertEqual(text,'□');self.assertEqual(rows[0]['prediction'],'ヱ')
        self.assertTrue(rows[0]['unsupported_code']);self.assertTrue(rows[0]['review_reason'])
    def test_valid_disagreement_keeps_cnn(self):
        row=dict(index=0,pattern='.-',prediction='ハ',top_k=[],rule_prediction='イ')
        text,rows,_=render_body([row]);self.assertEqual(text,'ハ');self.assertTrue(rows[0]['disagrees_with_rule'])
    def test_controls_hidden_and_flagged_if_malformed(self):
        rows=[dict(index=i,pattern=p,prediction=c,top_k=[]) for i,(p,c) in enumerate([('-.--.-','（'),('.--','ヤ'),('.-..-.','）')])]
        self.assertEqual(interpret(rows),[]);self.assertEqual(''.join(r['text_prediction'] for r in rows),'W')
        interpret([rows[-1]]);self.assertTrue(rows[-1]['review_reason'])

if __name__=='__main__':unittest.main()
