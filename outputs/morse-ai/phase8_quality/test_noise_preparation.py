import unittest
import numpy as np
from phase8_quality.noise_preparation import mix_at_snr

class NoiseTests(unittest.TestCase):
    def test_snr_and_peak(self):
        clean=np.sin(np.arange(16000)*.2);noise=np.random.default_rng(1).normal(size=17000)
        for snr in (20,10,5,0,-5):
            mixed,m=mix_at_snr(clean,noise,snr,offset=7)
            self.assertAlmostEqual(m['measured_snr_db'],snr,places=9);self.assertLessEqual(abs(mixed).max(),.950001)
            np.testing.assert_array_equal(mixed,mix_at_snr(clean,noise,snr,offset=7)[0])
    def test_invalid_noise(self):
        for clean,noise,offset in [(np.zeros(8),np.arange(8),0),(np.arange(8),np.ones(8),0),(np.arange(8),np.arange(7),0),(np.arange(8),np.arange(8),1),(np.arange(8),np.array([np.nan]*8),0)]:
            with self.assertRaises(ValueError):mix_at_snr(clean,noise,0,offset=offset)

if __name__=='__main__':unittest.main()
