import unittest,json,sys
from pathlib import Path
import splitter as s
sys.path.insert(0,str(s.ROOT))
from prepare_sentence_corpus import first_sentence
class SentenceTests(unittest.TestCase):
 def test_catalog(self):
  old=s.corpus();new=s.corpus('sentence');self.assertEqual(len(new['batches']),65);self.assertEqual(new['batches'][0],old['batches'][0])
  self.assertEqual(sum(b['id'].startswith('original44') for b in new['batches']),44)
  self.assertEqual(sum(b['id'].startswith('original20') for b in new['batches']),20)
  ids=[b['id'] for b in new['batches']];self.assertEqual(len(ids),len(set(ids)))
  for b in new['batches'][1:]:
   self.assertEqual(len(b['cases']),1);c=b['cases'][0];self.assertTrue(c['labels']);self.assertNotIn('□',c['labels']);self.assertEqual(c['units'],sum(u for on,u in c['pulses']))
   self.assertAlmostEqual(b['duration_seconds']['300'],c['units']*.3+20)
 def test_quotes_are_not_end_of_sentence(self):
  self.assertEqual(first_sentence('クスリ「レカネマブ」ヲツカイマス。ツギ。')[0],'クスリ「レカネマブ」ヲツカイマス。')
  self.assertEqual(first_sentence('デス」ツギ')[0],'デス」')
 def test_telegram_wrapped_addresses(self):
  cases={b['cases'][0]['parent_id']:b['cases'][0] for b in s.corpus('sentence')['batches'][1:]}
  self.assertTrue(cases['original20_no015']['input'].startswith('テツガク'))
  self.assertTrue(cases['original20_no019']['input'].startswith('コクサイ'))
  for key,c in cases.items():
   if key.startswith('original20'):
    self.assertGreaterEqual(len(c['removed_telegram_header_address_name']),2)
    if '」' in c['input']:self.assertTrue(c['input'].endswith('」'))
 def test_assets_match_and_old_corpus_retained(self):
  self.assertEqual(s.corpus_path('sentence').read_bytes(),(s.ROOT.parent/'android-morse/opticaltest/src/main/assets/batches.json').read_bytes())
  self.assertEqual(s.corpus()['gap_seconds'],10)
if __name__=='__main__':unittest.main()
