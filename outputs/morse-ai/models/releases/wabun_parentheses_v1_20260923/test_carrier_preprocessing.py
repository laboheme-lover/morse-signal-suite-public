import unittest
import numpy as np
from scipy.signal import welch
from carrier_preprocessing import translate_carrier
from generate_morse_audio import generate_morse_audio
from morse_segmentation import segment_morse


class CarrierTests(unittest.TestCase):
    def test_frequency_and_timing(self):
        x=generate_morse_audio('シ',.08,3272,.6,padding=.3)
        y,meta=translate_carrier(x)
        self.assertEqual(len(x),len(y))
        self.assertFalse(meta['timing_resampled'])
        f,p=welch(y,16000,nperseg=8192)
        self.assertAlmostEqual(f[np.argmax(p)],700,delta=3)
        a,_=segment_morse(x,frequency_hz=3272)
        b,_=segment_morse(y,frequency_hz=700)
        self.assertEqual([r['pattern'] for r in a],[r['pattern'] for r in b])
        for r,s in zip(a,b):
            self.assertAlmostEqual(r['start_seconds'],s['start_seconds'],delta=.003)
            self.assertAlmostEqual(r['end_seconds'],s['end_seconds'],delta=.003)

    def test_validation(self):
        for x in [np.zeros(16000),np.ones((16000,2)),np.full(16000,np.nan)]:
            with self.assertRaises(ValueError):translate_carrier(x)
        with self.assertRaises(ValueError):translate_carrier(np.ones(16000),source_hz=3272,target_hz=50)

    def test_identity_carrier_amplitude(self):
        x=.5*np.sin(2*np.pi*700*np.arange(16000)/16000)
        y,_=translate_carrier(x,source_hz=700)
        self.assertLess(np.sqrt(np.mean((x[1000:-1000]-y[1000:-1000])**2)),.005)


if __name__=='__main__':unittest.main()
