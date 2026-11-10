import unittest
import numpy as np
from optical_video.change_points import detect_changes
from optical_video.core import analyze_trace
from optical_video.evaluate_coverage_stress import schedule
from morse_table import MORSE_TABLE

class ChangeTests(unittest.TestCase):
    def test_recover_mid_pulse_change_and_flag(self):
        text='カモメノイロハ012';states,_=schedule([MORSE_TABLE[c] for c in text],12,30)
        signal=np.where(states,220.,30.);boundary=len(signal)//2;signal[boundary:]*=.3
        r=analyze_trace(np.arange(len(signal))/30,signal,30,threshold_method='change_aware')
        self.assertEqual(r['text'],text);self.assertEqual(r['status'],'REVIEW');self.assertTrue(r['exposure_changes'])
        self.assertLessEqual(abs(r['exposure_changes'][0]['time_seconds']-boundary/30),1/30)
    def test_clean_pulses_and_slow_drift_not_abrupt(self):
        states,_=schedule([MORSE_TABLE[c] for c in 'イロハニホヘトチリヌルヲワカヨ']);signal=np.where(states,220.,30.)
        self.assertFalse(detect_changes(signal,30))
        self.assertFalse(detect_changes(signal*np.linspace(1,.3,len(signal)),30))
    def test_absolute_time_preserved(self):
        states,_=schedule([MORSE_TABLE[c] for c in 'カモメノイロハ012'],12,30)
        signal=np.where(states,220.,30.);signal[len(signal)//2:]*=.3
        r=analyze_trace(np.arange(len(signal))/30+100,signal,30,threshold_method='change_aware')
        self.assertGreater(r['exposure_changes'][0]['time_seconds'],100)
    def test_ui_new_mode(self):
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'video_app.py'),default_timeout=30).run()
        app.checkbox[0].check().run();app.selectbox[0].select('変化点対応（実験的）').run();app.button[0].click().run()
        from optical_video.testing import finish_ui_job
        finish_ui_job(app)
        self.assertFalse(app.exception);self.assertEqual(app.text_area[0].value,'イWFPロ')

if __name__=='__main__':unittest.main()
