import unittest
import numpy as np
from optical_video.core import analyze_trace
from optical_video.evaluate_coverage_stress import schedule
from optical_video.change_points import detect_changes
from morse_table import MORSE_TABLE

class AmbiguousTests(unittest.TestCase):
    def test_black_floor_warning_keeps_unresolved_text(self):
        states,_=schedule([MORSE_TABLE[c] for c in 'イロハニホヘト']);b=np.where(states,220.,0.);b[len(b)//4:]*=.3
        r=analyze_trace(np.arange(len(b))/30,b,30,threshold_method='change_aware')
        self.assertEqual(r['status'],'REVIEW');self.assertTrue(r['exposure_suspicions']);self.assertFalse(r['exposure_changes'])
    def test_clean_signal_not_suspect(self):
        states,_=schedule([MORSE_TABLE[c] for c in 'イロハニホヘト'])
        for floor in (0.,3.,30.):self.assertFalse(detect_changes(np.where(states,220.,floor),30,ambiguous_only=True))

if __name__=='__main__':unittest.main()
