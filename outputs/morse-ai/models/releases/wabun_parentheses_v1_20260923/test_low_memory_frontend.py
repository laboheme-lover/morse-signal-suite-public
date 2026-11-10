from pathlib import Path
import sys,unittest
import numpy as np
from scipy.signal import stft,welch,hilbert
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'phase8_quality'))
from low_memory_frontend import ridge_frames,carrier,fast_analytic,track_carrier
from adaptive_pipeline import track_carrier as original
from stress_frontend import synth
from timing_frontend import segment_timing

class LowMemoryTests(unittest.TestCase):
    def test_batched_spectral_frames(self):
        for n in [16000,16001,270113]:
            x=np.random.default_rng(79).normal(size=n)
            f,p=welch(x,16000,nperseg=min(n,16384));b=(f>=300)&(f<=1500);a=float(f[b][p[b].argmax()])
            self.assertEqual(carrier(x,16000),a)
            t,ridge,strength=ridge_frames(x,16000,a)
            f,tt,z=stft(x,fs=16000,nperseg=1024,noverlap=896,boundary='zeros',padded=True)
            b=(f>=max(200,a-220))&(f<=min(1700,a+220));q=abs(z[b])**2;k=q.argmax(axis=0)
            np.testing.assert_array_equal(t,tt);np.testing.assert_array_equal(ridge,f[b][k]);np.testing.assert_allclose(strength,q[k,np.arange(len(tt))],rtol=1e-13)
    def test_real_fft_matches_padded_hilbert(self):
        x=np.random.default_rng(79).normal(size=16001);y,n=fast_analytic(x)
        np.testing.assert_allclose(y,hilbert(x,N=n)[:len(x)],atol=2e-14)
    def test_no_lost_samples_or_changed_synthetic_codes(self):
        for dot in [.075,.19]:
            for profile in ['stable','wobble60','jitter30','combined']:
                x,_,_=synth('ヘイハ',dot,profile,557)
                old,oldmeta=original(x);new,meta=track_carrier(x)
                self.assertEqual(len(new),len(x));self.assertEqual(new.dtype,np.float32);self.assertTrue(np.isfinite(new).all())
                np.testing.assert_array_equal(meta['track_hz'],oldmeta['track_hz'])
                self.assertEqual([r['pattern'] for r in segment_timing(new)[0]],[r['pattern'] for r in segment_timing(old)[0]])
    def test_silence_and_invalid(self):
        for x in [np.zeros(16000),np.ones((16000,2)),np.full(16000,np.nan),np.zeros(10)]:
            with self.assertRaises(ValueError):track_carrier(x)
    def test_saved_variant_selection(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/'evaluation_app.py'),default_timeout=60).run()
        old=ROOT/'phase8_quality/real_adaptive_v1/comparisons/real_combined_mode_M1_comparison.json'
        new=ROOT/'phase8_quality/real_low_memory_v1/viewer_comparisons/real_combined_mode_M1_comparison.json'
        app.multiselect[0].set_value([old,new]).run();self.assertFalse(app.exception)
        names=app.dataframe[0].value['評価'].tolist()
        self.assertTrue(names[0].startswith('known_real_'));self.assertTrue(names[1].startswith('low_memory_known_real_'))

if __name__=='__main__':unittest.main()
