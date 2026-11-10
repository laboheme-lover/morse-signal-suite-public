"""Boundary and numerical-regression checks for disk-streamed PC video."""
import tempfile, unittest
from pathlib import Path
import cv2
import numpy as np
from desktop_video import validate_metadata, MAX_BYTES
from flexible_roi import extract_flexible
from predict import extract_features

class DesktopVideoTests(unittest.TestCase):
    def test_limits(self):
        validate_metadata(MAX_BYTES, {'duration':1200})
        for size, duration in [(MAX_BYTES+1,1200),(1,1200.01),(0,1),(1,float('nan'))]:
            with self.assertRaises(ValueError):validate_metadata(size,{'duration':duration})

    def test_exact_legacy_features(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.mp4'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),30,(160,160))
            self.assertTrue(writer.isOpened())
            for i in range(90):
                frame=np.zeros((160,160,3),np.uint8)
                frame[60:100,60:100]=220 if i%18<9 else 10
                writer.write(frame)
            writer.release()
            a,b,_=extract_features(path,[60,60,40,40])
            x,y,meta=extract_flexible(path,[60,60,40,40])
            np.testing.assert_array_equal(a,x)
            np.testing.assert_array_equal(b,y)
            self.assertEqual(meta['roi_adapter'],'legacy_40px')
            self.assertEqual(y.dtype,np.float32)

if __name__=='__main__':unittest.main()
