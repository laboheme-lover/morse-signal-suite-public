import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import light_source as l
import trace_cache as c
import splitter as s

class LightSourceTests(unittest.TestCase):
 def test_blinking_light_preferred_over_static_lamp(self):
  a=np.full((20,100,160),10,dtype=np.uint8);a[:,10:20,10:20]=255
  a[::2,50:56,80:86]=240
  r=l.locate(a,640,400);x,y,w,h=r['roi']
  self.assertTrue(x<=332<x+w and y<=212<y+h)
 def test_static_scene_rejected(self):
  with self.assertRaises(s.SplitError):l.locate(np.full((20,100,160),100),640,400)
 def test_cache_reuse_and_source_roi_invalidation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'sample.mp4';source.write_bytes(b'original')
   trace=(dict(frames=3),np.array([0.,.03,.06]),np.array([1.,2.,1.]))
   with patch.object(s,'ROOT',root),patch.object(s,'read_trace',return_value=trace) as read:
    m,_,_=c.read_cached(source,[0,0,4,4]);self.assertFalse(m['brightness_cache_hit'])
    m,_,_=c.read_cached(source,[0,0,4,4]);self.assertTrue(m['brightness_cache_hit']);self.assertEqual(read.call_count,1)
    c.read_cached(source,[1,0,4,4]);self.assertEqual(read.call_count,2)
    source.write_bytes(b'changed file')
    c.read_cached(source,[0,0,4,4]);self.assertEqual(read.call_count,3)

 def test_corrupt_cache_rebuilt(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'sample.mp4';source.write_bytes(b'original')
   trace=(dict(frames=3),np.array([0.,.03,.06]),np.array([1.,2.,1.]))
   with patch.object(s,'ROOT',root),patch.object(s,'read_trace',return_value=trace) as read:
    c.read_cached(source,[0,0,4,4])
    next((root/'cache'/'brightness').glob('*.npz')).write_bytes(b'broken')
    m,_,_=c.read_cached(source,[0,0,4,4])
    self.assertFalse(m['brightness_cache_hit']);self.assertEqual(read.call_count,2)
