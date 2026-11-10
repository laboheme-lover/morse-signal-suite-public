from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT.parent/"phase2_m1"))
import numpy as np
import torch
from m1.data import envelope, collate, PreparedDataset
from m4.model import M4
from m1.utils import setup, metrics

CFG = json.loads((ROOT/'config/m4.json').read_text())


class M4Tests(unittest.TestCase):
    def setUp(self):
        setup(CFG)

    def test_attention_normalization_padding_and_gradient(self):
        model=M4(CFG).eval()
        logits,weights,lengths=model(torch.randn(3,1,101),torch.tensor([35,101,1]),return_attention=True)
        self.assertEqual(lengths.tolist(),[18,51,1])
        self.assertTrue(torch.isfinite(logits).all())
        self.assertTrue(torch.allclose(weights.sum(1),torch.ones(3),atol=1e-6))
        for i,length in enumerate(lengths):
            self.assertTrue(torch.equal(weights[i,length:],torch.zeros_like(weights[i,length:])))
        logits.sum().backward()
        self.assertTrue(all(p.grad is not None and p.grad.abs().sum()>0 for p in model.attention.parameters()))

    def test_shared_m3_initial_parameters_are_identical(self):
        from m3.model import M3
        baseline=M3(CFG).state_dict();setup(CFG);new=M4(CFG).state_dict()
        self.assertTrue(all(torch.equal(value,new[name]) for name,value in baseline.items()))

    def test_invalid_attention_size(self):
        for size in (0,-1,1.5):
            cfg=copy.deepcopy(CFG);cfg['model']['attention_size']=size
            with self.assertRaises(ValueError):M4(cfg)

    def test_multiscale_branches_and_bigru(self):
        model=M4(CFG)
        self.assertEqual([b.kernel_size[0] for b in model.branches],[3,5,9])
        self.assertEqual([b.out_channels for b in model.branches],[8,8,8])
        self.assertIsInstance(model.rnn,torch.nn.GRU)
        self.assertTrue(model.rnn.bidirectional)
        self.assertEqual(sum(p.numel() for p in model.parameters()),58548)
        x=torch.randn(2,1,80);model(x,torch.tensor([80,41])).sum().backward()
        self.assertTrue(all(b.weight.grad is not None and b.weight.grad.abs().sum()>0 for b in model.branches))

    def test_only_architecture_settings_differ_from_m3(self):
        previous=json.loads((ROOT.parent/'phase4_m3/config/m3.json').read_text())
        current=copy.deepcopy(CFG)
        previous.pop('architecture');current.pop('architecture');current['model'].pop('attention_size')
        self.assertEqual(previous,current)

    def test_invalid_multiscale_configuration(self):
        for kernels,channels in [([3,5,8],24),([3,3,9],24),([3],24),([3,5,9],25)]:
            cfg=copy.deepcopy(CFG);cfg['model']['branch_kernels']=kernels;cfg['model']['channels'][0]=channels
            with self.assertRaises(ValueError):M4(cfg)

    def test_envelope_silence_scale_and_speed(self):
        silence = envelope(np.zeros(16000), 16000, CFG)
        self.assertTrue(torch.equal(silence, torch.zeros_like(silence)))
        t = np.arange(16000)/16000
        x = np.sin(2*np.pi*700*t)*((t>.1)&(t<.7))
        a = envelope(x,16000,CFG)
        b = envelope(x*.2,16000,CFG)
        self.assertTrue(torch.allclose(a,b,atol=1e-5))
        self.assertEqual(len(a),101)
        self.assertGreater(float(a[20:60].mean()),.9)
        self.assertLess(float(a[80:90].mean()),.05)

    def test_invalid_audio_rejected(self):
        for audio,sr in [(np.zeros(16000),8000),(np.zeros((100,2)),16000),(np.full(100,np.nan),16000)]:
            with self.assertRaises(ValueError): envelope(audio,sr,CFG)

    def test_padding_does_not_change_prediction(self):
        m=M4(CFG).eval()
        a=torch.rand(35,1); b=torch.rand(103,1)
        with torch.no_grad():
            alone=m(*collate([(a,0,0)])[:2])[0]
            together=m(*collate([(a,0,0),(b,1,1)])[:2])[0]
            dirty=torch.randn(1,1,103);dirty[0,0,:35]=a[:,0]
            changed=m(dirty,torch.tensor([35]))[0]
        self.assertTrue(torch.allclose(alone,together,atol=1e-6))
        self.assertTrue(torch.allclose(alone,changed,atol=1e-6))
        self.assertEqual(len(alone),36)

    def test_gradient_and_small_overfit(self):
        cfg=copy.deepcopy(CFG);cfg['model'].update(classes=2,dropout=0,hidden_size=8,channels=[6,8])
        model=M4(cfg);opt=torch.optim.Adam(model.parameters(),lr=.02)
        data=[(torch.full((20,1),float(i%2)),i%2,i) for i in range(8)]
        x,lengths,y,_=collate(data)
        first=None
        for _ in range(35):
            opt.zero_grad();out=model(x,lengths);loss=torch.nn.functional.cross_entropy(out,y)
            if first is None:first=loss.item()
            loss.backward();opt.step()
        self.assertLess(loss.item(),first*.2)
        self.assertEqual((out.argmax(1)==y).sum().item(),8)

    def test_checkpoint_roundtrip(self):
        m=M4(CFG).eval();x=torch.rand(2,1,40);lengths=torch.tensor([40,31])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model.pt';torch.save({'state_dict':m.state_dict(),'config':CFG},p)
            ck=torch.load(p,weights_only=True);other=M4(ck['config']).eval();other.load_state_dict(ck['state_dict'])
            self.assertTrue(torch.equal(m(x,lengths),other(x,lengths)))

    def test_seed_repeatable(self):
        a=M4(CFG).state_dict();setup(CFG);b=M4(CFG).state_dict()
        self.assertTrue(all(torch.equal(a[k],b[k]) for k in a))

    def test_test_requires_explicit_evaluation_before_io(self):
        with patch('m1.data.WaveformDataset',side_effect=AssertionError('Must not open Test')):
            with self.assertRaises(ValueError):PreparedDataset('test',CFG)

    def test_train_only_asks_for_train(self):
        class FakeBase:
            labels={'A':0};rows=[]
            def __len__(self):return 1
            def __getitem__(self,i):return {'audio':np.zeros(16000),'sample_rate':16000,'label_index':0}
        with patch('m1.data.WaveformDataset',return_value=FakeBase()) as base:
            data=PreparedDataset('train',CFG)
            self.assertEqual(base.call_args.args,('train',))
            self.assertEqual(base.call_args.kwargs['purpose'],'training')
            self.assertEqual(len(data),1)

    def test_metrics_known_confusion(self):
        result=metrics([0,0,1,1],[0,1,1,1],2)
        self.assertEqual(result['confusion_matrix'],[[1,1],[0,2]])
        self.assertEqual(result['accuracy'],.75)
        self.assertAlmostEqual(result['macro_f1'],(2/3+.8)/2)

    def test_training_cli_completes_without_test_access(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('training_cli',ROOT/'scripts/train.py')
        train=importlib.util.module_from_spec(spec);spec.loader.exec_module(train)
        seen=[]
        class TinyDataset:
            def __init__(self,split,config):
                seen.append(split)
                if split not in ('train','validation'):raise AssertionError('Test accessed')
                self.labels={str(i):i for i in range(36)}
                self.items=[(torch.full((20+i%3,1),i/36),i,i) for i in range(36)]
            def __len__(self):return len(self.items)
            def __getitem__(self,i):return self.items[i]
        original_open=Path.open
        def guarded_open(path,*args,**kwargs):
            if path.name in ('test.csv','test_manifest.csv','test_lock.json','evaluation_index_lock.json') or 'test' in path.parts:
                raise AssertionError(f'Test read attempted: {path}')
            return original_open(path,*args,**kwargs)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cfg=copy.deepcopy(CFG);cfg['training']['epochs']=1
            config=root/'small.json';config.write_text(json.dumps(cfg))
            with patch.object(train,'ROOT',root),patch.object(train,'PreparedDataset',TinyDataset),patch.object(sys,'argv',['train','--config',str(config),'--run-name','smoke']),patch.object(Path,'open',guarded_open):
                train.main()
            result=json.loads((root/'runs/smoke/training_complete.json').read_text())
            self.assertEqual(result['status'],'complete')
            self.assertEqual(result['epochs_completed'],1)
            self.assertEqual(seen,['train','validation'])


if __name__=='__main__':unittest.main()
