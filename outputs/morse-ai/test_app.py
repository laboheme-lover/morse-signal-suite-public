import io
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from streamlit.testing.v1 import AppTest
from generate_morse_audio import generate_morse_audio

APP=Path(__file__).with_name('app.py')

class AppTests(unittest.TestCase):
    def test_upload_infer_details_and_invalidation(self):
        app=AppTest.from_file(str(APP),default_timeout=30).run()
        self.assertFalse(app.exception);self.assertTrue(app.button[0].disabled)
        b=io.BytesIO();sf.write(b,np.concatenate([generate_morse_audio(c,padding=.15) for c in 'イロハ']),16000,format='WAV')
        app.file_uploader[0].upload('sample.wav',b.getvalue(),'audio/wav').run()
        app.button[0].click().run()
        self.assertFalse(app.exception);self.assertEqual(app.text_area[0].value,'イロハ')
        self.assertEqual(app.metric[0].value,'3');self.assertEqual(app.metric[2].value,'0')
        result=app.session_state['recognition'];self.assertEqual(result['model'],'M3')
        self.assertEqual(app.metric[1].value,f"{result['mean_confidence']:.1%}")
        self.assertEqual(len(app.dataframe),2)
        app.selectbox[0].select_index(1).run();self.assertFalse(app.exception)
        app.slider[0].set_value(4).run()
        self.assertEqual(len(app.text_area),0)

    def test_mixed_sample_and_invalid_audio(self):
        app=AppTest.from_file(str(APP),default_timeout=30).run()
        app.radio[0].set_value('サンプル：イ（ヤチツ）ロ').run();app.button[0].click().run()
        self.assertFalse(app.exception);self.assertEqual(app.text_area[0].value,'イ（ヤチツ）ロ')
        app.radio[0].set_value('ファイルをアップロード').run()
        b=io.BytesIO();sf.write(b,np.zeros(16000),16000,format='WAV')
        app.file_uploader[0].upload('silence.wav',b.getvalue(),'audio/wav').run();app.button[0].click().run()
        self.assertFalse(app.exception);self.assertTrue(app.error)
        self.assertEqual(len(app.text_area),0)
