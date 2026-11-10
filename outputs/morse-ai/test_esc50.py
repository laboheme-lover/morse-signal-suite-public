import csv
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from esc50_manager import ESC50Manager, SPLIT_FOLDS
from add_esc50_noise import generate_esc50_sample
from augment_audio import generate_sample, SNR_LEVELS


class ESC50Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'meta').mkdir()
        (self.root/'audio').mkdir()
        self.rows = [dict(filename=f'{fold}-{100+fold}-A-0.wav', fold=fold,
                          category='fixture', src_file=str(100+fold)) for fold in range(1, 6)]
        self.write_catalog()
        # Stereo, 8 kHz, deliberately shorter than some Morse requests.
        rng = np.random.default_rng(1)
        for row in self.rows:
            sf.write(self.root/'audio'/row['filename'], rng.normal(0, 0.1, (2000, 2)), 8000)

    def tearDown(self):
        self.tmp.cleanup()

    def write_catalog(self):
        with (self.root/'meta/esc50.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['filename', 'fold', 'category', 'src_file'])
            writer.writeheader()
            writer.writerows(self.rows)

    def test_split_isolation(self):
        manager = ESC50Manager(self.root)
        for split, folds in SPLIT_FOLDS.items():
            self.assertEqual({r.fold for r in manager.candidates(split)}, set(folds))
            for seed in range(10):
                _, meta = manager.segment(split, 1000, np.random.default_rng(seed))
                self.assertIn(meta['esc50_fold'], folds)
        with self.assertRaises(ValueError):
            manager.segment('train', 1000, np.random.default_rng(0), filename=self.rows[4]['filename'])

    def test_conflicting_sources_quarantined(self):
        self.rows[4]['src_file'] = self.rows[3]['src_file']
        self.write_catalog()
        manager = ESC50Manager(self.root)
        self.assertEqual(len(manager.excluded_records), 2)
        self.assertEqual({r.fold for r in manager.records}, {1,2,3})
        with self.assertRaises(FileNotFoundError):
            manager.candidates('test', available_only=True)

    def test_missing_audio_requires_explicit_partial_mode(self):
        (self.root/'audio'/self.rows[0]['filename']).unlink()
        manager = ESC50Manager(self.root)
        with self.assertRaises(FileNotFoundError):
            manager.candidates('train')
        self.assertEqual(len(manager.candidates('train', available_only=True)), 2)

    def test_crop_repeat_resample_reproducibility(self):
        manager = ESC50Manager(self.root)
        for length in (1000, 16000):
            audio, meta = manager.segment('test', length, np.random.default_rng(21))
            repeated, again = manager.segment('test', length, np.random.default_rng(21))
            np.testing.assert_array_equal(audio, repeated)
            self.assertEqual(meta, again)
            self.assertEqual(len(audio), length)
            self.assertEqual(meta['esc50_resampled_samples'], 4000)
            self.assertEqual(meta['esc50_repeated'], length > 4000)

    def test_snr_after_pcm_save(self):
        manager = ESC50Manager(self.root)
        clean, _ = generate_sample('イ', 'normal', seed=19)
        for split in SPLIT_FOLDS:
            for snr in SNR_LEVELS:
                mixed, meta = generate_esc50_sample(manager, 'イ', 'normal', split, snr, 19, 7)
                self.assertLessEqual(max(abs(mixed)), 0.98000001)
                self.assertIn(meta['esc50_fold'], SPLIT_FOLDS[split])
                path = self.root/'mixed.wav'
                sf.write(path, mixed, 16000, subtype='PCM_16')
                saved, _ = sf.read(path)
                signal = clean.astype(float)*meta['mix_gain']
                measured = 10*np.log10(np.mean(signal**2)/np.mean((saved-signal)**2))
                self.assertAlmostEqual(measured, snr, delta=0.01)

    def test_silence_and_unsafe_catalog_rejected(self):
        sf.write(self.root/'audio'/self.rows[4]['filename'], np.zeros(4000), 16000)
        with self.assertRaises(ValueError):
            ESC50Manager(self.root).segment('test', 1000, np.random.default_rng(0))
        self.rows[0]['filename'] = '../escape.wav'
        self.write_catalog()
        with self.assertRaises(ValueError):
            ESC50Manager(self.root)


if __name__ == '__main__':
    unittest.main()
