import tempfile
import unittest
from pathlib import Path
import torch
from torch import nn
from torch.utils.data import DataLoader,TensorDataset
from audio_preprocessing import PreprocessConfig
from morse_cnn import MorseCNN,load_checkpoint
from train import run_epoch


class TrainingTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(31)
        self.old_threads=torch.get_num_threads()
        torch.set_num_threads(1)

    def tearDown(self):
        torch.set_num_threads(self.old_threads)

    def test_forward_backward_updates_parameters(self):
        model=MorseCNN()
        x=torch.randn(2,1,64,512)
        logits=model(x)
        self.assertEqual(tuple(logits.shape),(2,65))
        self.assertTrue(torch.isfinite(logits).all())
        before=model.features[0].weight.detach().clone()
        optimizer=torch.optim.Adam(model.parameters(),lr=0.001)
        nn.CrossEntropyLoss()(logits,torch.tensor([0,64])).backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
        optimizer.step()
        self.assertFalse(torch.equal(before,model.features[0].weight))

    def test_checkpoint_exact_reload_and_configuration(self):
        model=MorseCNN(3).eval()
        x=torch.randn(2,1,64,512)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'best.pt'
            torch.save(dict(format_version='m6-v1',model_config=model.model_config,
                            model_state_dict=model.state_dict(),preprocessing=PreprocessConfig().to_dict(),
                            label_to_index={'イ':0,'ロ':1,'ハ':2}),path)
            loaded,config,checkpoint=load_checkpoint(path)
            with torch.no_grad():
                torch.testing.assert_close(model(x),loaded(x),rtol=0,atol=0)
            self.assertEqual(config.target_frames,512)
            self.assertFalse(loaded.training)
            self.assertEqual(checkpoint['label_to_index']['ハ'],2)

    def test_temporal_variant_checkpoint(self):
        model=MorseCNN(3,32,0.1,'temporal').eval()
        x=torch.randn(2,1,64,512)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'temporal.pt'
            torch.save(dict(format_version='m6-v1',model_config=model.model_config,
                model_state_dict=model.state_dict(),preprocessing=PreprocessConfig().to_dict(),
                label_to_index={'イ':0,'ロ':1,'ハ':2}),path)
            loaded,_,_=load_checkpoint(path)
            with torch.no_grad():
                torch.testing.assert_close(model(x),loaded(x),rtol=0,atol=0)
            self.assertEqual(loaded.variant,'temporal')

    def test_validation_is_weighted_and_does_not_update_model(self):
        model=MorseCNN(3)
        x=torch.randn(5,1,64,512);y=torch.tensor([0,1,2,0,1])
        original={k:v.clone() for k,v in model.state_dict().items()}
        result=run_epoch(model,DataLoader(TensorDataset(x,y),batch_size=3),nn.CrossEntropyLoss())
        with torch.no_grad():
            expected=nn.CrossEntropyLoss()(model(x),y).item()
        self.assertAlmostEqual(result['loss'],expected,places=5)
        self.assertEqual(result['samples'],5)
        for key,value in model.state_dict().items():
            torch.testing.assert_close(value,original[key],rtol=0,atol=0)


if __name__=='__main__':
    unittest.main()
