import unittest, tempfile
from unittest.mock import patch
import contextlib, io
from common import *

class WabunTests(unittest.TestCase):
    def test_training_cli_without_test_files(self):
        import common, train
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'metadata').mkdir();(root/'config').mkdir()
            cfg=json.loads((ROOT/'config/m1.json').read_text())
            cfg['training']['epochs']=1
            write_json(root/'config/m1.json',cfg)
            labels={f'c{i}':i for i in range(65)}
            write_json(root/'metadata/label_mapping.json',labels)
            for split in ('train','validation'):
                rows=[]
                for i in (0,64):
                    wav=root/f'{split}_{i}.wav'
                    sf.write(wav,np.sin(np.arange(3200)*2*np.pi*700/16000).astype('float32')*.3,16000)
                    rows.append({'filename':str(wav),'label':f'c{i}','split':split,'sha256':sha(wav)})
                write_csv(root/f'metadata/{split}.csv',rows)
            write_json(root/'metadata/lock.json',{n:sha(root/'metadata'/n) for n in ('train.csv','validation.csv','label_mapping.json')})
            # No test index, manifest or audio exists: a training dependency would fail.
            with patch.object(common,'ROOT',root),patch.object(train,'ROOT',root),patch.object(train,'PHASE1',root),patch.object(sys,'argv',['train.py','--model','M1','--run-name','tiny']),contextlib.redirect_stdout(io.StringIO()):
                train.main()
            ck=torch.load(root/'runs/tiny/best.pt',weights_only=True)
            self.assertEqual(ck['config']['model']['classes'],65)
            self.assertEqual(len(ck['labels']),65)
            self.assertEqual(ck['epoch'],1)
    def test_test_access_guard(self):
        with self.assertRaises(ValueError): PreparedDataset('test', {})
    def test_class65_metric(self):
        result=metrics([0,64],[0,64],classes=65)
        self.assertEqual(result['accuracy'],1.)
        self.assertEqual(len(result['confusion_matrix']),65)
        self.assertEqual(result['support'][64],1)
    def test_all_models_65_roundtrip_and_padding(self):
        for name,cls in MODELS.items():
            with self.subTest(model=name):
                cfg=json.loads((ROOT/f'config/{name.lower()}.json').read_text())
                setup(cfg);m=cls(cfg).eval()
                x=torch.rand(2,1,40);lengths=torch.tensor([40,23])
                with torch.no_grad():
                    expected=m(x,lengths)
                    padded=torch.nn.functional.pad(x,(0,9),value=7.)
                    torch.testing.assert_close(expected,m(padded,lengths),atol=1e-6,rtol=1e-5)
                self.assertEqual(tuple(expected.shape),(2,65))
                torch.nn.functional.cross_entropy(m(x,lengths),torch.tensor([0,64])).backward()
                self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters()))
                with tempfile.TemporaryDirectory() as td:
                    file=Path(td)/'model.pt';torch.save(m.state_dict(),file)
                    restored=cls(cfg).eval();restored.load_state_dict(torch.load(file,weights_only=True))
                    with torch.no_grad():torch.testing.assert_close(expected,restored(x,lengths))

if __name__=='__main__':unittest.main()
