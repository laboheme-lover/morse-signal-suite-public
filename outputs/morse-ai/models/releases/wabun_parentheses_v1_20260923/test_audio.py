import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from generate_morse_audio import generate_morse_audio, save_wav
from morse_table import MORSE_TABLE
from visualize_audio import compute_mel_db, load_audio


class AudioTests(unittest.TestCase):
    def test_i_timing_frequency_and_silence(self):
        audio = generate_morse_audio('イ')
        self.assertEqual(len(audio), 11200)  # .1 silence + .1 dot + .1 gap + .3 dash + .1 silence
        for start, end in ((0, 1600), (3200, 4800), (9600, 11200)):
            self.assertTrue(np.all(audio[start:end] == 0))
        for start, end in ((1600, 3200), (4800, 9600)):
            tone = audio[start:end]
            self.assertGreater(np.sqrt(np.mean(tone**2)), 0.45)
            frequencies = np.fft.rfftfreq(len(tone), 1 / 16000)
            self.assertAlmostEqual(frequencies[np.argmax(np.abs(np.fft.rfft(tone)))], 700)
        self.assertLessEqual(np.max(np.abs(audio)), 0.700001)

    def test_all_labels_generate(self):
        for label, code in MORSE_TABLE.items():
            with self.subTest(label=label):
                audio = generate_morse_audio(label)
                units = sum(1 if s == '.' else 3 for s in code) + len(code) - 1
                self.assertEqual(len(audio), 3200 + 1600 * units)
                self.assertTrue(np.isfinite(audio).all())

    def test_wav_and_mel_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = save_wav(Path(folder) / 'イ.wav', generate_morse_audio('イ'))
            info = sf.info(path)
            self.assertEqual((info.samplerate, info.channels, info.subtype), (16000, 1, 'PCM_16'))
            audio = load_audio(path)
            np.testing.assert_allclose(audio, generate_morse_audio('イ'), atol=1/32768)
            mel = compute_mel_db(audio)
            self.assertEqual(mel.shape, (64, 88))
            self.assertTrue(np.isfinite(mel).all())
            self.assertGreater(float(mel.max() - mel.min()), 40)

    def test_invalid_parameters(self):
        for kwargs in ({'dot_duration': 0}, {'frequency_hz': 8000}, {'amplitude': 2},
                       {'padding': -1}, {'amplitude': float('nan')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                generate_morse_audio('イ', **kwargs)


if __name__ == '__main__':
    unittest.main()
