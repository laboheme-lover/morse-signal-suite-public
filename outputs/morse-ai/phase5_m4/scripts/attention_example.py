"""Inspect actual attention weights on a predetermined Validation example."""
from pathlib import Path
import argparse
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.append(str(ROOT.parent/'phase2_m1'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'reports/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch
from m1.data import WaveformDataset,PHASE1,envelope
from m1.utils import setup,write_json,sha
from m4.model import M4


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args=ap.parse_args()
    run=args.run.resolve();ck=torch.load(run/'best.pt',map_location='cpu',weights_only=True)
    cfg=ck['config'];setup(cfg)
    data=WaveformDataset('validation',root=PHASE1);sample=data[0]
    feature=envelope(sample['audio'],sample['sample_rate'],cfg)
    model=M4(cfg).eval();model.load_state_dict(ck['state_dict'])
    with torch.inference_mode():
        logits,weights,lengths=model(feature.T.unsqueeze(0),torch.tensor([len(feature)]),return_attention=True)
    w=weights[0,:lengths[0]].numpy();prob=logits.softmax(-1)[0];labels=sorted(ck['labels'],key=ck['labels'].get)
    prediction=labels[prob.argmax().item()]
    hop=cfg['preprocessing']['hop_ms']/1000
    fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True)
    axes[0].plot(np.arange(len(sample['audio']))/sample['sample_rate'],sample['audio'],lw=.5)
    axes[0].set(ylabel='Amplitude',title=f"M4 Validation example: true={sample['label']}, predicted={prediction}")
    axes[1].plot(np.arange(len(feature))*hop,feature[:,0].numpy());axes[1].set_ylabel('CNN input')
    axes[2].plot(np.arange(len(w))*hop*2,w);axes[2].set(xlabel='Time (s)',ylabel='Attention weight')
    fig.suptitle('Weights sum to 1; not a causal explanation',fontsize=10)
    fig.tight_layout();(run/'figures').mkdir(exist_ok=True)
    fig.savefig(run/'figures/attention_example.png',dpi=160);plt.close(fig)
    write_json(run/'attention_example.json',{'selection':'first Validation row, predetermined; not selected by prediction',
        'sample_id':sample['sample_id'],'filename':sample['path'],'audio_sha256':sha(sample['path']),
        'checkpoint_sha256':sha(run/'best.pt'),'true_label':sample['label'],'predicted_label':prediction,
        'probability':float(prob.max()),'weights':w.tolist(),'weight_sum':float(w.sum()),
        'step_seconds':hop*2,'scope':'Model aggregation weights; not causal attribution or accuracy'})
    print(json.dumps({'label':sample['label'],'prediction':prediction,'weight_sum':float(w.sum())}))


if __name__=='__main__':main()
