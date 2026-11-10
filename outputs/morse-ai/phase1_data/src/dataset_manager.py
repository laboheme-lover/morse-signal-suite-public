"""Model-independent raw waveforms. Training never reads a test index or WAV."""
from pathlib import Path
import json
import numpy as np
import soundfile as sf
from .common import ROOT, read_csv, sha256
from .morse_table import TABLE


class WaveformDataset:
    def __init__(self, split='train', root=ROOT, purpose='training', verify_hash=True):
        if split not in ('train','validation','test'): raise ValueError('Unknown split')
        if purpose not in ('training','evaluation'): raise ValueError('Unknown purpose')
        if split=='test' and purpose!='evaluation': raise ValueError('Test is evaluation-only')
        self.root=Path(root); self.split=split; self.verify_hash=verify_hash
        # No combined metadata file, no test manifest in the training code path.
        self.rows=read_csv(self.root / f'metadata/{split}.csv')
        self.labels=json.loads((self.root/'metadata/label_mapping.json').read_text(encoding='utf-8'))
        if split=='test':
            lock=json.loads((self.root/'reports/evaluation_index_lock.json').read_text())
            if sha256(self.root/'metadata/test.csv')!=lock['test_index_sha256'] or sha256(self.root/'metadata/label_mapping.json')!=lock['labels_sha256']:
                raise ValueError('Evaluation index / class mapping changed')
        for row in self.rows:
            path=(self.root / row['filename']).resolve()
            if row['split']!=split or row['label'] not in self.labels or TABLE[row['label']]!=row['morse_code']:
                raise ValueError('Index label / split mismatch')
            if split!='test' and 'test' in (p.lower() for p in path.parts): raise ValueError('Test path in training index')

    def __len__(self): return len(self.rows)

    def __getitem__(self,index):
        row=self.rows[index];path=(self.root/row['filename']).resolve()
        if self.verify_hash and sha256(path)!=row['sha256']: raise ValueError(f'WAV changed: {path}')
        audio,sr=sf.read(path,dtype='float32')
        if audio.ndim!=1 or sr!=int(row['sample_rate']) or not np.isfinite(audio).all(): raise ValueError('Invalid WAV')
        return {'audio':audio,'sample_rate':sr,'label':row['label'],'label_index':self.labels[row['label']],
                'split':self.split,'sample_id':row['sample_id'],'path':str(path)}
