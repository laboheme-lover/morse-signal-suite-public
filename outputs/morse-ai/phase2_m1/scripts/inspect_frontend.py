"""Visual QA on training examples only; never opens Test."""
from pathlib import Path
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'reports/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from m1.data import WaveformDataset,PHASE1,envelope
from m1.utils import write_json


def main():
    cfg=json.loads((ROOT/'config/m1.json').read_text())
    dataset=WaveformDataset('train',root=PHASE1)
    indices=[]
    for noisy in (False,True):
        indices.append(next(i for i,row in enumerate(dataset.rows)
            if row['label']=='A' and row['source_id']=='generated'
            and ((row['snr_db']=='-5.0' or row['snr_db']=='-5') if noisy else row['noise_type']=='none')))
    fig,axes=plt.subplots(2,2,figsize=(11,5))
    provenance=[]
    for row_index,i in enumerate(indices):
        sample=dataset[i];meta=dataset.rows[i]
        feature=envelope(sample['audio'],sample['sample_rate'],cfg).numpy().ravel()
        axes[row_index,0].plot(np.arange(len(sample['audio']))/sample['sample_rate'],sample['audio'],lw=.5)
        axes[row_index,0].set(title=f"A (.-): {meta['noise_type']}, SNR={meta['snr_db'] or 'clean'}",ylabel='Amplitude')
        axes[row_index,1].plot(np.arange(len(feature))*cfg['preprocessing']['hop_ms']/1000,feature)
        axes[row_index,1].set(title='Normalized RMS envelope (CNN input)',ylabel='Feature value')
        for ax in axes[row_index]:ax.set_xlabel('Time (s)')
        provenance.append({'sample_id':meta['sample_id'],'filename':meta['filename'],'sha256':meta['sha256'],'split':'train'})
    (ROOT/'reports').mkdir(exist_ok=True)
    fig.tight_layout();fig.savefig(ROOT/'reports/frontend_examples.png',dpi=160);plt.close(fig)
    write_json(ROOT/'reports/frontend_examples.json',{'config':cfg['preprocessing'],'examples':provenance})


if __name__=='__main__':main()
