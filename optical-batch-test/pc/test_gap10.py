import unittest
from test_splitter import trace
import splitter as s
from recovery import detect_candidates
class Gap10Tests(unittest.TestCase):
 def test_all_65_at_all_speeds(self):
  cases=s.corpus('sentence')['batches'][0]['cases']
  for unit in (.3,.45,.6):
   t,v=trace(cases,unit,gap=10)
   self.assertEqual(len(s.detect(t,v,cases,unit)['clips']),65)
   self.assertEqual(len(detect_candidates(t,v,cases,unit)['clips']),65)
 def test_old_20_second_pause_is_not_certified(self):
  cases=s.corpus()['batches'][0]['cases'][:3];t,v=trace(cases,gap=20)
  with self.assertRaisesRegex(s.SplitError,'休止'):s.detect(t,v,cases,.3)
if __name__=='__main__':unittest.main()
