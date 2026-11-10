import unittest,hashlib
from unittest.mock import patch
import numpy as np
import splitter as s
import optical_header as h
from test_splitter import trace

class HeaderTests(unittest.TestCase):
 def setUp(self):
  self.digest=hashlib.sha256(s.corpus_path('sentence').read_bytes()).hexdigest()
 def test_three_speeds_and_excluded_header(self):
  indices=[2,1];b=s.corpus('sentence')['batches'];cases=[b[i]['cases'][0] for i in indices]
  for ms in (300,450,600):
   text=h.encode(self.digest,ms,indices)
   t,v=trace([dict(pulses=h.pulses(text))]+cases,unit=ms/1000)
   result=h.decode(t,v);self.assertEqual(result['batch_ids'],[b[i]['id'] for i in indices]);self.assertEqual(result['unit_ms'],ms)
   mask=t>=result['body_from'];r=s.detect(t[mask],v[mask],cases,ms/1000)
   self.assertEqual([c['id'] for c in r['clips']],[c['id'] for c in cases])
 def test_checksums_wrong_corpus_and_no_header(self):
  text=h.encode(self.digest,300,[0])
  for invalid in (text[:-1]+('0' if text[-1]!='0' else '1'),h.encode('0'*64,300,[0]),'OB1'):
   with self.assertRaises(s.SplitError):h.parse(invalid)
  t,v=trace(s.corpus('sentence')['batches'][0]['cases'][:2])
  with self.assertRaises(s.SplitError):h.decode(t,v)
 def test_all_65_selection_and_bad_indices(self):
  self.assertEqual(len(h.parse(h.encode(self.digest,600,list(range(65))))['batch_ids']),65)
  for ids in ([],[1,1],[65],[-1]):
   with self.assertRaises(s.SplitError):h.encode(self.digest,300,ids)
 def test_analyze_auto_and_manual_window(self):
  b=s.corpus('sentence')['batches'];cases=[b[1]['cases'][0],b[2]['cases'][0]]
  t,v=trace([dict(pulses=h.pulses(h.encode(self.digest,300,[1,2])))]+cases)
  with patch.object(s,'identity',return_value={}),patch.object(s,'read_trace',return_value=({},t,v)):
   r,_,_=s.analyze('unused',[0,0,2,2],'single65',1,65,600,auto_header=True)
   self.assertEqual(len(r['clips']),2);self.assertEqual(r['unit_ms'],300)
   start=r['clips'][1]['signal_start']-2
   r,_,_=s.analyze('unused',[0,0,2,2],b[2]['id'],1,1,300,profile='sentence',video_start=start)
   self.assertEqual(r['clips'][0]['id'],cases[1]['id'])
 def test_corrupt_pulse_rejected(self):
  t,v=trace([dict(pulses=h.pulses(h.encode(self.digest,300,[1])))]+s.corpus('sentence')['batches'][1]['cases'])
  v[(t>=5)&(t<5.2)]=20
  with self.assertRaises(s.SplitError):h.decode(t,v)
