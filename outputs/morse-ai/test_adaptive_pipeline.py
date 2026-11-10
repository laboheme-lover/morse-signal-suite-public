import sys,unittest,io
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parent/'phase8_quality'))
from adaptive_pipeline import track_carrier,normalize_feature,evaluate
from timing_frontend import segment_timing
from stress_frontend import synth
from morse_table import MORSE_TABLE

class AdaptiveTests(unittest.TestCase):
    def test_upload_decoder(self):
        import soundfile as sf
        from experimental_audio_io import load_upload
        stream=io.BytesIO();sf.write(stream,np.zeros((44100,2)),44100,format='WAV')
        wave=load_upload(stream.getvalue(),'.wav');self.assertEqual(wave.shape,(16000,))
        with self.assertRaises(ValueError):load_upload(b'','.wav')
        with self.assertRaises(ValueError):load_upload(b'x','.exe')
        stream=io.BytesIO();sf.write(stream,np.zeros(1600),16000,format='WAV')
        with self.assertRaises(ValueError):load_upload(stream.getvalue(),'.wav')

    def test_tracking_wobble(self):
        audio,_,_=synth('スセソ',.08,'wobble60',41)
        transformed,meta=track_carrier(audio);rows,_=segment_timing(transformed)
        self.assertEqual(len(transformed),len(audio));self.assertTrue(np.isfinite(transformed).all())
        self.assertLess(meta['tracked_min_hz'],660);self.assertGreater(meta['tracked_max_hz'],740)
        self.assertEqual([r['pattern'] for r in rows],[MORSE_TABLE[c] for c in 'スセソ'])
    def test_normalization_keeps_padding(self):
        feature=torch.cat([torch.zeros(10,1),torch.ones(40,1),torch.zeros(10,1)])
        adjusted,scale=normalize_feature(feature,.2,{'preprocessing':{'hop_ms':10}})
        self.assertEqual(scale,.5);self.assertEqual(len(adjusted),40)
        self.assertTrue(torch.equal(adjusted[:10],feature[:10]));self.assertTrue(torch.equal(adjusted[-10:],feature[-10:]))
    def test_invalid_inputs(self):
        for audio in (np.zeros(16000),np.ones((16000,2)),np.full(16000,np.nan)):
            with self.assertRaises(ValueError):track_carrier(audio)
        with self.assertRaises(ValueError):normalize_feature(torch.ones(40,1),0,{'preprocessing':{'hop_ms':10}})
    def test_live_app(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parent
        app=AppTest.from_file(str(root/'experiment_app.py'),default_timeout=90).run()
        self.assertFalse(app.exception)
        app.button[0].click().run();self.assertFalse(app.exception)
        table=app.dataframe[0].value
        self.assertEqual(len(table),2);self.assertNotIn('CER',table.columns)
        self.assertEqual(table.iloc[1]['認識本文'],'スセソ')
        app.selectbox[2].set_value('combined_mode').run();self.assertFalse(app.exception)
        app.text_area[0].set_value('スセソ').run();self.assertFalse(app.exception)
        self.assertIn('CER',app.dataframe[0].value.columns)
        self.assertEqual(app.dataframe[0].value.iloc[1]['CER'],0)
        app.selectbox[1].set_value('M2').run();self.assertFalse(app.exception)
        self.assertTrue(any('設定が変わりました' in r.value for r in app.info))

if __name__=='__main__':unittest.main()
