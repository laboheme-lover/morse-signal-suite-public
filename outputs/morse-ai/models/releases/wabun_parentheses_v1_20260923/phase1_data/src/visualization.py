from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import spectrogram
import soundfile as sf
from .common import ROOT,read_csv,write_json


def plot_reports(root=ROOT):
    root=Path(root); rows=read_csv(root/'metadata/metadata.csv');out=root/'reports/figures';out.mkdir(parents=True,exist_ok=True)
    generated=[r for r in rows if r['source_id']=='generated']
    example=next((r for r in generated if r['label']=='A' and r['noise_type']=='none'),generated[0] if generated else rows[0])
    audio,sr=sf.read(root/example['filename'])
    def save(name):plt.tight_layout();plt.savefig(out/name,dpi=150);plt.close()
    plt.figure(figsize=(9,3));plt.plot(np.arange(len(audio))/sr,audio,lw=.7);plt.xlabel('Time (s)');plt.ylabel('Amplitude');plt.title(f"Waveform: {example['label']} / {example['noise_type']}");save('waveform.png')
    f,t,z=spectrogram(audio,sr,nperseg=min(256,len(audio)))
    plt.figure(figsize=(9,3));plt.pcolormesh(t,f,10*np.log10(z+1e-15),shading='auto');plt.ylim(0,min(2500,sr/2));plt.xlabel('Time (s)');plt.ylabel('Frequency (Hz)');plt.colorbar(label='PSD (dB/Hz)');save('spectrogram.png')
    from collections import Counter
    labels=sorted({r['label'] for r in rows});x=np.arange(len(labels))
    plt.figure(figsize=(12,4))
    for offset,sp in enumerate(('train','validation','test')):
        c=Counter(r['label'] for r in rows if r['split']==sp);plt.bar(x+(offset-1)*.26,[c[l] for l in labels],width=.26,label=sp)
    plt.xticks(x,labels);plt.ylabel('Count');plt.title('Active dataset: per-class counts');plt.legend(loc='upper left',bbox_to_anchor=(1,1));save('class_counts.png')
    plt.figure(figsize=(9,4))
    for sp in ('train','validation','test'):
        vals=[float(r['duration']) for r in rows if r['split']==sp];plt.hist(vals,bins=40,alpha=.45,label=sp)
    plt.xlabel('Duration (s)');plt.ylabel('Count');plt.legend();save('duration_distribution.png')
    plt.figure(figsize=(9,4))
    for name,subset in [('reused',[r for r in rows if r['source_id']!='generated']),('generated',generated)]:
        vals=[float(r['frequency']) for r in subset if r['frequency']];plt.hist(vals,bins=30,alpha=.5,label=name)
    plt.xlabel('Metadata carrier frequency (Hz)');plt.ylabel('Count');plt.legend();save('frequency_distribution.png')
    counts=Counter('clean' if r['snr_db']=='' else str(float(r['snr_db'])) for r in rows)
    keys=sorted((k for k in counts if k!='clean'),key=float);keys+=['clean'] if 'clean' in counts else []
    plt.figure(figsize=(9,4));plt.bar(keys,[counts[k] for k in keys]);plt.xlabel('Metadata SNR (dB), whole-recording RMS');plt.ylabel('Count');save('snr_distribution.png')
    write_json(root/'reports/figure_provenance.json',{'example_sample_id':example['sample_id'],'example_path':example['filename'],
        'scope':'active index only; metadata carrier/SNR, not estimated from WAV','figures':sorted(p.name for p in out.glob('*.png'))})
