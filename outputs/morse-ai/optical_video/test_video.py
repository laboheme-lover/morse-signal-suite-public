from pathlib import Path
import json,tempfile,unittest
import numpy as np
from optical_video.core import analyze_video,analyze_trace,decode,INTERNATIONAL_REVERSE
from optical_video.synthetic import generate
from morse_table import MORSE_TABLE

class VideoTests(unittest.TestCase):
    def test_real_encoded_formats_timing_noise_and_inverse(self):
        patterns=[MORSE_TABLE[c] for c in 'イロハ']
        with tempfile.TemporaryDirectory() as td:
            for fps,ext,noise,invert in [(30,'.avi',0,False),(60,'.avi',12,False),(30,'.mp4',5,True)]:
                path=Path(td)/('点滅 日本語'+ext)
                truth=generate(path,patterns,fps,9,noise,invert)
                result=analyze_video(path,(60,40,40,40),invert=invert)
                self.assertEqual(result['text'],'イロハ');self.assertEqual(result['status'],'OK')
                pulses=[r for r in result['events'] if r['on']]
                self.assertEqual(len(pulses),len(truth['events']))
                for got,want in zip(pulses,truth['events']):
                    self.assertLessEqual(abs(got['start_seconds']-want['start_seconds']),1/fps+1e-7)
                    self.assertLessEqual(abs(got['end_seconds']-want['end_seconds']),1/fps+1e-7)
                with self.assertRaises(ValueError):analyze_video(path,(0,0,10,10))
                with self.assertRaises(ValueError):analyze_video(path,(-1,0,10,10))
    def test_mixed_table_and_warnings(self):
        from mixed_morse import INTERNATIONAL_REVERSE as existing
        self.assertEqual(INTERNATIONAL_REVERSE,existing)
        def rows(patterns):return [dict(pattern=p,review_reason='') for p in patterns]
        r=rows([MORSE_TABLE['イ'],MORSE_TABLE['（'],'.--','..-.','.--.','.-.-.-',MORSE_TABLE['）'],MORSE_TABLE['ロ']])
        text,warnings=decode(r);self.assertEqual(text,'イWFP.ロ');self.assertFalse(warnings)
        self.assertEqual(decode(rows(['........']))[0],'□')
        self.assertTrue(decode(rows([MORSE_TABLE['（'],'.--']))[1])
        self.assertTrue(decode(rows([MORSE_TABLE['）']]))[1])
    def test_low_fps_uniform_and_ambiguous(self):
        times=np.arange(90)/30
        with self.assertRaises(ValueError):analyze_trace(times,np.full(90,100),30)
        brightness=np.full(90,30.);brightness[10:13]=220;brightness[16:25]=220
        r=analyze_trace(times,brightness,30,dot_seconds=.1)
        self.assertEqual(r['text'],'');self.assertTrue(r['candidate_text']);self.assertEqual(r['status'],'REVIEW')
        brightness=np.full(90,30.);brightness[10:19]=220;brightness[28:37]=220
        with self.assertRaises(ValueError):analyze_trace(times,brightness,30)
        self.assertTrue(analyze_trace(times,brightness,30,dot_seconds=.3)['text'])
    def test_clipped_pulse_and_threshold_validation(self):
        times=np.arange(90)/30;brightness=np.full(90,30.);brightness[:9]=220;brightness[18:45]=220
        r=analyze_trace(times,brightness,30,dot_seconds=.3)
        self.assertEqual(r['characters'][0]['text'],'□');self.assertTrue(r['characters'][0]['review_reason'])
        with self.assertRaises(ValueError):analyze_trace(times,brightness,30,thresholds=(200,100))
    def test_ui_sample_and_invalidation(self):
        from streamlit.testing.v1 import AppTest
        page=Path(__file__).resolve().parents[1]/'pages/1_動画の点滅認識.py'
        app=AppTest.from_file(str(page),default_timeout=30).run()
        self.assertFalse(app.exception)
        app.checkbox[0].check().run();self.assertFalse(app.exception)
        app.button[0].click().run()
        from optical_video.testing import finish_ui_job
        finish_ui_job(app);self.assertFalse(app.exception)
        self.assertEqual(app.text_area[0].value,'イWFPロ')
        app.number_input[0].set_value(0).run()
        self.assertEqual(len(app.text_area),0)

if __name__=='__main__':unittest.main()
