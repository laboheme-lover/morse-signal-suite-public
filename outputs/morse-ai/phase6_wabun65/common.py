from pathlib import Path
import csv, json, sys
import numpy as np
import soundfile as sf
import torch
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
for name in ('phase1_data','phase2_m1','phase3_m2','phase4_m3','phase5_m4'):
    sys.path.append(str(PROJECT/name))
from m1.model import M1
from m2.model import M2
from m3.model import M3
from m4.model import M4
from m1.data import envelope, collate
from m1.utils import setup, sha, write_json, write_csv, metrics
MODELS = {'M1':M1,'M2':M2,'M3':M3,'M4':M4}

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

class PreparedDataset(torch.utils.data.Dataset):
    def __init__(self, split, config, evaluation=False):
        if split not in ('train','validation','test') or (split=='test' and not evaluation):
            raise ValueError('Test is evaluation-only')
        self.labels=json.loads((ROOT/'metadata/label_mapping.json').read_text(encoding='utf-8'))
        self.rows=read_csv(ROOT/f'metadata/{split}.csv')
        lock=json.loads((ROOT/'metadata/lock.json').read_text())
        for filename in (f'{split}.csv','label_mapping.json'):
            if sha(ROOT/'metadata'/filename)!=lock[filename]: raise ValueError('Index changed')
        self.items=[]
        for i,r in enumerate(self.rows):
            p=Path(r['filename'])
            if r['split']!=split or (split!='test' and 'test' in [x.lower() for x in p.parts]):
                raise ValueError('Split mismatch')
            if sha(p)!=r['sha256']: raise ValueError('Audio changed')
            x,sr=sf.read(p,dtype='float32')
            self.items.append((envelope(x,sr,config),self.labels[r['label']],i))
    def __len__(self): return len(self.items)
    def __getitem__(self,index): return self.items[index]

def infer(model, loader):
    model.eval()
    targets=[]; guesses=[]; probabilities=[]; indices=[]; loss=0.
    with torch.inference_mode():
        for x,lengths,y,ids in loader:
            logits=model(x,lengths)
            loss+=torch.nn.functional.cross_entropy(logits,y,reduction='sum').item()
            p=logits.softmax(-1)
            targets.extend(y.tolist());guesses.extend(p.argmax(-1).tolist())
            probabilities.extend(p.max(-1).values.tolist());indices.extend(ids.tolist())
    result=metrics(targets,guesses,classes=65)
    result['loss']=loss/len(targets)
    return result,(targets,guesses,probabilities,indices)
