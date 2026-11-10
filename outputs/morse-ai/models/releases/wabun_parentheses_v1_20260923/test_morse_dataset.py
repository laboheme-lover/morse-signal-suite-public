import csv
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import RandomSampler, SequentialSampler
from audio_preprocessing import PreprocessConfig, compute_mel_db, mel_to_tensor, wav_to_tensor
from generate_morse_audio import generate_morse_audio, save_wav
from morse_table import MORSE_TABLE
from morse_dataset import MorseDataset, create_dataloaders


class TensorPreprocessingTests(unittest.TestCase):
    def test_padding_preserves_signal_and_overlong_is_explicit(self):
        mel=compute_mel_db(generate_morse_audio('イ'))
        tensor=mel_to_tensor(mel)
        self.assertEqual(tuple(tensor.shape),(1,64,512))
        self.assertEqual(tensor.dtype,torch.float32)
        np.testing.assert_array_equal(tensor[0,:,:88].numpy(),mel)
        self.assertTrue(torch.all(tensor[0,:,88:]==-100))
        with self.assertRaises(ValueError):
            mel_to_tensor(mel,PreprocessConfig(target_frames=64))
        with self.assertWarns(UserWarning):
            cropped=mel_to_tensor(mel,PreprocessConfig(target_frames=64),allow_truncate=True)
        np.testing.assert_array_equal(cropped[0].numpy(),mel[:,:64])

    def test_invalid_mel(self):
        for mel in (np.zeros((32,100)),np.zeros((64,0)),np.full((64,10),np.nan)):
            with self.assertRaises(ValueError):
                mel_to_tensor(mel)
        with self.assertRaises(ValueError):
            PreprocessConfig(target_frames=0)


class MorseDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.config={'status':'complete','labels':['イ','モ'],'samples_per_class':3}
        (self.root/'dataset_config.json').write_text(json.dumps(self.config),encoding='utf-8')
        (self.root/'label_mapping.json').write_text(json.dumps({'イ':0,'モ':1}),encoding='utf-8')
        rows=[]
        for split in ('train','validation','test'):
            for label,index in (('イ',0),('モ',1)):
                audio=generate_morse_audio(label)
                relative=f'{split}/{index}.wav'
                save_wav(self.root/relative,audio)
                rows.append(dict(filepath=relative,split=split,label=label,class_index=index,
                                 morse_code=MORSE_TABLE[label],samples=len(audio)))
        with (self.root/'metadata.csv').open('w',encoding='utf-8-sig',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

    def tearDown(self):
        self.temp.cleanup()

    def test_shared_preprocessing_labels_and_isolation(self):
        datasets={s:MorseDataset(self.root,s) for s in ('train','validation','test')}
        for split,dataset in datasets.items():
            self.assertEqual(len(dataset),2)
            x,y=dataset[1]
            self.assertEqual(y.dtype,torch.int64)
            self.assertEqual(y.item(),1)
            torch.testing.assert_close(x,wav_to_tensor(self.root/split/'1.wav'),rtol=0,atol=0)
            self.assertTrue(all(row['split']==split for row in dataset.rows))

    def test_loader_sampling_and_partial_batch(self):
        loaders=create_dataloaders(self.root,batch_size=3)
        self.assertIsInstance(loaders['train'].sampler,RandomSampler)
        self.assertIsInstance(loaders['test'].sampler,SequentialSampler)
        for loader in loaders.values():
            x,y=next(iter(loader))
            self.assertEqual(tuple(x.shape),(2,1,64,512))
            self.assertEqual(set(y.tolist()),{0,1})
        one=create_dataloaders(self.root,seed=92)
        two=create_dataloaders(self.root,seed=92)
        self.assertEqual(list(one['train'].sampler),list(two['train'].sampler))

    def test_incomplete_dataset_and_short_input_rejected(self):
        with self.assertRaises(ValueError):
            MorseDataset(self.root,'train',PreprocessConfig(target_frames=64))
        self.config['status']='generating'
        (self.root/'dataset_config.json').write_text(json.dumps(self.config),encoding='utf-8')
        with self.assertRaises(ValueError):
            MorseDataset(self.root,'train')


if __name__=='__main__':
    unittest.main()
