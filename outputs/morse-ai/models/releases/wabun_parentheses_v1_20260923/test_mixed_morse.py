import unittest
from mixed_morse import normalize_mixed_reference,decode_mixed,INTERNATIONAL
from morse_table import MORSE_TABLE,REVERSE_TABLE

class MixedTests(unittest.TestCase):
    def test_reference(self):
        self.assertEqual(normalize_mixed_reference('HR HR ＜ホレ＞ コクレンノ（WFP）。（415.7ppm）＜ラタ＞'),'コクレンノ（WFP）（415.7PPM）')
        with self.assertRaises(ValueError):normalize_mixed_reference('IPCC')

    def test_mode_and_decimal(self):
        patterns=[MORSE_TABLE['シ'],MORSE_TABLE['（']]+[INTERNATIONAL[c] for c in 'WFP1.2']+[MORSE_TABLE['）'],MORSE_TABLE['シ']]
        rows=[dict(pattern=p,prediction=REVERSE_TABLE[p],rule_prediction=REVERSE_TABLE[p]) for p in patterns]
        self.assertEqual(decode_mixed(rows),('シ（WFP1.2）シ','シ（WFP1.2）シ'))
        rows[2]['prediction']='ヘ'
        cnn,rule=decode_mixed(rows)
        self.assertEqual(cnn,'シ（EFP1.2）シ')
        self.assertEqual(rule,'シ（WFP1.2）シ')

    def test_unbalanced(self):
        with self.assertRaises(ValueError):normalize_mixed_reference('（WFP')
        with self.assertRaises(ValueError):decode_mixed([dict(pattern=MORSE_TABLE['）'],prediction='）',rule_prediction='）')])
