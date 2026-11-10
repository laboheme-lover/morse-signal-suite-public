import unittest
import numpy as np,torch
from dataset import augment,features,tensorize,CONDITIONS
from model import MODELS

class PipelineTests(unittest.TestCase):
 def setUp(self):
  self.frames=np.full((90,64,64),12,np.uint8);self.frames[15:24,25:39,25:39]=210;self.frames[33:60,25:39,25:39]=210;self.times=np.arange(90)/30
 def test_every_condition_is_reproducible_and_finite(self):
  for name in CONDITIONS:
   a,p=augment(self.frames,self.times,name,42);b,q=augment(self.frames,self.times,name,42)
   np.testing.assert_array_equal(a,b);self.assertEqual(p,q)
   x=tensorize(features(a),len(a)/30);self.assertEqual(x.shape,(5,256));self.assertTrue(np.isfinite(x).all())
 def test_speed_changes_duration(self):
  fast,_=augment(self.frames,self.times,'fast',42);slow,_=augment(self.frames,self.times,'slow',42)
  self.assertLess(len(fast),len(slow))
 def test_augmentation_does_not_modify_source(self):
  original=self.frames.copy();augment(self.frames,self.times,'mixed',42);np.testing.assert_array_equal(original,self.frames)
 def test_models_have_valid_gradients(self):
  torch.set_num_threads(2)
  for cls in MODELS.values():
   m=cls();y=m(torch.randn(3,5,256));self.assertEqual(tuple(y.shape),(3,65));y.square().mean().backward()
   self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters()))

if __name__=='__main__':unittest.main()
