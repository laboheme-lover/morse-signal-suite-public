import unittest
import numpy as np
from optical_video.core import analyze_trace
from optical_video.adaptive import local_thresholds
from optical_video.evaluate_coverage_stress import schedule
from morse_table import MORSE_TABLE

class AdaptiveTests(unittest.TestCase):
    def test_clean_and_gradual_exposure(self):
        text='イロハニホヘトチリヌルヲワカヨ';states,_=schedule([MORSE_TABLE[c] for c in text])
        signal=np.where(states,220.,30.);t=np.arange(len(signal))/30
        self.assertEqual(analyze_trace(t,signal,30,threshold_method='adaptive')['text'],text)
        signal*=np.linspace(1,.3,len(signal))
        r=analyze_trace(t,signal,30,threshold_method='adaptive')
        self.assertEqual(r['text'],text)
        self.assertLess(r['trace'][-50]['threshold_on'],r['trace'][50]['threshold_on'])
    def test_flat_local_windows_keep_global_threshold(self):
        off,on,valid=local_thresholds(np.full(100,30.),30,3,90,150)
        self.assertFalse(valid.any());self.assertTrue((off==90).all());self.assertTrue((on==150).all())
    def test_invalid_options(self):
        states,_=schedule(['.-','.-']);b=np.where(states,220.,30.);t=np.arange(len(b))/30
        for options in ({'threshold_method':'unknown'},{'threshold_method':'adaptive','thresholds':(90,150)},{'threshold_method':'adaptive','adaptive_window_seconds':0}):
            with self.assertRaises(ValueError):analyze_trace(t,b,30,**options)
    def test_adaptive_ui_and_cache_invalidation(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'video_app.py'),default_timeout=30).run()
        app.checkbox[0].check().run();app.button[0].click().run()
        from optical_video.testing import finish_ui_job
        finish_ui_job(app)
        self.assertEqual(app.text_area[0].value,'イWFPロ')
        app.selectbox[0].select('適応しきい値（実験的）').run()
        self.assertEqual(len(app.text_area),0)
        app.button[0].click().run();finish_ui_job(app);self.assertFalse(app.exception)
        self.assertEqual(app.text_area[0].value,'イWFPロ')

if __name__=='__main__':unittest.main()
