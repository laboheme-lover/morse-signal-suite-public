import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
import video_compression as vc
class CompressionTests(unittest.TestCase):
 def test_web_limits(self):
  m=dict(duration=300,width=1920,height=1080,fps=60)
  self.assertEqual(vc.web_reasons(m,300*1024**2),[])
  self.assertTrue(vc.web_reasons({**m,'duration':301},1))
  self.assertTrue(vc.web_reasons(m,300*1024**2+1))
 def test_export_preserves_source_and_timing(self):
  try:vc.ffmpeg_path()
  except ValueError:self.skipTest("FFmpeg is not installed")
  with tempfile.TemporaryDirectory() as folder:
   src=Path(folder)/'source.mp4'
   writer=cv2.VideoWriter(str(src),cv2.VideoWriter_fourcc(*'mp4v'),30,(160,160))
   for i in range(90):writer.write(np.full((160,160,3),255 if i%9<3 else 0,np.uint8))
   writer.release();original=src.read_bytes()
   job=vc.start(src,folder);job['process'].wait(timeout=30);r=vc.finish(job)
   self.assertEqual(r['frames'],90);self.assertEqual(r['timestamp_max_delta_seconds'],0)
   self.assertEqual(src.read_bytes(),original);self.assertNotEqual(r['path'],str(src))
   self.assertTrue(Path(r['path']).exists());self.assertFalse(job['partial'].exists())
   job=vc.start(src,folder);vc.cancel(job);self.assertFalse(job['dest'].exists());self.assertFalse(job['partial'].exists())
if __name__=='__main__':unittest.main()
