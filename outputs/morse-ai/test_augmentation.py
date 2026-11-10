import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from augment_audio import SPEED_RANGES, SNR_LEVELS, generate_sample, mix_at_snr
from generate_variations import generate_variations


class AugmentationTests(unittest.TestCase):
    def test_ranges_jitter_and_frequency(self):
        dots = []
        for speed, bounds in SPEED_RANGES.items():
            for seed in range(10):
                audio, meta = generate_sample('イ', speed, seed=seed)
                dot = meta['dot_duration']
                dots.append(dot)
                self.assertTrue(bounds[0] <= dot <= bounds[1])
                self.assertTrue(600 <= meta['frequency_hz'] <= 800)
                self.assertTrue(0.4 <= meta['amplitude'] <= 0.9)
                self.assertEqual([t['kind'] for t in meta['timing_samples']], ['.', 'gap', '-'])
                cursor = 1600
                for part in meta['timing_samples']:
                    count = part['samples']
                    base = dot * 16000 * (3 if part['kind'] == '-' else 1)
                    self.assertLessEqual(abs(count-base), base*0.1+0.5)
                    segment = audio[cursor:cursor+count]
                    if part['kind'] == 'gap':
                        self.assertTrue(np.all(segment == 0))
                    else:
                        freq = np.fft.rfftfreq(count, 1/16000)[np.argmax(abs(np.fft.rfft(segment)))]
                        self.assertLessEqual(abs(freq-meta['frequency_hz']), 16000/count)
                    cursor += count
                self.assertEqual(len(audio), cursor+1600)
        self.assertEqual(len(set(dots)), 30)

    def test_snr_and_peak(self):
        for speed in SPEED_RANGES:
            clean, _ = generate_sample('モ', speed, seed=17)
            for snr in SNR_LEVELS:
                audio, meta = generate_sample('モ', speed, 'white', snr, 17)
                signal = clean.astype(np.float64) * meta['mix_gain']
                noise = audio-signal
                measured = 10*np.log10(np.mean(signal**2)/np.mean(noise**2))
                self.assertAlmostEqual(measured, snr, places=10)
                self.assertLessEqual(np.max(abs(audio)), 0.98000001)
                self.assertGreater(np.std(noise[:1600]), 0)

    def test_saved_metadata_and_reproduction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'run'
            rows = generate_variations(root, ['イ'], seed=42)
            self.assertEqual(len(rows), 18)
            with (root/'metadata.csv').open(encoding='utf-8-sig', newline='') as stream:
                disk_rows = list(csv.DictReader(stream))
            for row in disk_rows:
                snr = float(row['snr_db']) if row['snr_db'] else None
                audio, meta = generate_sample(row['label'], row['speed'], row['noise_type'], snr, int(row['seed']))
                stored, sr = sf.read(root/row['filepath'])
                self.assertEqual(sr, 16000)
                self.assertEqual(len(stored), int(row['samples']))
                self.assertEqual(json.loads(row['timing_samples']), meta['timing_samples'])
                self.assertEqual(hashlib.sha256((root/row['filepath']).read_bytes()).hexdigest(), row['wav_sha256'])
                np.testing.assert_allclose(stored, audio, atol=1/32768)
                if snr is not None:
                    clean, _ = generate_sample(row['label'], row['speed'], seed=int(row['seed']))
                    signal = clean.astype(np.float64)*float(row['mix_gain'])
                    measured = 10*np.log10(np.mean(signal**2)/np.mean((stored-signal)**2))
                    self.assertAlmostEqual(measured, snr, delta=0.01)
            with self.assertRaises(FileExistsError):
                generate_variations(root, ['イ'])

    def test_invalid_conditions(self):
        for options in ({'speed':'bad'}, {'noise_type':'esc50'}, {'noise_type':'white'},
                        {'snr_db':20}, {'noise_type':'white','snr_db':30}):
            kwargs = dict(label='イ', speed='normal') | options
            with self.subTest(options=options), self.assertRaises(ValueError):
                generate_sample(**kwargs)
        for signal, noise in (([0,0],[1,1]), ([1,1],[0,0]), ([1],[1,2]), ([float('nan')],[1])):
            with self.assertRaises(ValueError):
                mix_at_snr(signal, noise, 10)


if __name__ == '__main__':
    unittest.main()
