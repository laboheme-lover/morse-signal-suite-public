import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from predict import MorsePredictor,save_prediction
from audio_preprocessing import audio_to_tensor
from generate_morse_audio import generate_morse_audio,save_wav


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.predictor=MorsePredictor()

    def test_shared_preprocessing_and_probabilities(self):
        audio=generate_morse_audio('イ')
        p=self.predictor;result=p.predict_audio(audio)
        with torch.inference_mode():
            probabilities=p.model(audio_to_tensor(audio,p.config).unsqueeze(0)).softmax(1)[0]
        expected=int(probabilities.argmax())
        self.assertEqual(result['prediction'],p.labels[expected])
        self.assertAlmostEqual(result['confidence'],float(probabilities[expected]),places=6)
        self.assertEqual(len(result['top_k']),3)
        self.assertTrue(all(a['probability']>=b['probability'] for a,b in zip(result['top_k'],result['top_k'][1:])))
        self.assertEqual(result['input_shape'],[1,64,512])
        all_candidates=p.predict_audio(audio,65)['top_k']
        self.assertAlmostEqual(sum(r['probability'] for r in all_candidates),1.,places=5)

    def test_file_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            path=save_wav(directory/'i.wav',generate_morse_audio('イ'))
            result=self.predictor.predict_file(path)
            metadata=save_prediction(result,directory/'result')
            self.assertNotIn('mel',metadata)
            np.testing.assert_array_equal(np.load(directory/'result/mel.npy'),result['mel'])
            self.assertGreater((directory/'result/mel.png').stat().st_size,100)
            with self.assertRaises(FileExistsError):save_prediction(result,directory/'result')

    def test_invalid_inputs_and_no_truncation(self):
        for audio in [np.array([]),np.zeros(1600),np.full(1600,np.nan),np.zeros((2,1600))]:
            with self.assertRaises(ValueError):self.predictor.predict_audio(audio)
        for k in [0,66,1.5,True]:
            with self.assertRaises(ValueError):self.predictor.predict_audio(generate_morse_audio('イ'),k)
        with self.assertRaises(ValueError):self.predictor.predict_audio(np.ones(16000*5)*.1)
        with self.assertRaises(FileNotFoundError):self.predictor.predict_file('nonexistent_m8_test.wav')
