"""Frozen-asset integrity and audio M3 inference smoke test, not an accuracy evaluation."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'outputs/morse-ai/phase6_wabun65'), str(ROOT / 'optical-ml')]

class ReleaseTests(unittest.TestCase):
    def test_optical_release_integrity(self):
        from production import verify_release
        verify_release()

    def test_audio_frozen_files_integrity(self):
        release = ROOT / 'outputs/morse-ai/models/releases/wabun_parentheses_v1_20260923'
        manifest = json.loads((release / 'release_manifest.json').read_text(encoding='utf-8'))
        self.assertGreater(len(manifest['files']), 0)
        for name, expected in manifest['files'].items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((release / name).read_bytes()).hexdigest(), expected)

    def test_adopted_audio_m3_forward(self):
        from common import MODELS, envelope, collate
        checkpoint = ROOT / 'outputs/morse-ai/models/releases/wabun_parentheses_v1_20260923/phase6_wabun65/runs/m3_wabun65_20260922/best.pt'
        ck = torch.load(checkpoint, map_location='cpu', weights_only=True)
        torch.set_num_threads(2)
        model = MODELS['M3'](ck['config']).eval()
        model.load_state_dict(ck['state_dict'])
        t = np.arange(16000, dtype=np.float32) / 16000
        wave = (.5 * np.sin(2 * np.pi * 700 * t) * ((t < .2) | ((t > .4) & (t < .9)))).astype(np.float32)
        features = envelope(wave, 16000, ck['config'])
        x, lengths, _, _ = collate([(features, 0, 0)])
        with torch.inference_mode():
            logits = model(x, lengths)
        self.assertEqual(tuple(logits.shape), (1, 65))
        self.assertTrue(torch.isfinite(logits).all())
        self.assertAlmostEqual(float(logits.softmax(-1).sum()), 1., places=6)

if __name__ == '__main__':
    unittest.main()
