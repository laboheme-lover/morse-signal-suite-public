import unittest
import numpy as np
from optical_video.diagnostics import missed_signal_windows
from optical_video.core import analyze_trace
from optical_video.evaluate_coverage_stress import schedule
from morse_table import MORSE_TABLE

class DiagnosticsTests(unittest.TestCase):
    def test_hidden_flashes_warn_without_modifying_inputs(self):
        t=np.arange(600)/30;s=np.where((np.arange(600)//9)%2,50.,10.);states=np.zeros(600,dtype=bool)
        before=s.copy();r=missed_signal_windows(t,s,states,30,.3,150,190)
        self.assertTrue(r);np.testing.assert_array_equal(before,s);self.assertFalse(states.any())
        self.assertEqual(len(r),1)
    def test_quiet_and_detected_flashes_are_not_missing(self):
        t=np.arange(600)/30
        self.assertFalse(missed_signal_windows(t,np.full(600,30.),np.zeros(600,dtype=bool),30,.3,150,190))
        s=np.where((np.arange(600)//9)%2,220.,30.)
        self.assertFalse(missed_signal_windows(t,s,s>150,30,.3,150,190))
    def test_exposure_warning_preserves_partial_text(self):
        states,_=schedule([MORSE_TABLE[c] for c in 'イロハニホヘトチリヌルヲワカヨ'])
        signal=np.where(states,220.,30.);signal[len(signal)//2:]*=.3
        r=analyze_trace(np.arange(len(signal))/30,signal,30)
        self.assertEqual(r['status'],'REVIEW');self.assertTrue(r['diagnostics'])
        self.assertTrue(r['text']);self.assertNotEqual(r['text'],'イロハニホヘトチリヌルヲワカヨ')

if __name__=='__main__':unittest.main()
