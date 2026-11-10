import unittest,tempfile,json
from pathlib import Path
import numpy as np
import cv2
import splitter as s
from recovery import detect_candidates
from test_splitter import trace

class RecoveryTests(unittest.TestCase):
 def setUp(self):self.cases=s.corpus()['batches'][0]['cases'][:3]
 def test_count_and_unassigned_references(self):
  t,v=trace(self.cases);r=detect_candidates(t,v,self.cases,.3)
  self.assertEqual(len(r['clips']),3);self.assertEqual(r['quality'],'REVIEW')
  self.assertTrue(all(c['labels'] is None for c in r['clips']))
 def test_anomaly_inside_case_does_not_abort_following_cases(self):
  t,v=trace(self.cases);keep=~((t>5.05)&(t<5.25));r=detect_candidates(t[keep],v[keep],self.cases,.3)
  self.assertEqual(len(r['clips']),3);self.assertGreater(r['clips'][0]['timing_anomaly_count'],0)
  self.assertEqual(r['clips'][1]['timing_anomaly_count'],0)
 def test_timestamp_hole_is_not_a_pause(self):
  t,v=trace(self.cases);keep=~((t>10)&(t<28));r=detect_candidates(t[keep],v[keep],self.cases,.3)
  self.assertTrue(any(not p['usable_boundary'] for p in r['pauses']))
  self.assertLess(len(r['clips']),3)
 def test_mismatch_remains_unassigned(self):
  t,v=trace(self.cases);r=detect_candidates(t,v,self.cases[:2],.3)
  self.assertEqual(len(r['clips']),3);self.assertEqual(r['expected_count'],2)
  self.assertTrue(all(c['labels'] is None for c in r['clips']))
 def test_low_contrast_still_rejected(self):
  t,v=trace(self.cases,low=100,high=109)
  with self.assertRaises(s.SplitError):detect_candidates(t,v,self.cases,.3)
 def test_invalid_time_rejected(self):
  t,v=trace(self.cases);t[3]=t[2]
  with self.assertRaises(s.SplitError):detect_candidates(t,v,self.cases,.3)
 def test_review_export_requires_acknowledgement(self):
  t,v=trace(self.cases);r=detect_candidates(t,v,self.cases,.3)
  with self.assertRaisesRegex(s.SplitError,'明示的'):s.export(r,'unused')
 def test_negative_first_timestamp_only(self):
  t=np.array([-.0992888889,.033,.066,.099,.4])
  fixed,log=s.correct_initial_timestamp(t,30.3069)
  self.assertEqual(fixed[0],0);self.assertEqual(len(log),1)
  np.testing.assert_array_equal(fixed[1:],t[1:])
  self.assertGreater(np.diff(fixed).max(),.12)
 def test_no_correction_to_normal_timestamps(self):
  t=np.arange(10)/30
  fixed,log=s.correct_initial_timestamp(t,30)
  np.testing.assert_array_equal(t,fixed);self.assertEqual(log,[])
 def test_unexplained_negative_timestamp_rejected(self):
  with self.assertRaises(s.SplitError):s.correct_initial_timestamp([-.1,.5,.533],30)
 def test_candidate_export_skips_requested_case_without_label_files(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);video=root/'input.mp4';t,v=trace(self.cases)
   writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),30,(64,48))
   for value in v:writer.write(np.full((48,64,3),round(value),dtype=np.uint8))
   writer.release()
   result,_,_=s.analyze(video,[0,0,64,48],'single65',1,3,300,mode='pause_candidates')
   target=s.export(result,root/'candidates',allow_review=True,skip_ids=['candidate_002'])
   report=json.loads((target/'split_manifest.json').read_text(encoding='utf-8'))
   self.assertEqual([c['id'] for c in report['outputs']],['candidate_001','candidate_003'])
   self.assertEqual([c['id'] for c in report['skipped']],['candidate_002'])
   self.assertEqual(len(list(target.glob('*.txt'))),0)
   self.assertEqual(report['quality'],'REVIEW')
if __name__=='__main__':unittest.main(verbosity=2)
