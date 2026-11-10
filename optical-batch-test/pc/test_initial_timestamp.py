import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import splitter as s

class InitialTimestampTests(unittest.TestCase):
 def response(self, pts):
  return SimpleNamespace(returncode=0,stderr='\n'.join(f'n: {i} pts: {i} pts_time:{t}' for i,t in enumerate(pts)))
 def test_confirmed_first_frame_repaired(self):
  raw=[.0988777778,.0329888889,.0659777778]
  with patch.object(s.subprocess,'run',return_value=self.response([0,.0329889,.0659778])):
   fixed,log=s.verify_initial_timestamp('input.mp4',raw,30.31)
  self.assertEqual(fixed[0],0)
  np.testing.assert_array_equal(fixed[1:],raw[1:])
  self.assertEqual(len(log),1)
 def test_disagreement_rejected(self):
  with patch.object(s.subprocess,'run',return_value=self.response([0,.04,.08])):
   with self.assertRaises(s.SplitError):s.verify_initial_timestamp('input.mp4',[.099,.033,.066],30)
 def test_genuine_duplicate_rejected(self):
  with patch.object(s.subprocess,'run',return_value=self.response([0,0,.033])):
   with self.assertRaises(s.SplitError):s.verify_initial_timestamp('input.mp4',[0,0,.033],30)
 def test_failed_decoder_rejected(self):
  with patch.object(s.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr='')):
   with self.assertRaises(s.SplitError):s.verify_initial_timestamp('input.mp4',[.099,.033,.066],30)

class ReadTraceTimestampTests(unittest.TestCase):
 def test_real_read_path_applies_verified_correction(self):
  class Capture:
   i=-1
   def read(self):
    self.i+=1
    return (True,np.zeros((4,4,3),dtype=np.uint8)) if self.i<4 else (False,None)
   def get(self,key):return [99,33,66,99][self.i]
   def release(self):pass
  with patch.object(s,'info',return_value=dict(fps=30,width=4,height=4,frames=4)),patch.object(s.cv2,'VideoCapture',return_value=Capture()),patch.object(s,'verify_initial_timestamp',return_value=(np.array([0,.033,.066]),[{'frame':0}])):
   meta,t,v=s.read_trace('input.mp4',[0,0,4,4])
  np.testing.assert_allclose(t,[0,.033,.066,.099])
  self.assertEqual(meta['timestamp_corrections'],[{'frame':0}])
 def test_later_backward_time_still_rejected(self):
  class Capture:
   i=-1
   def read(self):self.i+=1;return True,np.zeros((4,4,3),dtype=np.uint8)
   def get(self,key):return [0,33,66,50][self.i]
   def release(self):pass
  with patch.object(s,'info',return_value=dict(fps=30,width=4,height=4,frames=4)),patch.object(s.cv2,'VideoCapture',return_value=Capture()):
   with self.assertRaises(s.SplitError):s.read_trace('input.mp4',[0,0,4,4])
